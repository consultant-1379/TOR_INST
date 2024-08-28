#!/bin/sh

DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
MKDIR=/bin/mkdir
SSH=/usr/bin/ssh
GREP=/bin/grep
AWK=/bin/awk
STEP=0
LOGDIR="/var/log/torinst"
LOGFILE="${LOGDIR}/preUpgrade.log"
SCP=/usr/bin/scp
RM=/bin/rm
RPM=/bin/rpm
SCFW=/definition/os/ossc

get_absolute_path()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/../ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
}


### Function: step_litp() ###
# 
# Executes and prints litp commands.
# Exits if litp command fails
#
# Arguments:
#       None
# Return Values:

function step_litp() {
        STEP=$(( ${STEP} + 1 ))
        printf "Step %03d: litp %s\n" $STEP "$*" 

        command litp "$@" 2>&1 
        if [ "${PIPESTATUS[0]}" -gt 0 ]; then
                exit 1;
        fi
}


### Function: create_ms_dumps_dir() ###
# 
# Creates dump directory in ms node
#
# Arguments:
#       None
# Return Values:

create_ms_dumps_dir()
{
mkdir -p /ericsson/tor/dumps
chown litp_jboss:litp_jboss /ericsson/tor/dumps
}

### Function: create_hcdumps() ###
# 
# It creates heap and core dumps shares
# required before 1.0.17/3 to 1.0.19 upgrade
#
# Arguments:
#       None
# Return Values:
#       None

create_hcdumps()
{

        #HARCODED VALUES START HERE
        local _sharename_="hcdumps"
        local _sharesize_="100G"
        local _mountpoint_=/ericsson/tor/dumps
        #HARCODED VALUES END HERE

        #discover ms data config
        local _component_="/inventory/deployment1/ms1/ms_node/sfs/export_storadm/"
        local _path_=`get_property_value $_component_ path`
        local _path_prefix_=${_path_%-storadm_home}
        local _options_=`get_property_value $_component_ options`
        local _driver_=`get_property_value $_component_ driver`
        local _sfs_user_=`get_property_value $_component_ username`
        local _sfs_pwd_=`get_property_value $_component_ password`
        local _storage_pool_=`get_property_value $_component_ storage_pool`
        local _server_=`get_property_value $_component_ server`

        #discover sc data config
        _component_=/inventory/deployment1/cluster1/sc1/control_1/sfs_homedir/sfs_share_storadm
        local _scdatanet_=`get_property_value $_component_ data_net`
        local _scdatavip_=`get_property_value $_component_ data_vip`

        
        local _name_="${_storage_pool_}-${_sharename_}"
        _path_="${_path_prefix_}-${_sharename_}"



	#configure the share in the definition
  /usr/bin/litp /definition/nasinfo/${_sharename_} show status >/dev/null
  (( $? != 0 )) && step_litp /definition/nasinfo/${_sharename_} create nas-service-def name="${_name_}" options="${_options_}"
  /usr/bin/litp /definition/sfs_client_homedirs/sfs_share_${_sharename_} show status >/dev/null
  (( $? != 0 )) && step_litp /definition/sfs_client_homedirs/sfs_share_${_sharename_} create nas-client-def service="${_name_}" mountpoint="${_mountpoint_}"
  
  /usr/bin/litp /definition materialise >/dev/null

  #update properties in inventory
  step_litp /inventory/deployment1/ms1/ms_node/sfs/${_sharename_} update \
        name="${_name_}" \
        path="${_path_}" \
        driver="${_driver_}" \
        username="${_sfs_user_}" \
        password="${_sfs_pwd_}" \
        storage_pool="${_storage_pool_}" \
        server="${_server_}" \
        shared_size="${_sharesize_}" \
        create_fs=True 

  step_litp /inventory/deployment1/ms1/ms_node/sfs_homedir/sfs_share_${_sharename_} update \
        service="${_name_}" \
        data_net="${_scdatanet_}" \
        data_vip="${_scdatavip_}"

 step_litp /inventory/deployment1/cluster1/sc1/control_1/sfs_homedir/sfs_share_${_sharename_} update \
        service="${_name_}" \
        data_net="${_scdatanet_}" \
        data_vip="${_scdatavip_}"
        
 step_litp /inventory/deployment1/cluster1/sc2/control_2/sfs_homedir/sfs_share_${_sharename_} update \
        service="${_name_}" \
        data_net="${_scdatanet_}" \
        data_vip="${_scdatavip_}"

 step_litp /inventory/deployment1/ms1/ms_node/sfs/${_sharename_} configure
 step_litp /inventory/deployment1/ms1/ms_node/sfs_homedir/sfs_share_${_sharename_} configure
 step_litp /inventory/deployment1/cluster1/sc1/control_1/sfs_homedir/sfs_share_${_sharename_} configure
 step_litp /inventory/deployment1/cluster1/sc2/control_2/sfs_homedir/sfs_share_${_sharename_} configure
 step_litp /cfgmgr apply scope=/inventory/deployment1/
}


### Function: wait_for_hcdumps_apply() ###
# 
# Waits for changes in create_hcdumps function to apply
#
# Arguments:
#       None
# Return Values:
#       None

wait_for_hcdumps_apply()
{
  local _lastcount_=-1
  while [ 1 ] ; do
    local _count_
    log "Changes are being applied to ms and to controller nodes, this may take a couple of minutes..."
    local _1applying_ms1_=`step_litp /inventory/deployment1/ms1/ms_node/sfs/ show -rp | ${GREP} -E "^\[Applying\]" | ${AWK} '{print $2}'`
    local _2applying_ms1_=`step_litp /inventory/deployment1/ms1/ms_node/sfs_homedir/ show -rp | ${GREP} -E "^\[Applying\]" | ${AWK} '{print $2}'`
    local _applying_sc1_=`step_litp /inventory/deployment1/cluster1/sc1/control_1/sfs_homedir/ show -rp | ${GREP} -E "^\[Applying\]" | ${AWK} '{print $2}'`
    local _applying_sc2_=`step_litp /inventory/deployment1/cluster1/sc2/control_2/sfs_homedir/ show -rp | ${GREP} -E "^\[Applying\]" | ${AWK} '{print $2}'`
    local _sum_applying_ms1_=$((${_1applying_ms1_} + ${_2applying_ms1_}))

   log "MS still applying ${_sum_applying_ms1_} components. SC-1 still applying ${_applying_sc1_} components. SC-2 still applying ${_applying_sc2_} components"
    if [ ${_sum_applying_ms1_} -eq 0 ] && [ ${_applying_sc1_} -eq 0 ] && [ ${_applying_sc2_} -eq 0 ] ; then
      log "Changes applied"
      break
    else
      log "Changes still being applied, please wait ..."
      sleep 30
    fi
  done
}

### Function: remove_dirs_from_sc_common() ###
#
# Remove ericsson_dir and eritor_dir from
# definition and inventory before 1.0.19
# due to the change in snippets
# Arguments:
#       None
# Return Values:
#       None

remove_dirs_from_sc_common()
{
log "Updating sc_common_dirs in Definition and Inventory"
	/usr/bin/litp /definition/sc_common_dirs/ericsson_dir delete >/dev/null
	/usr/bin/litp /definition/sc_common_dirs/eritor_dir delete >/dev/null
	/usr/bin/litp /inventory/deployment1/cluster1/sc1/sc_common_dirs/ericsson_dir delete -f >/dev/null
	/usr/bin/litp /inventory/deployment1/cluster1/sc1/sc_common_dirs/eritor_dir delete -f >/dev/null
	/usr/bin/litp /inventory/deployment1/cluster1/sc2/sc_common_dirs/ericsson_dir delete -f >/dev/null
	/usr/bin/litp /inventory/deployment1/cluster1/sc2/sc_common_dirs/eritor_dir delete -f >/dev/null
}

### Function: logrotate_updates() ###
# 
# Update logrotate rules for lms and peer nodes
# Update Selinux context for /var/ericsson/log and subdirectories on peer nodes
#
# Arguments:
#       None
# Return Values:
#       None
logrotate_updates() 
{
  local rc
  local _sc1_
  local _sc2_
  
  log "Removing /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs from definition"
  /usr/bin/litp /definition/logrotate_rules/jboss_logs show status >/dev/null
  (( $? == 0 )) && /usr/bin/litp /definition/logrotate_rules/jboss_logs delete -f

  log "Removing /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs from inventory"
  /usr/bin/litp /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs show status >/dev/null
  if (( $? == 0 )); then
    /usr/bin/litp /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs deconfigure >/dev/null
    /usr/bin/litp /cfgmgr apply scope=/inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs >/dev/null
    while :; do
      log "Waiting for jboss_logs to get removed from inventory..."
      rc=$(/usr/bin/litp /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs show status | grep status | awk -F\" '{print $2}')
      if [[ $rc == "Removed" ]]; then 
        /usr/bin/litp /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs delete -f
        break
      fi
      sleep 30
    done
  else
    log "The /inventory/deployment1/ms1/ms_node/logrotate_rules/jboss_logs already removed from inventory"
  fi

  log "Updating jboss_logs and policy_agent logrotate rules for peer nodes"
  /usr/bin/litp /definition/logrotate_server_rules/jboss_logs update path="/var/ericsson/log/jboss/*/*.log"
  /usr/bin/litp /definition/logrotate_server_rules/policy_agent update copytruncate=true size=6M
  /usr/bin/litp /definition materialise
  /usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules/jboss_logs configure
  /usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules/jboss_logs configure
  
  log "Removing /definition/logrotate_server_rules/jboss_console_logrotate from definition"
  /usr/bin/litp /definition/logrotate_server_rules/jboss_console_logrotate show status >/dev/null
  (( $? == 0 )) && /usr/bin/litp /definition/logrotate_server_rules/jboss_console_logrotate delete -f

  log "Removing jboss_console_logrotate from logrotate_server_rules inventory - SC-1"
  /usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules/jboss_console_logrotate show status >/dev/null
  if (( $? == 0 )); then 
    /usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules/jboss_console_logrotate deconfigure >/dev/null
    /usr/bin/litp /cfgmgr apply scope=/inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules
    while :; do
      log "Waiting for jboss_console_logrotate to get removed from inventory - SC-1..."
      rc=$(/usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules/jboss_console_logrotate show status | grep status | awk -F\" '{print $2}')
      if [[ $rc == "Removed" ]]; then 
        /usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules/jboss_console_logrotate delete -f
        break
      fi
      sleep 30
    done
  else 
    log "The /inventory/deployment1/cluster1/sc1/control_1/logrotate_server_rules/jboss_console_logrotate already removed from inventory"
  fi
  
  log "Removing jboss_console_logrotate from logrotate_server_rules inventory - SC-2"
  /usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules/jboss_console_logrotate show status >/dev/null
  if (( $? == 0 )); then 
    /usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules/jboss_console_logrotate deconfigure >/dev/null
    /usr/bin/litp /cfgmgr apply scope=/inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules
    while :; do
      log "Waiting for jboss_console_logrotate to get removed from inventory - SC-2..."
      rc=$(/usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules/jboss_console_logrotate show status | grep status | awk -F\" '{print $2}')
      if [[ $rc == "Removed" ]]; then
        /usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules/jboss_console_logrotate delete -f
        break
      fi
      sleep 30
    done
  else
    log "The /inventory/deployment1/cluster1/sc2/control_2/logrotate_server_rules/jboss_console_logrotate already removed from inventory"
  fi

  log "Setting up the var_log_t context on /var/ericsson/log on the peer nodes"
  _sc1_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os/system show | grep hostname | awk -F\" '{print $2}')
  _sc2_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os/system show | grep hostname | awk -F\" '{print $2}')
  ssh ${_sc1_} "ls -Z /var/ericsson/log" | grep var_log_t >/dev/null
  if (( $? != 0 )); then
    ssh ${_sc1_} 'semanage fcontext -a  -t var_log_t "/var/ericsson/log(/.*)?"'
    ssh ${_sc1_} 'restorecon -R /var/ericsson/log'
  else
    log "var_log_t already set on ${_sc1_}"
  fi

  ssh ${_sc2_} "ls -Z /var/ericsson/log" | grep var_log_t >/dev/null
  if (( $? != 0 )); then
    ssh ${_sc2_} 'semanage fcontext -a  -t var_log_t "/var/ericsson/log(/.*)?"'
    ssh ${_sc2_} 'restorecon -R /var/ericsson/log'
  else
    log "var_log_t already set on ${_sc2_}"
  fi
}

### Function: delete_dump_files() ###
# 
# Delete jboss dumps files under /ericsson/tor/dumps
#
# Arguments:
#       None
# Return Values:
#       None
delete_dump_files() 
{
  local _sc1_
  local _sc2_
  _sc1_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os/system show | grep hostname | awk -F\" '{print $2}')
  _sc2_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os/system show | grep hostname | awk -F\" '{print $2}')
  log "Removing files from /ericsson/tor/dumps directory on peer nodes"
  ssh ${_sc1_} "df -h /ericsson/tor/dumps" | grep vg_root-lv_root
  (( $? == 0 )) && ssh ${_sc1_} "rm -rf /ericsson/tor/dumps/*"
  ssh ${_sc2_} "df -h /ericsson/tor/dumps" | grep vg_root-lv_root
  (( $? == 0 )) && ssh ${_sc2_} "rm -rf /ericsson/tor/dumps/*"
}

### Function: delete_old_jboss_logs() ###
# 
# Delete jboss log files already rotated by jbosstemp from /var/ericsson/log/jboss/*
#
# Arguments:
#       None
# Return Values:
#       None
delete_old_jboss_logs()
{
  local _sc1_
  local _sc2_
  _sc1_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os/system show | grep hostname | awk -F\" '{print $2}')
  _sc2_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os/system show | grep hostname | awk -F\" '{print $2}')
  log "Removing old jboss log files from /var/ericsson/log/jboss directory on peer nodes"
  ssh ${_sc1_} "rm -f /var/ericsson/log/jboss/*/*.log.201*"
  ssh ${_sc2_} "rm -f /var/ericsson/log/jboss/*/*.log.201*"
}

#####################################################################################
#workaround for datapath/pmmedcom shared file /opt/ericsson/datapaths.xml
#needed only to upgrade from 1.0.17 to 1.0.19 iso x.88 or latest
#####################################################################################
datapath_fix()
{

_local_path=/opt/ericsson/torinst/etc/datapath/
_remote_path=/var/tmp/
datapath=ERICdatapath_CXP9030305-1.4.81-1.noarch.rpm
pmmedcom=ERICpmmedcom_CXP9030103-2.14.60-1.noarch.rpm
_nodes_to_upgrade=(sc-1 sc-2)
_files_to_copy=(${pmmedcom} ${datapath})
for sc_node in ${_nodes_to_upgrade[*]} ; do
        for new_files in ${_files_to_copy[*]} ; do
        if [ -f ${_local_path}${new_files} ] ; then

#copy file to remote server
                _result_=$(${SCP} ${_local_path}$new_files ${sc_node}:${_remote_path} 2>&1)
                if [ $? -ne 0 ] ; then
                        error "Can't copy ${_local_path}${new_files} to ${_remote_path} on ${sc_node}:"
                        error "${_result_}"
                        exit 1
                fi
#upgrade rpm on remote server
                _result_=$(${SSH} ${sc_node} "${RPM} -Uva --force ${_remote_path}${new_files}")
                if [ $? -ne 0 ] ; then
                        error "RPM ${_remote_path}${new_files} upgrade failed on ${sc_node}: "
                        error "${_result_}"
                        exit 1
                fi
#cleanup remote server
                _result_=$(${SSH} ${sc_node} "${RM} -rf ${_remote_path}${new_files}")
                if [ $? -ne 0 ] ; then
                        error "failed to remove ${_remote_path}${new_files} on ${sc_node}: "
                        error "${_result_}"
                        exit 1
                fi


        else
                error "No file ${new_files} found on MS in ${_local_path} directory."
                exit 1
        fi
        done
log "On ${sc_node} server RPMs was successfully upgraded"
done

}


#####################################################################################
#workaround for HORNETQ
#needed only to upgrade from 1.0.17 to 1.0.19 iso x.88 or latest
#####################################################################################
hornetq_fix()
{

_local_path=/opt/ericsson/torinst/etc/hornetq/
hornetq_sh=configure_hornetq_cluster.sh
hornetq_py=hornteq.py
hornetq_sh_path=/opt/ericsson/nms/litp/etc/jboss/jboss_instance/post_start.d/
hornetq_py_path=/opt/ericsson/PlatformIntegrationBridge/etc/

_nodes_to_upgrade=(sc-1 sc-2)
for sc_node in ${_nodes_to_upgrade[*]} ; do
#copy configure_hornetq_cluster.sh to remote server
    if [ -f ${_local_path}${hornetq_sh} ] ; then
        _result_=$(${SCP} ${_local_path}${hornetq_sh} ${sc_node}:${hornetq_sh_path} 2>&1)
        if [ $? -ne 0 ] ; then
            error "Can't copy ${_local_path}${hornetq_sh} to ${hornetq_sh_path} on ${sc_node}:"
            error "${_result_}"
            exit 1
        fi
	else 
		log "Can't find ${_local_path}${hornetq_sh} file, skipping to copy it to SC nodes"
    fi       
#copy hornteq.py to remote server        
	if [ -f ${_local_path}${hornetq_py} ] ; then
        _result_=$(${SCP} ${_local_path}${hornetq_py} ${sc_node}:${hornetq_py_path} 2>&1)
        if [ $? -ne 0 ] ; then
            error "Can't copy ${_local_path}${hornetq_py} to ${hornetq_py_path} on ${sc_node}:"
            error "${_result_}"
            exit 1
        fi
    else 
		log "Can't find ${_local_path}${hornetq_py} file, skipping to copy it to SC nodes"
    fi        
#upgrade hornetq configuration on remote server
    _result_=$(${SSH} ${sc_node} "${hornetq_py_path}${hornetq_py}")
    if [ $? -ne 0 ] ; then
        error "hornetq configuration update failed by ${_remote_path}${new_files} on ${sc_node}: "
        error "${_result_}"
        exit 1
    fi
#cleanup remote server
    _result_=$(${SSH} ${sc_node} "${RM} -rf ${hornetq_py_path}${hornetq_py}")
    if [ $? -ne 0 ] ; then
        error "failed to remove ${_remote_path}${new_files} on ${sc_node}: "
        error "${_result_}"
        exit 1
    fi
log "On ${sc_node} server hornetq configuration was successfully upgraded!"
done

}

### Function: campaign_etf_generators() ###
# 
# Delete objects under etf_generator & campaign_generator
#
# Arguments:
#       None
# Return Values:
#       None
campaign_etf_generators()
{
  log "Removing Upgrade object under etf_generator and campaign_generator from inventory"
  for i in $(/usr/bin/litp /inventory show -rp | grep cmw | grep Upgrade | awk '{print $1}' | sort -u); do
    /usr/bin/litp $i delete -f
  done
}

### Function: config_core_dump() ###
# 
# Configure core dump on ms and peer nodes
#
# Arguments:
#       None
# Return Values:
#       None
config_core_dump()
{
  local _core_pattern_="/ericsson/tor/dumps/core.%e.pid%p.usr%u.sig%s.tim%t"
  local _sc1_
  local _sc2_
  _sc1_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os/system show | grep hostname | awk -F\" '{print $2}')
  _sc2_=$(/usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os/system show | grep hostname | awk -F\" '{print $2}')
  log "Configuring core dump on lms"
  sysctl -a | grep ${_core_pattern_} >/dev/null
  (( $? == 0 )) && sysctl -q -w kernel.core_pattern="$_core_pattern_"
  log "Configuring core dump on sc-1"
  ssh ${_sc1_} "sysctl -a" | grep ${_core_pattern_} >/dev/null 
  (( $? == 0 )) && ssh ${_sc1_} 'sysctl -q -w kernel.core_pattern="$_core_pattern_"'
  log "Configuring core dump on sc-2"
  ssh ${_sc2_} "sysctl -a" | grep ${_core_pattern_} >/dev/null
  (( $? == 0 )) && ssh ${_sc2_} 'sysctl -q -w kernel.core_pattern="$_core_pattern_"'
}

### Function: update_fw_rules() ###
# 
# Updating fw rules for ipv6 udp 
# TORD-961 TORD-955
# Arguments:
#       None
# Return Values:
#       None
update_fw_rules()
{
  local rc
  local sc1_appl
  local sc2_appl

  log "Removing sc-1/sc-2 firewall rules from definition"
  for i in $(/usr/bin/litp /definition/os/ossc/ find --name fw_.+); do
    /usr/bin/litp $i delete 
  done
  /usr/bin/litp /definition/os/ossc/Jgroup_probe delete >/dev/null
  
  log "Removing sc-1/sc-2 firewall rules from inventory"
  for i in $(/usr/bin/litp /inventory/deployment1/cluster1/ find --name fw_.+); do
    /usr/bin/litp $i delete -f
  done
  /usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os/Jgroup_probe delete -f >/dev/null
  /usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os/Jgroup_probe delete -f >/dev/null
  
  log "Recreating firewall rules for peer nodes. It may take a while..."
  litp ${SCFW}/fw_tor_basic create firewalls-def name="000 tor Jboss" dport="8080,9990,9999,4447,5445,5455" proto=tcp 
  litp ${SCFW}/fw_basetcp create firewalls-def name="001 basetcp" dport="22,80,111,161,162,443,1389,3000,25151,7788,2163,6389" proto=tcp
  litp ${SCFW}/fw_tor_oss create firewalls-def name="001 tor oss" dport="4569,4570,50042,65532,12468,50057,49786" proto=tcp
  litp ${SCFW}/fw_apps create firewalls-def name="001 custom ports" dport="636,389,1494" proto=tcp
  litp ${SCFW}/fw_nfstcp create firewalls-def name="002 nfstcp" dport="662,875,2020,2049,4001,4045" proto=tcp
  litp ${SCFW}/fw_hyperic create firewalls-def name="003 hyperic" dport="57004,57005,57006" proto=tcp
  litp ${SCFW}/fw_syslog create firewalls-def name="004 syslog" dport="514" proto=tcp
  litp ${SCFW}/fw_syslogudp create firewalls-def name="004 syslogudp" dport="514" proto=udp
  litp ${SCFW}/fw_baseudp create firewalls-def name="010 baseudp" dport="111,123,623,1129,9876,25151" proto=udp
  #litp ${SCFW}/fw_nfsudp create firewalls-def name="011 nfsudp" dport="662,875,2020,2049,4001,4045" proto=udp
  litp ${SCFW}/fw_netbackup create firewalls-def name="012 netbackup" dport="13724,1556,13783,13722" proto=tcp
  litp ${SCFW}/fw_SSO1 create firewalls-def name="039 SSO1" dport="1699,4445,10389" proto=tcp
  litp ${SCFW}/fw_logstash_tcp create firewalls-def name="040 logstash" dport="9200" proto=tcp
  litp ${SCFW}/fw_logstash_forward_tcp create firewalls-def name="041 logstash forward tcp" dport="2514" proto=tcp
  litp ${SCFW}/fw_icmp create firewalls-def name="100 icmp" provider=iptables proto=icmp
  litp ${SCFW}/fw_icmpv6 create firewalls-def name="100 icmpv6" provider=ip6tables proto="ipv6-icmp"
  litp ${SCFW}/fw_igmp create firewalls-def name="100 igmp" proto=igmp
  litp ${SCFW}/fw_dns_tcp create firewalls-def name="101 Nameservices tcp" dport="53" proto=tcp
  litp ${SCFW}/fw_dns_udp create firewalls-def name="102 Nameservices udp" dport="53" proto=udp
  litp ${SCFW}/fw_streaming create firewalls-def name="120 Streaming TCP external" dport="1233,1234" proto=tcp
  # FM notification
  local fmpm0_addr=$(litp /inventory/deployment1/alias_FMPMServ_su_0 show | awk -F\" '/ip:/ {print $2}')
  local fmpm1_addr=$(litp /inventory/deployment1/alias_FMPMServ_su_1 show | awk -F\" '/ip:/ {print $2}')
  litp ${SCFW}/fw_oss_notif_FMPMServ_su_0 create firewalls-def name="40 OSS NOTIF FMPMServ 0" dport="15554" provider=iptables proto="tcp" destination="$fmpm0_addr"
  litp ${SCFW}/fw_oss_notif_FMPMServ_su_1 create firewalls-def name="40 OSS NOTIF FMPMServ 1" dport="15554" provider=iptables proto="tcp" destination="$fmpm1_addr"
  # IPv6 global link if implemented
  local sc1_ipv6_global=$(litp /inventory/deployment1/alias_sc1_ipv6 show | awk -F\" '/ip:/ {print $2}')
  echo $sc1_ipv6_global | grep "[a-fA-F0-9]\{0,4\}[:]" >/dev/null
  if (( $? == 0 )); then
    litp ${SCFW}/fw_sc1_ipv6_global create firewalls-def name="48 sc1 ipv6 global link" source="$sc1_ipv6_global" provider=ip6tables proto=all
  fi
  local sc2_ipv6_global=$(litp /inventory/deployment1/alias_sc2_ipv6 show | awk -F\" '/ip:/ {print $2}')
  echo $sc2_ipv6_global | grep "[a-fA-F0-9]\{0,4\}[:]" >/dev/null
  if (( $? == 0 )); then
    litp ${SCFW}/fw_sc2_ipv6_global create firewalls-def name="48 sc2 ipv6 global link" source="$sc2_ipv6_global" provider=ip6tables proto=all
  fi
  # IPv6 local link
  local sc1_ipv6_local=$(ssh sc-1 "ifconfig bond0" | sed -n 's/\s\+inet6 addr:\s\(.\+\)\/.\+Scope:Link/\1/p')
  local sc2_ipv6_local=$(ssh sc-2 "ifconfig bond0" | sed -n 's/\s\+inet6 addr:\s\(.\+\)\/.\+Scope:Link/\1/p')
  litp ${SCFW}/fw_sc1_ipv6_local create firewalls-def name="48 sc1 ipv6 local link" source="$sc1_ipv6_local" provider=ip6tables proto=all
  litp ${SCFW}/fw_sc2_ipv6_local create firewalls-def name="48 sc2 ipv6 local link" source="$sc2_ipv6_local" provider=ip6tables proto=all
  # Alias IPv4 addresses
  declare -a alias_list=('/inventory/deployment1/alias_FMPMServ_su_0' \
    '/inventory/deployment1/alias_FMPMServ_su_1' \
    '/inventory/deployment1/alias_MSFM_su_0' \
    '/inventory/deployment1/alias_MSFM_su_1' \
    '/inventory/deployment1/alias_MSPM0_su_0' \
    '/inventory/deployment1/alias_MSPM0_su_1' \
    '/inventory/deployment1/alias_MSPM1_su_0' \
    '/inventory/deployment1/alias_MSPM1_su_1' \
    '/inventory/deployment1/alias_MedCore_su_0' \
    '/inventory/deployment1/alias_MedCore_su_1' \
    '/inventory/deployment1/alias_UIServ_su_0' \
    '/inventory/deployment1/alias_UIServ_su_1' \
    '/inventory/deployment1/alias_httpd' \
    '/inventory/deployment1/alias_logstash' \
    '/inventory/deployment1/alias_ms' \
    '/inventory/deployment1/alias_nasconsole' \
    '/inventory/deployment1/alias_sc1' \
    '/inventory/deployment1/alias_sc2' \
    '/inventory/deployment1/cluster1/sc1/alias_SSO_su_0' \
    '/inventory/deployment1/cluster1/sc2/alias_SSO_su_1' \
    '/inventory/deployment1/cluster1/sc1/alias_ctx_farm_master_host' \
    '/inventory/deployment1/cluster1/sc1/alias_masterservice' \
    '/inventory/deployment1/cluster1/sc1/alias_ossrc_ldap_1' \
    '/inventory/deployment1/cluster1/sc1/alias_ossrc_ldap_2')
  for i in ${alias_list[@]}; do
    source_addr=$(litp $i show | awk -F\" '/ip:/ {print $2}')
    rule_name=$(echo $i | sed 's/.\+alias_\(.\+\)/\1/')
    rule_comment=$(echo $rule_name | sed 's/_/ /g')
    litp ${SCFW}/fw_${rule_name} create firewalls-def name="42 $rule_comment" source=${source_addr} provider=iptables proto=all
  done
  # Backup and storage IPv4 addresses
  local sc1_backup_ip=$(litp /inventory/deployment1/cluster1/sc1/ip_backup show | awk -F\" '/address:/ {print $2}') 
  local sc1_storage_ip=$(litp /inventory/deployment1/cluster1/sc1/ip_storage show | awk -F\" '/address:/ {print $2}')
  local sc2_backup_ip=$(litp /inventory/deployment1/cluster1/sc2/ip_backup show | awk -F\" '/address:/ {print $2}') 
  local sc2_storage_ip=$(litp /inventory/deployment1/cluster1/sc2/ip_storage show | awk -F\" '/address:/ {print $2}')
  local ms_backup_ip=$(litp /inventory/deployment1/ms1/ip_backup show | awk -F\" '/address:/ {print $2}')
  local ms_storage_ip=$(litp /inventory/deployment1/ms1/ip_storage show | awk -F\" '/address:/ {print $2}')
  litp ${SCFW}/fw_sc1_backup create firewalls-def name="42 sc1 backup ip" source=${sc1_backup_ip} provider=iptables proto=all
  litp ${SCFW}/fw_sc1_storage create firewalls-def name="42 sc1 storage ip" source=${sc1_storage_ip} provider=iptables proto=all
  litp ${SCFW}/fw_sc2_backup create firewalls-def name="42 sc2 backup ip" source=${sc2_backup_ip} provider=iptables proto=all
  litp ${SCFW}/fw_sc2_storage create firewalls-def name="42 sc2 storage ip" source=${sc2_storage_ip} provider=iptables proto=all
  litp ${SCFW}/fw_ms_backup create firewalls-def name="42 ms backup ip" source=${ms_backup_ip} provider=iptables proto=all
  litp ${SCFW}/fw_ms_storage create firewalls-def name="42 ms storage ip" source=${ms_storage_ip} provider=iptables proto=all
  # SFS VIPs
  local vip_n=0
  for i in $(litp /inventory/deployment1/ show -r | grep data_vip | sort -u | awk -F\" '{print $2}'); do
    (( vip_n++ ))
    litp ${SCFW}/fw_sfs_vip_${vip_n} create firewalls-def name="42 sfs vip ${vip_n}" source=${i} provider=iptables proto=all
  done
  log "Stopping puppet agent on peer nodes"
  ssh sc-1 "service puppet stop" >/dev/null
  ssh sc-2 "service puppet stop" >/dev/null
  log "Flushing iptables on peer nodes"
  ssh sc-1 "ip6tables --flush; iptables --flush"
  ssh sc-2 "ip6tables --flush; iptables --flush"
  log "Applying inventory changes"
  /usr/bin/litp /definition materialise
  /usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os configure
  /usr/bin/litp /cfgmgr apply scope=/inventory/deployment1/cluster1/sc1/control_1/os
  /usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os configure
  /usr/bin/litp /cfgmgr apply scope=/inventory/deployment1/cluster1/sc2/control_2/os
  log "Starting puppet on peer nodes"
  ssh sc-1 "service puppet start" >/dev/null
  ssh sc-2 "service puppet start" >/dev/null
  log "Waiting for changes to get applied. Please wait..."
  sleep 40
  while :; do
    sc1_appl=$(/usr/bin/litp /inventory/deployment1/cluster1/sc1/control_1/os show -rp | grep fw_ | grep -v Applied | wc -l)
	sc2_appl=$(/usr/bin/litp /inventory/deployment1/cluster1/sc2/control_2/os show -rp | grep fw_ | grep -v Applied | wc -l)
    if (( $sc1_appl == 0 && $sc2_appl == 0 )); then
      log "Firewall rules applied successfully to peer nodes"
      break
    else
      log "SC-1 still applying $sc1_appl firewall rules. SC-2 still applying $sc2_appl firewall rules. Please wait..."
      sleep 30	  
    fi	
  done
}

### Function: update_jee_container() ###
# 
# Removing  jgroups-udp-mcast_* and jgroups_mping_mcast_* from jee config
# Adding enm.udp.mcast_* to command-line-option
# TORD-947 & TORD-966 (set Xms and Xmx parameters)
# Arguments:
#       None
# Return Values:
#       None
update_jee_container()
{
  declare -a jeeItem
  local rc
  local enm_udp_mcast_addr
  local enm_udp_mcast_port
  log "Updating definition with a new jee container configuration"
  for item in $(/usr/bin/litp /definition/jee_containers show -l); do
    rc=$(/usr/bin/litp /definition/jee_containers/$item/instance show | perl -e 'while (<>) { $a="$1" if /jgroups-udp-mcast-addr:\s+\"(.+)\"/; $b="$1" if /jgroups-udp-mcast-port:\s+\"(.+)\"/ } print "$a $b"')
    jeeItem=(${rc})
    enm_udp_mcast_addr=${jeeItem[0]}
    enm_udp_mcast_port=${jeeItem[1]}
    if [[ $enm_udp_mcast_addr != "" && $enm_udp_mcast_port != "" ]]; then 	
      /usr/bin/litp /definition/jee_containers/${item}/instance update ^jgroups-udp-mcast-addr ^jgroups-udp-mcast-port >/dev/null
      /usr/bin/litp /definition/jee_containers/${item}/instance/ENM_Multicast_ADDR create jee-property-def property="-Denm.udp.mcast_addr" value=$enm_udp_mcast_addr >/dev/null
      /usr/bin/litp /definition/jee_containers/${item}/instance/ENM_Multicast_PORT create jee-property-def property="-Denm.udp.mcast_port" value=$enm_udp_mcast_port >/dev/null	
    else
      log "$item already updated"	
    fi
    if [[ ${item} != "jee_SSO" ]]; then
      /usr/bin/litp /definition/jee_containers/${item}/instance update Xmx="6144M" Xms="6144M" >/dev/null
    fi
  done
  log "Removing jgroups-udp-mcast_* and jgroups_mping-mcast_* entries from inventory"
  for item in $(/usr/bin/litp / find --resource jee.jee_container.JEEContainer); do
    /usr/bin/litp $item update ^jgroups-udp-mcast-addr ^jgroups-udp-mcast-port >/dev/null	
  done
  /usr/bin/litp /definition materialise 
}

#################
### Main Body ###
#################

get_absolute_path

_cfl_=${SCRIPT_HOME}/bin/common_functions.lib
if [ ! -f ${_cfl_} ] ; then
  ${ECHO} "Cant find ${_cfl_}"
  exit 1
else
  . ${_cfl_}
fi

if [ ! -d "${LOGDIR}" ]; then
    ${MKDIR} ${LOGDIR}
fi

if [ -f "${LOGFILE}" ]; then
  _mod_date_=`${DATE} +%Y%m%d_%H%M%S -r "${LOGFILE}"`
  NEWLOG="${LOGFILE%.log}-${_mod_date_}.log"
  if [ -f "${NEWLOG}" ]; then  # in case ntp has reset time and log exists
    NEWLOG="${LOGFILE%.log}-${_mod_date_}_1.log"
  fi
  ${MV} "${LOGFILE}" "${NEWLOG}"
fi

update_jee_container | ${TEE} -a ${LOGFILE}
update_fw_rules | ${TEE} -a ${LOGFILE}
delete_dump_files | ${TEE} -a ${LOGFILE}
delete_old_jboss_logs | ${TEE} -a ${LOGFILE}
campaign_etf_generators | ${TEE} -a ${LOGFILE}
logrotate_updates | ${TEE} -a ${LOGFILE}
create_ms_dumps_dir | ${TEE} -a ${LOGFILE}
create_hcdumps | ${TEE} -a ${LOGFILE}
if [ "${PIPESTATUS[0]}" -gt 0 ]; then
  exit 1;
fi
wait_for_hcdumps_apply | ${TEE} -a ${LOGFILE}
remove_dirs_from_sc_common | ${TEE} -a ${LOGFILE}

#####################################################################################
#workaround for datapath/pmmedcom shared file /opt/ericsson/datapaths.xml
#needed only to upgrade from 1.0.17 to 1.0.19 iso x.88 or latest
#####################################################################################
datapath_fix
#####################################################################################
#workaround for HORNETQ
#needed only to upgrade from 1.0.17 to 1.0.19 iso x.88 or latest
#####################################################################################
hornetq_fix
#####################################################################################
config_core_dump | ${TEE} -a ${LOGFILE}

exit 0