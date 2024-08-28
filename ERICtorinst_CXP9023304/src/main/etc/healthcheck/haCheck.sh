#!/bin/bash

# sc1 & sc2 hostnames
sc1=$(litp /inventory/deployment1/cluster1/sc1/control_1/os/system show | grep hostname | awk -F\" '{print $2}')
sc2=$(litp /inventory/deployment1/cluster1/sc2/control_2/os/system show | grep hostname | awk -F\" '{print $2}')
tmp_log=aaa_1.tmp
bold=$(tput bold)
normal=$(tput sgr0)

clean_up () {
  [[ -e $tmp_log ]] && \rm $tmp_log
}

printf "Checking HACS Configuration$\n"
# llt status
RESULT=$(ssh $sc1 "service llt status")
if [[ $RESULT == "LLT is loaded and configured" ]]; then
  printf "llt is loaded and configured on $sc1 ... OK\n"
else
  printf "  llt is not loaded or configured on $sc1 ... NOK\n" 
  printf "  Login to $sc1 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
  exit 1
fi
RESULT=$(ssh $sc2 "service llt status")
if [[ $RESULT == "LLT is loaded and configured" ]]; then
  printf "llt is loaded and configured on $sc2 ... OK\n"
else
  printf "  llt is not loaded or configured on $sc2 ... NOK\n" 
  printf "  Login to $sc2 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
  exit 1
fi

# gab status
RESULT=$(ssh $sc1 "service gab status")
if [[ $RESULT == "GAB is loaded and configured" ]]; then
  printf "gab is loaded and configured on $sc1 ... OK\n"
else
  printf "  gab is not loaded or configured on $sc1 ... NOK\n" 
  printf "  Login to $sc1 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
  exit 1
fi
RESULT=$(ssh $sc2 "service gab status")
if [[ $RESULT == "GAB is loaded and configured" ]]; then
  printf "gab is loaded and configured on $sc2 ... OK\n"
else
  printf "  gab is not loaded or configured on $sc2 ... NOK\n" 
  printf "  Login to $sc2 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
  exit 1
fi

# had status
RESULT=$(ssh $sc1 "pgrep had")
if [[ $RESULT != "" ]]; then
  printf "had is running on $sc1 ... OK\n"
else
  printf "  had is not running on $sc1 ... NOK\n" 
  printf "  Login to $sc1 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
  exit 1
fi
RESULT=$(ssh $sc2 "pgrep had")
if [[ $RESULT != "" ]]; then
  printf "had is running on $sc2 ... OK\n"
else
  printf "  had is not running on $sc2 ... NOK\n" 
  printf "  Login to $sc2 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
  exit 1
fi

# vcs_csgvip & vcs_gcovip from inventory
vcs_csgvip=$(litp /inventory/deployment1/cluster1/vcs_config show | grep vcs_csgvip | awk -F\" '{print $2}')
vcs_gcovip=$(litp /inventory/deployment1/cluster1/vcs_config show | grep vcs_gcovip | awk -F\" '{print $2}')

# csgnic check
RESULT=$(ssh $sc1 "/opt/VRTSvcs/bin/hares -state csgnic -sys $sc1")
if [[ $RESULT == "ONLINE" ]]; then 
  printf "csgnic is ONLINE on $sc1 ... OK\n"
else
  printf "csgnic is NOT ONLINE on $sc1 ... NOK\n" 
  printf "Login to $sc1 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
fi

RESULT=$(ssh $sc2 "/opt/VRTSvcs/bin/hares -state csgnic -sys $sc2")
if [[ $RESULT == "ONLINE" ]]; then
  printf "csgnic is ONLINE on $sc2 ... OK\n"
else 
  printf "  csgnic is NOT ONLINE on $sc2 ... NOK\n"
  printf "  Login to $sc2 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
fi

# gcoip check
RESULT_sc1=$(ssh $sc1 "/opt/VRTSvcs/bin/hares -state gcoip -sys $sc1")
RESULT_sc2=$(ssh $sc2 "/opt/VRTSvcs/bin/hares -state gcoip -sys $sc2")
[[ $RESULT_sc1 == "ONLINE" ]] && printf "gcoip in ONLINE on $sc1 ... OK\n"
[[ $RESULT_sc2 == "ONLINE" ]] && printf "gcoip in ONLINE on $sc2 ... OK\n"
if [[ $RESULT_sc1 != "ONLINE" && $RESULT_sc2 != "ONLINE" ]]; then 
  printf "  gcoip is neither ONLINE on $sc1 or $sc2 ... NOK\n"
  printf "  Login to $sc1 or $sc2 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
fi

# webip check
RESULT_sc1=$(ssh $sc1 "/opt/VRTSvcs/bin/hares -state webip -sys $sc1")
RESULT_sc2=$(ssh $sc2 "/opt/VRTSvcs/bin/hares -state webip -sys $sc2")
[[ $RESULT_sc1 == "ONLINE" ]] && printf "webip in ONLINE on $sc1 ... OK\n"
[[ $RESULT_sc2 == "ONLINE" ]] && printf "webip in ONLINE on $sc2 ... OK\n"
if [[ $RESULT_sc1 != "ONLINE" && $RESULT_sc2 != "ONLINE" ]]; then 
  printf "  webip in neither ONLINE on $sc1 or $sc2 ... NOK\n"
  printf "  Login to $sc1 or $sc2 and check the /var/VRTSvcs/log/engine_A.log for more information\n"
fi

# HB check
low_hb=$(litp /inventory/deployment1/cluster1/vcs_config show | grep vcs_lltlinklowpri1 | awk -F\" '{print $2}')
hb1=$(litp /inventory/deployment1/cluster1/vcs_config show | grep vcs_lltlink1 | awk -F\" '{print $2}')
hb2=$(litp /inventory/deployment1/cluster1/vcs_config show | grep vcs_lltlink2 | awk -F\" '{print $2}')
printf "\nChecking HB connectivity between $sc1 and $sc2. Please wait\n"
# all HB interfaces should be on different NIC/bond
llt_hb=0
if [[ $low_hb == $hb1 || $low_hb == $hb2 || $hb1 == $hb2 ]]; then 
  printf "\n${bold}WARNING:${normal} Each HB link need to use different physical NIC\n \
      (e.g. lltlinklowpri1 => bond0, lltlink1 => eth3, lltlink2 => eth4)\n \
      Correct the settings in /etc/llttab file on $sc1 and $sc2\n \
      Only lltlinklowpri1 connection between nodes will be be tested\n\n"
  llt_hb=1
fi
# pinging sc1 from sc2
coproc ssh $sc1 "/opt/VRTSllt/lltping -s"
ssh $sc2 "/opt/VRTSllt/lltping -c 0" >$tmp_log
grep $low_hb $tmp_log | grep UP >/dev/null
sleep 1
if (( $? == 0 )); then
  printf "Low priority HB (lltlinklowpri1) ... OK\n"
else 
  printf "Low priority HB (lltlinklowpri1) is not UP ... NOK\n" 
  printf "  Check /etc/llttab or /var/VRTSvcs/log/engine_A.log for more information\n\n"
fi
if (( $llt_hb == 0 )); then
  grep $hb1 $tmp_log | grep UP >/dev/null; sleep 1
  if (( $? == 0 )); then
    printf "HB1 (lltlink1) ... OK\n"
  else
    printf "HB1 (lltlink1) is not UP ... NOK\n" 
    printf "  Check /etc/llttab or /var/VRTSvcs/log/engine_A.log for more information\n\n"
  fi
  grep $hb2 $tmp_log | grep UP >/dev/null; sleep 1
  if (( $? == 0 )); then
    printf "HB2 (lltlink1) ... OK\n"
  else
    printf "HB2 (lltlink1) is not UP ... NOK\n" 
    printf "  Check /etc/llttab or /var/VRTSvcs/log/engine_A.log for more information\n\n"
  fi
fi

# stop lltping on sc1
printf "Stopping lltping process on $sc1 ... "
P=$(ssh $sc1 "pgrep lltping")
ssh $sc1 "kill $P"
$(ssh $sc1 "pgrep lltping") # check if process was killed
if (( $? == 0 )); then
  printf "NOK\n" 
  printf "  Cannot stop lttping process on $sc1\n"
  printf "  Login to $sc1 and kill lttping process manually\n\n"
else
  printf "OK\n\n"
fi

# remove the tmp file
clean_up

exit 0
