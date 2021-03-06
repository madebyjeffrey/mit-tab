#Copyright (C) 2011 by Julia Boortz and Joseph Lynch

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import tab_logic
from tab.models import *
import mwmatching
import random
                
#take in list of teams
#return pairing as list of [gov_team, opp_team]


#DOES NOT WORK
def approx_pairing(list_of_teams):
    
    #print list_of_teams[bracket]
    team_ideal = []
    for i in range(len(list_of_teams[bracket])/2):
                #print "i = " + str(i)
                #print list_of_teams[bracket][len(list_of_teams[bracket])-1-i].seed
                #print list_of_teams[bracket][i].seed

                #teamIdeal is (rank, team, speak/seed of ideal team to hit)

        team_ideal +=[(i, list_of_teams[bracket][i], tot_speaks(list_of_teams[bracket][len(list_of_teams[bracket])-1-i]))]
        team_ideal +=[(len(list_of_teams[bracket])-1-i, list_of_teams[bracket][len(list_of_teams[bracket])-1-i], tot_speaks(list_of_teams[bracket][i]))]
            #now_rounds[bracket] = list_of_teams[bracket]
        now_rounds[bracket] = team_ideal

#Works for up to about ten teams
def exhaustive_pairing(list_of_teams):
    #list of all possible pairings
    all_pairs = pair_exhaustively(list_of_teams, [], [])
    #print all_pairs
    #now check weight and choose best
    min_weight = None
    opt_pairing = None
    for pairing in all_pairs:
        #print pairing
        if len(pairing) == 2:
            weight = 0
            for pair in pairing:
                indexA = list_of_teams.index(pair[0])
                indexB = list_of_teams.index(pair[1])
                pairA_opt = list_of_teams[len(list_of_teams)-indexA-1]
                pairB_opt = list_of_teams[len(list_of_teams)-indexB-1]
                weight += calc_weight(pair[0],pair[1],pairA_opt, pairB_opt)
            if min_weight == None:
                min_weight = weight
                opt_pairing = pairing
            else:
                if weight < min_weight:
                    min_weight = weight
                    opt_pairing = pairing
        else:
            weight=0 #right now, don't calculate by in weight. Should change)
    #print opt_pairing
    return opt_pairing
        

   


#will return all possible pairings    
def pair_exhaustively(list_of_teams, cur_pairing, all_pairs):
    #print 
    #print "list_of_teams" + str(list_of_teams)
    #print "cur_pairing" + str(cur_pairing)
    if len(list_of_teams) == 0: #no more teams left to pair
        all_pairs +=[cur_pairing]
        cur_pairing = []
     #   print "all_pairs" + str(all_pairs)
    else:
        if len(list_of_teams)/2 != len(list_of_teams)/2.0 and cur_pairing == []:
            for t in list_of_teams:
                bye = t
                temp_teams = []
                for tmp in list_of_teams:
                    if tmp != bye:
                        temp_teams+=[tmp]
                pair_exhaustively(temp_teams,cur_pairing+[[bye]],all_pairs)
        for i in range(len(list_of_teams)):
       #     print i
            if i!=0:
       #         print "cur_pairing" + str(cur_pairing)
                teams = []
                for t in list_of_teams:
                    teams +=[t]
                teams.remove(list_of_teams[i])
                teams.remove(list_of_teams[0])
         #       print "teams" + str(teams)
          #      print "cur_pair" + str(cur_pairing)
           #     print "all_pairs" + str(all_pairs)
                pair_exhaustively(teams, cur_pairing+[[list_of_teams[0],list_of_teams[i]]], all_pairs)
    return determine_gov_opp(all_pairs)

def perfect_pairing(list_of_teams):
     #assign weights to edges:
    graph_edges = []
    for i in range(len(list_of_teams)):
        for j in range(len(list_of_teams)):
        # may want to change actual penalties
        # a team should not have an edge back to itself
        # nor do we need to calculate an edge from a to b and b to a
            if i > j: 
                wt = calc_weight(list_of_teams[i], list_of_teams[j],i, j, list_of_teams[len(list_of_teams)-i-1], list_of_teams[len(list_of_teams)-j-1], len(list_of_teams)-i-1, len(list_of_teams)-j-1)
                #now add edge to graph
                graph_edges +=[(i,j,wt)]
    #print "graph_edges"
    #print graph_edges
             
    pairings_num = mwmatching.maxWeightMatching(graph_edges, maxcardinality=True)
    #print "Pairing numbers"
    #print pairings_num
    all_pairs = []
    for pair in pairings_num:
        if pair < len(list_of_teams):
            if [list_of_teams[pairings_num.index(pair)], list_of_teams[pair]] not in all_pairs and [list_of_teams[pair], list_of_teams[pairings_num.index(pair)]] not in all_pairs:
                all_pairs +=[[list_of_teams[pairings_num.index(pair)], list_of_teams[pair]]]
                #print "all pairs"
                #print all_pairs
    #print all_pairs
    return determine_gov_opp(all_pairs)




#Determine the weight of the pairing between teamA and teamB, i.e. how bad it is
#teamA_opt is the optimal team for teamA to be paired with
#teamB_opt is the optimal team for teamB to be paired with
             
def calc_weight(team_a,
                team_b,
                team_a_ind,
                team_b_ind,
                team_a_opt,
                team_b_opt,
                team_a_opt_ind,
                team_b_opt_ind):
    """ 
    Calculate the penalty for a given pairing
    
    Args:
        team_a - the first team in the pairing
        team_b - the second team in the pairing
        team_a_ind - the position in the pairing of team_a
        team_b_ind - the position in the pairing of team_b
        team_a_opt - the optimal power paired team for team_a to be paired with
        team_b_opt - the optimal power paired team for team_b to be paired with
        team_a_opt_ind - the position in the pairing of team_a_opt
        team_b_opt_ind - the position in the pairing of team_b_opt
    """
    
    # Get configuration values
    all_settings = dict([(ts.key, ts.value) for ts in TabSettings.objects.all()])
    def try_get(key, default= None):
        try:
            return int(all_settings[key])
        except:
            return default
    current_round = try_get("cur_round", 1)
    tot_rounds = try_get("tot_rounds", 5)
    power_pairing_multiple = try_get("power_pairing_multiple", -1)
    high_opp_penalty = try_get("high_opp_penalty", 0)
    high_gov_penalty = try_get("high_gov_penalty", -100)
    high_high_opp_penalty = try_get("higher_opp_penalty", -10)
    same_school_penalty = try_get("same_school_penalty", -1000)
    hit_pull_up_before = try_get("hit_pull_up_before", -10000)
    hit_team_before = try_get("hit_team_before", -100000)
    
    # Penalize for being far away from ideal power pairings
    if current_round == 1:
        wt = power_pairing_multiple * (abs(team_a_opt.seed - team_b.seed) + abs(team_b_opt.seed - team_a.seed))/2.0
    else:
        wt = power_pairing_multiple * (abs(team_a_opt_ind - team_b_ind) + abs(team_b_opt_ind - team_a_ind))/2.0
   
    half = int(tot_rounds / 2) + 1
    # Penalize for both teams having n/2 + 1 opps, meaning we'll have to give
    # a fifth opp to one of the teams
    if tab_logic.num_opps(team_a) >= half and tab_logic.num_opps(team_b) >= half:
        wt += high_opp_penalty

    # Penalize for both teams having n/2+2 opps, meaning we'll have to give
    # a fourth opp to one of the teams
    if tab_logic.num_opps(team_a) >= half+1 and tab_logic.num_opps(team_b) >= half+1:
        wt += high_high_opp_penalty
    
    # Penalize for both teams having n/2 + 1 govs, meaning we'll have to give
    # a fourth gov to one of the teams
    if tab_logic.num_govs(team_a) >= half and tab_logic.num_govs(team_b) >= half:
        wt += high_gov_penalty
        
    # Penalize for teams being from the same school
    if team_a.school == team_b.school:
        wt += same_school_penalty
        
    # Penalize for team hitting pull-up more than once
    if (tab_logic.hit_pull_up(team_a) and tab_logic.tot_wins(team_b) < tab_logic.tot_wins(team_a)) or (tab_logic.hit_pull_up(team_b) and tab_logic.tot_wins(team_a) < tab_logic.tot_wins(team_b)):
        wt += hit_pull_up_before

    # Penalize for teams hitting each other before 
    if tab_logic.hit_before(team_a, team_b):
        wt += hit_team_before
        
    return wt




#convert a sorted list of teams to a power pairing
def listToPair(listOfTeams):
    pair = [None]*(len(listOfTeams)/2)
    for i in range(len(listOfTeams)/2):
        pair[i] = [listOfTeams[i],listOfTeams[(len(listOfTeams)-1-i)]]
    return pair

def totPairs(teams):
    tot = 1
    for i in range(len(teams)):
        if i/2 != i/2.0:
            tot*=i
   # print tot
    return tot


def determine_gov_opp(all_pairs):
    final_pairings = []
    for p in all_pairs:
        if tab_logic.num_govs(p[0]) < tab_logic.num_govs(p[1]): #p[0] should be gov
            final_pairings +=[[p[0],p[1]]]
        elif tab_logic.num_govs(p[1]) < tab_logic.num_govs(p[0]): #p[1] should be gov
            final_pairings +=[[p[1],p[0]]]
        elif tab_logic.num_opps(p[0]) < tab_logic.num_opps(p[1]): #p[1] should be gov
            final_pairings +=[[p[1],p[0]]]
        elif tab_logic.num_opps(p[1]) < tab_logic.num_opps(p[0]): #p[0] should be gov
            final_pairings +=[[p[0],p[1]]]
        elif random.randint(0,1) == 0:
            final_pairings +=[[p[0],p[1]]]
        else:
            final_pairings +=[[p[1],p[0]]]
    return final_pairings
                                                        

                                 
