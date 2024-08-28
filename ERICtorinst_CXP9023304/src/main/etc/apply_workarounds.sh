#!/bin/bash

AWK=/bin/awk
CHCON=/usr/bin/chcon
CP=/bin/cp
DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
GREP=/bin/grep
RM=/bin/rm
SCP=/usr/bin/scp
SED=/bin/sed
SERVICE=/sbin/service
SSH=/usr/bin/ssh

### Function: setup_env ###
#
# Determine absolute path to software
#
# Arguments:
#   none
# Return Values:
#   none
setup_env()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/../ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
  if [ ! -f ${SCRIPT_HOME}/bin/common_functions.lib ] ; then
    ${ECHO} "${SCRIPT_HOME}/bin/common_functions.lib not found"
    exit 1
  fi
  . ${SCRIPT_HOME}/bin/common_functions.lib
  if [ $? -ne 0 ] ; then
    ${ECHO} "Failed to import ${SCRIPT_HOME}/bin/common_functions.lib"
  fi
}

check_exit()
{
	if [ $1 -ne 0 ] ; then
	  if [ $2 ] ; then
		  error "$2"
		fi
		exit $1
	fi
}

log()
{
	${ECHO} "$*"
}

update_rsyslog_startorder()
{
  local _host1_=$1
  _result_=$(${SSH} ${_host1_} "${GREP} \"chkconfig: 2345 12 88\" /etc/init.d/rsyslog")
  declare -i _start_priority_=$(${ECHO} ${_result_} | ${AWK} '{print $4}')
  if (( $_start_priority_ == 12 )); then
    ${ECHO} "The rsyslog startup priority will be changed from S12 to S26"
    ${SSH} ${_host1_} "${CP} /etc/init.d/rsyslog /var/tmp/rsyslog.orig"
    check_exit $? "Failed to copy rsyslog LSB script"
    ${ECHO} "A copy of /etc/init.d/rsyslog is stored under /var/tmp directory"
    ${SSH} ${_host1_} "${SED} -i 's/chkconfig: 2345 12 88/chkconfig: 2345 26 88/' /etc/init.d/rsyslog"
    check_exit $? "Failed to update start level in rsyslog LSB script"
    ${SSH} ${_host1_} "[[ -f /etc/rc2.d/S12rsyslog ]] && ${RM} /etc/rc2.d/S12rsyslog"
    check_exit $? "Failed to remove old rsyslog LSB rc2.d links"
    ${SSH} ${_host1_} "[[ -f /etc/rc3.d/S12rsyslog ]] && ${RM} /etc/rc3.d/S12rsyslog"
    check_exit $? "Failed to remove old rsyslog LSB rc3.d links"
    ${ECHO} "Restarting rsyslog service on ${_host1_}, it may take some time..."
    ${SSH} ${_host1_} "${SERVICE} rsyslog restart"
    check_exit $? "Failed to restart rsyslog on ${_host1_}"
  else
    ${ECHO} "rsyslog startup priority already set to S12"
  fi
}

update_saf_timeouts()
{
log "Implementing timeout changes in SAF"
ssh sc-1 'immcfg -a smfRebootTimeout=2100000000000 smfConfig=1,safApp=safSmfService'
ssh sc-1 'immcfg -a smfAdminOpTimeout=1800000000000 smfConfig=1,safApp=safSmfService'
ssh sc-1 'amf-adm si-swap safSi=SC-2N,safApp=OpenSAF'
ssh sc-2 'immcfg -a smfRebootTimeout=2100000000000 smfConfig=1,safApp=safSmfService'
ssh sc-2 'immcfg -a smfAdminOpTimeout=1800000000000 smfConfig=1,safApp=safSmfService'
log "Timeout values updated successfully!"
}

# ********************************************************************
#
#   Main body of program
#
# ********************************************************************
setup_env

_controllers_=( `get_controller_list` )
check_exit $? "${_controllers_}"

_host1_=`get_property_value /inventory/deployment1/cluster1/sc1/control_1/os/ip "address"`
check_exit $? "${_host1_}"
update_rsyslog_startorder "${_host1_}"
check_exit $? "Failed to update rsyslog start order"
update_saf_timeouts

