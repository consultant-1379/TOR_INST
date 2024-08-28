#!/bin/bash

## hostname of the first node in the cluster
sc_node=$(litp /inventory/deployment1/cluster1/sc1/control_1/os/system show | grep hostname | awk -F\" '{print $2}')
tmp_log=aaa_1.tmp
bold=$(tput bold)
normal=$(tput sgr0)
declare -a appList

## Cluster status
nodes_in_cluster () {
  printf "Cluster status\n"
  result=$(ssh $sc_node "cmw-status -v node")
  p=0 ## if p == 3 print result
  for line in $result; do
    if [[ $line =~ safAmfNode ]]; then 
	  node=$(echo $line | awk -F\, '{print $1}' | awk -F \= '{print $2}'); (( p++ ))
	fi
	if [[ $line =~ AdminState ]]; then
	  admState=$line; (( p++ ))
	fi
	if [[ $line =~ OperState ]]; then 
	  operState=$line; (( p++ ))
    fi
    if (( $p == 3 )); then
      printf "%-8s %s  %s\n" $node $admState $operState; p=0
    fi	  
  done
}

## Remove tmp file aaa_1.tmp
clean_up () {
  [[ -e $tmp_log ]] && \rm $tmp_log
}

## Check campaign status per application
app_camp_state () {
  printf "\nCampaign status for deployed applications\n"
  #printf "${bold}App Name   Campaign Name             Status${normal}\n"
  campList=$(ssh $sc_node "cmw-repository-list --campaign | xargs cmw-campaign-status")
  i=0
  for app in $(litp /inventory/deployment1/cluster1/cmw_cluster_config/campaign_generator show -l); do
    appList[$i]=$app
    camp=$(litp /inventory/deployment1/cluster1/cmw_cluster_config/campaign_generator/$app show | grep \
      campaign_file | awk -F\/ '{print $11}' | awk -F\. '{print $1}')
    for line in $campList; do
      if [[ $line =~ $camp ]]; then
   	    status=$(echo $line | awk -F\= '{print $2}')
        printf "%-8s %-23s %s\n" $app $camp $status    #$camp $status
	  fi
    done
	(( i++ ))
  done
}

su_per_app () {
  printf "\nSUs included in applications"
  max_index=${#appList[@]}
  for ((i=0; i < max_index; i++)); do 
    su_list=$(ssh $sc_node "amf-state su | grep ${appList[$i]}")
    printf "\n%s:\n" ${appList[$i]}
	for su in $su_list; do
	  result=$(ssh $sc_node "amf-state su all $su")
	  printf "%s\n" $result
	done  
  done 
}

vcs_si_state () {
  ssh $sc_node "/opt/VRTSvcs/bin/hagrp -state | tail -n +4" >$tmp_log
  printf "\nVCS SI status\n"
  #cat $tmp_log
  while read line; do
	#line="$(echo $line |awk '{print $1, $3, $4}')"
	echo $line
	printf "%s\n" $line
  done < $tmp_log
  clean_up
}

## Main ##
nodes_in_cluster
app_camp_state
su_per_app
#vcs_si_state
echo ""

exit 0
