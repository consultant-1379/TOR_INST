#!/bin/bash

CP=/bin/cp
DATE=/bin/date
ECHO=/bin/echo
DIRNAME=/usr/bin/dirname
LITP=/usr/bin/litp
LOGGER=/usr/bin/logger
MKDIR=/bin/mkdir
MV=/bin/mv
SSH=/usr/bin/ssh
TEE=/usr/bin/tee

STEP=0
LOGDIR="/var/log/torinst"
LOGFILE="${LOGDIR}/campaign_execution.log"


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

setup_env()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/../ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
  if [ -f ${SCRIPT_HOME}/bin/common_functions.lib ] ; then
    source ${SCRIPT_HOME}/bin/common_functions.lib
  else
    ${ECHO} "${SCRIPT_HOME}/bin/common_functions.lib not found!"
    exit 3
  fi
}

create_cmw_backup()
{
  log "Creating CMW backups ..." | ${TEE} -a ${LOGFILE}
  _controllers_=(`get_controller_list`)
  if [ $? -ne 0 ] ; then
    error "Failed to get a list of control nodes" | ${TEE} -a ${LOGFILE}
    error "${_controllers_}" | ${TEE} -a ${LOGFILE}
    exit 1
  fi
  _system_=`${LITP} ${_controllers_[0]} find --name system 2>&1`
  if [ $? -ne 0 ] ; then
    error "Failed to find any systems for ${_controllers_[0]}" | ${TEE} -a ${LOGFILE}
    error "${_system_}" | ${TEE} -a ${LOGFILE}
    exit 1
  fi
  _ctrl_host_=`get_property_value ${_system_} "hostname"`
  _rc_=$?
  if [ ${_rc_} -ne 0 ] ; then
    error "${_ctrl_host_}" | ${TEE} -a ${LOGFILE}
    exit ${_rc_}
  fi
  if [ "${_ctrl_host_}" == "" ] ; then
    error "Could not find a control host in landscape for ${_system_}" | ${TEE} -a ${LOGFILE}
    exit 4
  fi
  log "Using control node ${_ctrl_host_} to create CMW backup ..." | ${TEE} -a ${LOGFILE}
  local _backup_name_="backup.before.campaign_generator_execute.`${DATE} +%Y%m%d_%H%M%S`"
  log "Creating 3 CMW Backups ${_backup_name_} ..." | ${TEE} -a ${LOGFILE}
  for (( c=0; c<=3; c++ ))
  do
  	sleep 5
  	${SSH} -o StrictHostKeyChecking=no  ${_ctrl_host_} "cmw-partial-backup-create ${_backup_name_}_${c} 2>&1" | ${TEE} -a ${LOGFILE}
  	_rc_=${PIPESTATUS[0]}
  	if [ ${_rc_} -ne 0 ] ; then
	    error "Creation of CMW backup ${_backup_name_}_$c failed, check the CMW is running correctly on the nodes." | ${TEE} -a ${LOGFILE}
	    exit 1
  	fi
  	log "CMW backup ${_backup_name_}_$c successfully created on ${_ctrl_host_}." | ${TEE} -a ${LOGFILE}
  done
}

campaign_generate()
{
  log "Generating installation campaigns ...."
  litp /inventory/deployment1/cluster1/cmw_cluster_config/etf_generator generate_etfs
  litp /inventory/deployment1/cluster1/cmw_cluster_config/etf_generator verify
  litp /inventory/deployment1/cluster1/cmw_cluster_config/campaign_generator generate
}

campaign_execute()
{
  create_cmw_backup
  litp /inventory/deployment1/cluster1/cmw_cluster_config/campaign_generator execute
  cmw_configuration_persist
  update_monitoring
  log "All installation campaigns have completed."
}
#Torinst Logger
${LOGGER} -t "tor_inst" "Starting TOR installation campaigns at `${DATE} +%Y-%m-%d_%H:%M:%S`"
setup_env
campaign_generate | ${TEE} -a ${LOGFILE}
_rc_=${PIPESTATUS[0]}
if [ ${_rc_} -ne 0 ] ; then
  exit 1
fi
campaign_execute | ${TEE} -a ${LOGFILE}
_rc_=${PIPESTATUS[0]}
if [ ${_rc_} -ne 0 ] ; then
  exit 1
fi
${LOGGER} -t "tor_inst" "Completed TOR installation campaigns at `${DATE} +%Y-%m-%d_%H:%M:%S`"
exit 0
