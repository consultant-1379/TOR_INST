#!/bin/bash
# ********************************************************************
# Ericsson LMI                                    SCRIPT
# ********************************************************************
#
# (c) Ericsson LMI 2013 - All rights reserved.
#
# The copyright to the computer program(s) herein is the property
# of Ericsson LMI. The programs may be used
# and/or copied only with the written permission from Ericsson LMI or in accordance with
# the terms and conditions stipulated in the agreement/contract under which the program(s)
# have been supplied.
#
# ********************************************************************
# Name    : healthcheck.sh
# Date    : 15/07/2013
# Revision: R1A01
# Purpose : TOR healthcheck script
#
# Usage   : N/A
#
# ********************************************************************

AWK=/bin/awk
DATE=/bin/date
DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
GREP=/bin/grep
LITP=/usr/bin/litp
PERL=/usr/bin/perl
TEE=/usr/bin/tee
TPUT=/usr/bin/tput

NMS_UTIL=/opt/ericsson/com.ericsson.nms.utilities

get_absolute_path()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
  . ${SCRIPT_HOME}/../../bin/common_functions.lib
}


# sc1 & sc2 hostnames
_sc1_=$(${LITP} /inventory/deployment1/cluster1/sc1/control_1/os/system show | ${GREP} hostname | ${AWK} -F\" '{print $2}')
_sc2_=$(${LITP} /inventory/deployment1/cluster1/sc2/control_2/os/system show | ${GREP} hostname | ${AWK} -F\" '{print $2}')

## time stamp
_now_=$(${DATE} +"%Y.%m.%d-%H.%M%S")
_logfile_="/var/log/torinst/healthcheck_log-$_now_.log"

_bold_=$(${TPUT} bold)
_normal_=$(${TPUT} sgr0)


get_absolute_path


${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
${ECHO} "** Network Connectivity Check **" | ${TEE} -a ${_logfile_}
${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
${PERL} ${SCRIPT_HOME}/networkCheck.pl ${_sc1_} ${_sc2_} | ${TEE} ${_logfile_}

${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
${ECHO} "** HACS Healthcheck **" | ${TEE} -a ${_logfile_}
${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
${BASH} ${SCRIPT_HOME}/haCheck.sh | ${TEE} -a ${_logfile_}

${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
${ECHO} "** Core MW Basic Healthcheck **" | ${TEE} -a ${_logfile_}
${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
${BASH} ${SCRIPT_HOME}/cmwCheck.sh | ${TEE} -a ${_logfile_}

${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
${ECHO} "** JBoss Health Check **" | ${TEE} -a ${_logfile_}
${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
${BASH} ${SCRIPT_HOME}/hc_jboss.bsh | ${TEE} -a ${_logfile_}
if [ ${PIPESTATUS[0]} -ne 0 ] ; then
  ${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
  ${ECHO} "Errors reported from JBoss health check" | ${TEE} -a ${_logfile_}
  ${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
fi

# Heatlhchecks for LOGSTASH/UI/SSO
ssh $_sc1_ "ls ${NMS_UTIL}/ui_all_hc.sh" > /dev/null 2>&1
if [ $? -eq 0 ]
  then
  ${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
  ${ECHO} "** UI Services Healthcheck **" | ${TEE} -a ${_logfile_}
  ${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
  ssh $_sc1_ "cd ${NMS_UTIL};${BASH} ui_all_hc.sh" 2>&1 | ${TEE} -a ${_logfile_}
fi

ssh $_sc1_ "ls ${NMS_UTIL}/logstash_all_hc.sh" > /dev/null 2>&1
if [ $? -eq 0 ]
  then
  ${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
  ${ECHO} "** Logstash Services Healthcheck **" | ${TEE} -a ${_logfile_}
  ${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
  _active_=`/opt/ericsson/torinst/bin/amf_status.bsh | grep logstash | awk '{print $6}'`
  ssh $_active_ "cd ${NMS_UTIL};${BASH} logstash_all_hc.sh" 2>&1 | ${TEE} -a ${_logfile_}
fi

${ECHO} "${_bold_}" | ${TEE} -a ${_logfile_}
${ECHO} "** End of healtcheck **" | ${TEE} -a ${_logfile_}
${ECHO} "Information logged in ${_logfile_}" 2>&1 | ${TEE} -a ${_logfile_}
${ECHO} "${_normal_}" | ${TEE} -a ${_logfile_}
exit 0
