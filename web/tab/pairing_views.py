from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import Http404,HttpResponse,HttpResponseRedirect
from django.contrib.auth.decorators import permission_required
from django.utils import simplejson
from errors import *
from models import *
from django.shortcuts import redirect
from forms import ResultEntryForm, UploadFileForm, score_panel, validate_panel
import cache_logic
import tab_logic
import assign_judges
import random
import sys
import traceback
import send_texts as texting
import backup
import time
import datetime
import os
import pprint

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def swap_judges_in_round(request, src_round, src_judge, dest_round, dest_judge):
    try :
        src_judge = Judge.objects.get(id=int(src_judge))
        dest_judge = Judge.objects.get(id=int(dest_judge))
        
        src_round = Round.objects.get(id=int(src_round))
        dest_round = Round.objects.get(id=int(dest_round))
        
        dest_round.judge = src_judge
        src_round.judge = dest_judge
        dest_round.save()
        src_round.save()
        data = {"success":True}
    except Exception as e:
        print "ARG ", e
        data = {"success":False}
    data = simplejson.dumps(data)
    return HttpResponse(data, mimetype='application/json')

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def swap_teams_in_round(request, src_round, src_team, dest_round, dest_team):
    try :
        src_team = Team.objects.get(id=int(src_team))
        dest_team = Team.objects.get(id=int(dest_team))
        if int(src_round) == int(dest_round):
            same_round = Round.objects.get(id=int(src_round))
            gov_team = same_round.gov_team
            opp_team = same_round.opp_team
            same_round.gov_team = opp_team
            same_round.opp_team = gov_team
            same_round.save()
        else:
            src_round = Round.objects.get(id=int(src_round))
            dest_round = Round.objects.get(id=int(dest_round))
            if src_round.gov_team == src_team:
                if dest_round.gov_team == dest_team:
                    # Swap the two gov teams
                    src_round.gov_team = dest_team
                    dest_round.gov_team = src_team
                else:
                    # Swap src_rounds gov team with 
                    # dest_round's opp team
                    src_round.gov_team = dest_team
                    dest_round.opp_team = src_team
            else:
                if dest_round.gov_team == dest_team:
                    # Swap src_rounds opp team with
                    # dest_round's gov team
                    src_round.opp_team = dest_team
                    dest_round.gov_team = src_team
                else:
                    # Swap the two opp teams
                    src_round.opp_team = dest_team
                    dest_round.opp_team = src_team
            dest_round.save()
            src_round.save()
        data = {'success':True}
    except Exception as e:
        print "Unable to swap teams: ", e
        data = {'success':False}
    data = simplejson.dumps(data)
    return HttpResponse(data, mimetype='application/json')


@permission_required('tab.tab_settings.can_change', login_url="/403/")
def pair_round(request):
    cache_logic.clear_cache()
    current_round = TabSettings.objects.get(key="cur_round")
    next_round = current_round.value 
    if request.method == 'POST':
        try:
            backup.backup_round("round_%i_before_pairing.db" % (next_round))
            tab_logic.pair_round()
            backup.backup_round("round_%i_after_pairing.db" % (next_round))
        except Exception, e:
            traceback.print_exc(file=sys.stdout)
            return render_to_response('error.html', 
                                 {'error_type': "Pair Next Round",
                                  'error_name': "Pairing Round %s" % (current_round.value + 1),
                                  'error_info':"Could not pair next round because of: [%s]" %(e)}, 
                                  context_instance=RequestContext(request))           
        current_round.value = current_round.value + 1
        current_round.save() 
        return view_status(request)
    else:
        #We must check a few things:
        # 1) Have all round results been entered
        # 2) Do the round results make sense
        # 3) Are all Judges Checked In
        check_status = []
        current_round = current_round.value
        title = "Pairing Round %s" % (current_round)
        num_rounds = TabSettings.objects.get(key="tot_rounds").value
        rounds = Round.objects.filter(round_number = current_round-1)
        msg = "All Rounds Entered for Overall Round %s" % (current_round-1)
        if not all(map(lambda r: r.victor != 0, rounds)):
            check_status.append((msg, "No", "Missing rounds from the previous round."))
        else :
            check_status.append((msg, "Yes", "Results for previous round have all been entered."))
        #Put sanity checks here
        # end
        checkins = CheckIn.objects.filter(round_number = current_round)
        checked_in_judges = set([c.judge for c in checkins])
        n_over_two = Team.objects.filter(checked_in=True).count() / 2
        msg = "N/2 Judges checked in for Round %s? Need %d, have %d." % (current_round, n_over_two, len(checked_in_judges))
        if len(checked_in_judges) < n_over_two:
            check_status.append((msg, 
                                 "No", 
                                 "Not enough judges checked in. Need %i and only have %i"%(n_over_two,len(checked_in_judges))
                                 ))
        else:
            check_status.append((msg, "Yes", "Have judges"))
        ready_to_pair = "Yes"
        ready_to_pair_alt = "Checks passed!"
        try:
            tab_logic.ready_to_pair(current_round)
        except Exception as e:
            ready_to_pair = "No"
            ready_to_pair_alt = str(e) 
        check_status.append(("Additional Minor Checks (Enough Rooms)", ready_to_pair, ready_to_pair_alt))
        
        return render_to_response('pair_round.html',
                                  locals(),
                                  context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def assign_judges_to_pairing(request):
    current_round_number = TabSettings.objects.get(key="cur_round").value - 1
    if request.method == 'POST':
        print "Assigning judges"
        print request.POST
        panel_points, errors = [], []
        potential_panel_points = [k for k in request.POST.keys() if k.startswith('panel_')]
        for point in potential_panel_points:
           try:
               point = int(point.split("_")[1])
               num = float(request.POST["panel_{0}".format(point)])
               if num > 0.0:
                   panel_points.append((Round.objects.get(id=point), num))
           except Exception as e:
               errors.append(e)
               pass

        panel_points.reverse()
        rounds = list(Round.objects.filter(round_number=current_round_number))
        judges = [ci.judge for ci in CheckIn.objects.filter(round_number=current_round_number)]
        try:
            assign_judges.add_judges(rounds, judges, panel_points)
        except Exception as e:
            return render_to_response('error.html',
                                     {'error_type': "Judge Assignment",
                                      'error_name': "",
                                      'error_info': str(e)},
                                      context_instance=RequestContext(request))
        return view_round(request, current_round_number)
    else:
        return view_round(request, current_round_number)


@permission_required('tab.tab_settings.can_change', login_url='/403/')
def view_backup(request, filename):
    backups = backup.list_backups()
    item_list = []
    item_type='backup'
    title = "Viewing Backup: {}".format(filename)
    item_manip = "restore from that backup"
    links = [('/backup/download/{}/'.format(filename), "Download Backup", False),
             ('/backup/restore/{}/'.format(filename), "Restore From Backup", True)]
    return render_to_response('list_data.html', locals(), context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url='/403/')
def download_backup(request, filename):
    print "Trying to download {}".format(filename)
    wrapper, size = backup.get_wrapped_file(filename)
    response = HttpResponse(wrapper, content_type='text/plain')
    response['Content-Length'] = size
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    return response

@permission_required('tab.tab_settings.can_change', login_url='/403/')
def upload_backup(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            backup.handle_backup(request.FILES['file'])
            return render_to_response('thanks.html', 
                                     {'data_type': "Backup",
                                      'data_name': request.FILES['file'].name,
                                      'data_modification': "CREATE"}, 
                                      context_instance=RequestContext(request))
    else:
        form = UploadFileForm()
    return render_to_response('data_entry.html', 
                              {'form': form,
                               'title': 'Upload a Backup'}, 
                               context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def manual_backup(request):
    try:
        cur_round, btime = TabSettings.objects.get(key="cur_round").value, int(time.time())
        now = datetime.datetime.fromtimestamp(btime).strftime("%Y-%m-%d_%I:%M")
        backup.backup_round("manual_backup_round_{}_{}_{}.db".format(cur_round, btime, now))
    except:
        traceback.print_exc(file=sys.stdout)
        return render_to_response('error.html',
                                 {'error_type': "Manual Backup",'error_name': "Backups",
                                  'error_info': "Could not backup database. Something is wrong with your AWS setup."},
                                  context_instance=RequestContext(request))
    return render_to_response('thanks.html',
                             {'data_type': "Backing up database",
                              'data_name': " for round {} as version number {}".format(cur_round, btime)},
                               context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def view_backups(request):
    backups = backup.list_backups()
    item_list = [(i,i) for i in sorted(backups)]
    item_type='backup'
    title = "Viewing All Backups"
    item_manip = "restore from that backup"
    links = [('/upload_backup/', "Upload Backup", False)]
    return render_to_response('list_data.html', locals(), context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def restore_backup(request, filename):
    print "Trying to restore %s" % filename
    backup.restore_from_backup(filename)
    return render_to_response('thanks.html',
                             {'data_type': "Restored from backup",
                              'data_name': "{}".format(filename)},
                               context_instance=RequestContext(request))
    
    
def view_status(request):
    current_round_number = TabSettings.objects.get(key="cur_round").value-1
    return view_round(request, current_round_number)

def view_round(request, round_number, errors = None):
    if errors is None:
        errors = []
    valid_pairing, byes = True, []
    print "1: ",time.time()
    round_pairing = list(Round.objects.filter(round_number = round_number))

    random.seed(1337)
    random.shuffle(round_pairing)
    round_pairing.sort(key = lambda x: tab_logic.team_comp(x, round_number),
                       reverse = True)

    print "2: ",time.time()
    #For the template since we can't pass in something nicer like a hash
    round_info = [[pair]+[None]*8 for pair in round_pairing]
    for pair in round_info:
        pair[1] = tab_logic.tot_wins(pair[0].gov_team)
        pair[2] = tab_logic.tot_speaks(pair[0].gov_team)
        pair[3] = tab_logic.num_govs(pair[0].gov_team)    
        pair[4] = tab_logic.num_opps(pair[0].gov_team)    
        pair[5] = tab_logic.tot_wins(pair[0].opp_team)
        pair[6] = tab_logic.tot_speaks(pair[0].opp_team)
        pair[7] = tab_logic.num_govs(pair[0].opp_team)    
        pair[8] = tab_logic.num_opps(pair[0].opp_team)
    print "3: ",time.time()

    paired_teams = [team.gov_team for team in round_pairing] + [team.opp_team for team in round_pairing]
    n_over_two = Team.objects.filter(checked_in=True).count() / 2
    valid_pairing = len(round_pairing) >= n_over_two
    for present_team in Team.objects.filter(checked_in=True):
        if not (present_team in paired_teams):
            errors.append("%s was not in the pairing" % (present_team))
            byes.append(present_team) 
    pairing_exists = len(round_pairing) > 0 
    excluded_judges = Judge.objects.exclude(judges__round_number = round_number).filter(checkin__round_number = round_number)
    non_checkins = Judge.objects.exclude(judges__round_number = round_number).exclude(checkin__round_number = round_number)
    size = max(map(len, [excluded_judges, non_checkins, byes]))
    # The minimum rank you want to warn on
    warning = 5
    judge_slots = [1,2,3]
    print "4: ",time.time()

    # A seemingly complex one liner to do a fairly simple thing
    # basically this generates the table that the HTML will display such that the output looks like:
    # [ Byes ][Judges not in round but checked in][Judges not in round but not checked in]
    # [ Team1][             CJudge1              ][                 Judge1               ]
    # [ Team2][             CJudge2              ][                 Judge2               ]
    # [      ][             CJudge3              ][                 Judge3               ]
    # [      ][                                  ][                 Judge4               ]
    excluded_people = zip(*map( lambda x: x+[""]*(size-len(x)), [list(byes), list(excluded_judges), list(non_checkins)])) 

    return render_to_response('display_info.html',
                               locals(),
                               context_instance=RequestContext(request))

def alternative_judges(request, round_id, judge_id=None):
    round_obj = Round.objects.get(id=int(round_id))
    round_number = round_obj.round_number
    round_gov, round_opp = round_obj.gov_team, round_obj.opp_team
    # All of these variables are for the convenience of the template
    try:
        current_judge_id = int(judge_id)
        current_judge_obj = Judge.objects.get(id=current_judge_id)
        current_judge_name = current_judge_obj.name
        current_judge_rank = current_judge_obj.rank
    except TypeError:
        current_judge_id, current_judge_obj, current_judge_rank = "","",""
        current_judge_name = "No judge"
    excluded_judges = Judge.objects.exclude(judges__round_number = round_number) \
                                   .filter(checkin__round_number = round_number)
    included_judges = Judge.objects.filter(judges__round_number = round_number) \
                                   .filter(checkin__round_number = round_number)
    excluded_judges = [(j.name, j.id, float(j.rank))
                       for j in
                       assign_judges.can_judge_teams(excluded_judges, round_gov, round_opp)]
    included_judges = [(j.name, j.id, float(j.rank))
                       for j in
                       assign_judges.can_judge_teams(included_judges, round_gov, round_opp)]
    included_judges = sorted(included_judges, key=lambda x: -x[2])
    excluded_judges = sorted(excluded_judges, key=lambda x: -x[2])

    return render_to_response('judge_dropdown.html',
                              locals(),
                              context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def assign_judge(request, round_id, judge_id, remove_id=None):
    try :
        round_obj = Round.objects.get(id=int(round_id))
        judge_obj = Judge.objects.get(id=int(judge_id))
        if remove_id is not None:
            remove_obj = Judge.objects.get(id=int(remove_id))
            round_obj.judges.remove(remove_obj)

        round_obj.judges.add(judge_obj)
        round_obj.save()
        data = {"success":True,
                "round_id": round_obj.id,
                "judge_name": judge_obj.name,
                "judge_rank": float(judge_obj.rank),
                "judge_id": judge_obj.id}
    except Exception as e:
        print "Failed to assign judge: ", e
        data = {"success":False}
    data = simplejson.dumps(data)
    return HttpResponse(data, mimetype='application/json')

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def remove_judge(request, round_id, judge_id):
    try :
        round_obj = Round.objects.get(id=int(round_id))
        judge_obj = Judge.objects.get(id=int(judge_id))

        round_obj.judges.remove(judge_obj)
        round_obj.save()
        data = {"success":True,
                "round_id": round_obj.id,
                "judge_name": judge_obj.name,
                "judge_rank": float(judge_obj.rank),
                "judge_id": judge_obj.id}
    except Exception as e:
        print "Failed to assign judge: ", e
        data = {"success":False}
    data = simplejson.dumps(data)
    return HttpResponse(data, mimetype='application/json')


@permission_required('tab.tab_settings.can_change', login_url="/403/")
def send_texts(request):
    try:
        print "#"*80
        print "Sending Texts"   
        print "#"*80
        texting.text()
        print "done sending "
        print "#"*80
    except:
        traceback.print_exc(file=sys.stdout)
        return render_to_response('error.html',
                                 {'error_type': "Texting",'error_name': "Texts",
                                  'error_info': "Could not send texts. Sorry."},
                                  context_instance=RequestContext(request))
    return render_to_response('thanks.html',
                             {'data_type': "Texting",
                              'data_name': "Texts"},
                               context_instance=RequestContext(request))

"""dxiao: added a html page for showing tab for the current round.
Uses view_status and view_round code from revision 108."""
def pretty_pair(request, printable=False):

    errors, byes = [], []

    round_number = TabSettings.objects.get(key="cur_round").value-1
    round_pairing = list(Round.objects.filter(round_number = round_number))

    #We want a random looking, but constant ordering of the rounds
    random.seed(0xBEEF)
    random.shuffle(round_pairing)
    round_pairing.sort(key=lambda r: r.gov_team.name)
    paired_teams = [team.gov_team for team in round_pairing] + [team.opp_team for team in round_pairing]

    byes = [bye.bye_team for bye in Bye.objects.filter(round_number=round_number)]

    print "getting errors"
    for present_team in Team.objects.filter(checked_in=True):
        if not (present_team in paired_teams):
            if present_team not in byes:
                print "got error for", present_team
                errors.append(present_team) 

    pairing_exists = len(round_pairing) > 0
    printable = printable
    return render_to_response('round_pairings.html',
                               locals(),
                               context_instance=RequestContext(request))

def pretty_pair_print(request):
    return pretty_pair(request, True)

def view_rounds(request):
    number_of_rounds = TabSettings.objects.get(key="tot_rounds").value
    rounds = [(i, "Round %i" % i) for i in range(1,number_of_rounds+1)]
    return render_to_response('list_data.html',
                              {'item_type':'round',
                               'item_list': rounds,
                               'show_delete': True},
                              context_instance=RequestContext(request))

def enter_result(request, round_id):
    round_obj = Round.objects.get(id=round_id)
    if request.method == 'POST':
        form = ResultEntryForm(request.POST, round_instance=round_obj)
        if form.is_valid():
            try:
                result = form.save()
            except ValueError:
                return render_to_response('error.html', 
                                         {'error_type': "Round Result",
                                          'error_name': "["+str(round_obj)+"]",
                                          'error_info':"Invalid round result, could not remedy."}, 
                                          context_instance=RequestContext(request))
            return render_to_response('thanks.html', 
                                     {'data_type': "Round Result",
                                      'data_name': "["+str(round_obj)+"]"}, 
                                      context_instance=RequestContext(request))
    else:
        is_current = round_obj.round_number == TabSettings.objects.get(key="cur_round")
        form = ResultEntryForm(round_instance=round_obj)
    return render_to_response('round_entry.html', 
                              {'form': form,
                               'title': "Entering Ballot for {}".format(str(round_obj)),
                               'gov_team': round_obj.gov_team,
                               'opp_team': round_obj.opp_team}, 
                               context_instance=RequestContext(request))


def enter_multiple_results(request, round_id, num_entered):
    round_obj = Round.objects.get(id=round_id)
    num_entered = max(int(num_entered), 1)
    if request.method == 'POST':
        forms = [ResultEntryForm(request.POST,
                                 prefix=str(i),
                                 round_instance=round_obj,
                                 no_fill = True)
                 for i in range(1, num_entered +1)]
        all_good = True
        for form in forms:
            all_good = all_good and form.is_valid()
        if all_good:
            # result is of the format:
            # winner_1 => [(debater, role, speaks, rank), (debater, role, speaks, rank) ...]
            # winner_2 => [(debater, role, sp ...]
            result = {}
            debaters = ResultEntryForm.GOV + ResultEntryForm.OPP
            for form in forms:
                cleaned_data = form.cleaned_data
                winner = cleaned_data["winner"]
                if winner not in result:
                    result[winner] = []

                result[winner].append([])
                for debater in debaters:
                    old_stats = RoundStats.objects.filter(round=round_obj, debater_role = debater)
                    if len(old_stats) > 0:
                        old_stats.delete()
                    debater_obj = Debater.objects.get(pk=cleaned_data["%s_debater"%(debater)])
                    debater_role_obj = debater
                    speaks_obj, ranks_obj = float(cleaned_data["%s_speaks"%(debater)]),int(cleaned_data["%s_ranks"%(debater)])
                    result[winner][-1].append((debater_obj, debater_role_obj, speaks_obj, ranks_obj))
            # Validate the extracted data and return it
            all_good, error_msg = validate_panel(result)
            if all_good:
                final_scores, final_winner = score_panel(result, "discard_minority" in request.POST)
                print final_scores
                for (debater, role, speaks, ranks) in final_scores:
                    RoundStats.objects.create(debater = debater,
                                              round = round_obj,
                                              speaks = speaks,
                                              ranks = ranks,
                                              debater_role = role)
                round_obj.victor = final_winner
                round_obj.save()
                return render_to_response('thanks.html', 
                                         {'data_type': "Round Result",
                                          'data_name': "["+str(round_obj)+"]"}, 
                                          context_instance=RequestContext(request))
            else:
                forms[0]._errors["winner"] = forms[0].error_class([error_msg])
    else:
        forms = [ResultEntryForm(prefix = str(i),
                                 round_instance=round_obj,
                                 no_fill = True) for i in range(1, num_entered + 1)]
    return render_to_response('round_entry_multiple.html',
                              {'forms': forms,
                               'title': "Entering Ballots for {}".format(str(round_obj)),
                               'gov_team': round_obj.gov_team,
                               'opp_team': round_obj.opp_team}, 
                               context_instance=RequestContext(request))

@permission_required('tab.tab_settings.can_change', login_url="/403/")
def confirm_start_new_tourny(request):
    return render_to_response('confirm.html', 
                              {'link': "/pairing/start_tourny/",
                               'confirm_text': "Create New Tournament"}, 
                               context_instance=RequestContext(request))
                               
@permission_required('tab.tab_settings.can_change', login_url="/403/")                               
def start_new_tourny(request):
    try:
        clear_db()
        TabSettings.objects.create(key = "cur_round", value = 1)
        TabSettings.objects.create(key = "tot_rounds", value = 5)
        TabSettings.objects.create(key = "var_teams_to_break", value = 8)
        TabSettings.objects.create(key = "nov_teams_to_break", value = 4)

    
    except Exception as e:
        return render_to_response('error.html', 
                            {'error_type': "Could not Start Tournament",
                            'error_name': "",
                            'error_info':"Invalid Tournament State. Time to hand tab. [%s]"%(e)}, 
                            context_instance=RequestContext(request))
    return render_to_response('thanks.html', 
                            {'data_type': "Started New Tournament",
                            'data_name': ""}, 
                            context_instance=RequestContext(request))
        
def clear_db():
    check_ins = CheckIn.objects.all()
    for i in range(len(check_ins)):
        CheckIn.delete(check_ins[i])
    print "Cleared Checkins"
    
    round_stats = RoundStats.objects.all()
    for i in range(len(round_stats)):
        RoundStats.delete(round_stats[i])
    print "Cleared RoundStats"
        
    rounds = Round.objects.all()
    for i in range(len(rounds)):
        Round.delete(rounds[i])
    print "Cleared Rounds"
        
    judges = Judge.objects.all()
    for i in range(len(judges)):
        Judge.delete(judges[i])
    print "Cleared Judges"
        
    rooms = Room.objects.all()
    for i in range(len(rooms)):
        Room.delete(rooms[i])
    print "Cleared Rooms"
        
    scratches = Scratch.objects.all()
    for i in range(len(scratches)):
        Scratch.delete(scratches[i])
    print "Cleared Scratches"
        
    tab_set = TabSettings.objects.all()
    for i in range(len(tab_set)):
        TabSettings.delete(tab_set[i])
    print "Cleared TabSettings"
        
    teams = Team.objects.all()
    for i in range(len(teams)):
        Team.delete(teams[i])   
    print "Cleared Teams"
    
    debaters = Debater.objects.all()
    for i in range(len(debaters)):
        Debater.delete(debaters[i])
    print "Cleared Debaters"
    
    schools = School.objects.all()
    for i in range(len(schools)):
        School.delete(schools[i])                     
    print "Cleared Schools"
                              
