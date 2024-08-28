#!/bin/bash

CP=/bin/cp
DATE=/bin/date
DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
GETOPT=/usr/bin/getopt
GREP=/bin/grep
IPTABLES=/sbin/iptables
IP6TABLES=/sbin/ip6tables
LITP=/usr/bin/litp
MKDIR=/bin/mkdir
TEE=/usr/bin/tee

MSFW=/definition/os/osms
SCFW=/definition/os/ossc




get_absolute_path()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/../ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
}

update_ui_modcluster_rule()
{
local _address_
local i=0
for _su_ in `${LITP} /inventory/deployment1/cluster1/UIServ/ find --name instance` ; do
	${_address_} = get_address _su_
	create_fwrule ${SCFW}/fw_modclusster_su_${i} "039 UImodclusterSU ${i++}" "8009" "tcp" none none "${_address_}"
	done
}

update_apache_modcluster_rule()
{
local _apache_path_
local _apache_address_

${_apache_path_} = ${LITP} /inventory find --name httpd_service
 ${LITP} ${_apache_path_} show > /dev/null 2>&1
  if [ $? -ne 0 ] ; then
    error "Path for HTTPD service not found!"
    exit ${EXIT_ERROR}
  fi
${_apache_address_}= get_address  ${_apache_path_}
create_fwrule ${SCFW}/fw_modclusster_apache "039 UImodclusterApache" "8009" "tcp" none none "${_apache_address_}"
}

# main body of program
get_absolute_path

_cfl_=${SCRIPT_HOME}/bin/common_functions.lib
if [ ! -f ${_cfl_} ] ; then
  ${ECHO} "Cant find ${_cfl_}"
  exit 1
else
  . ${_cfl_}
fi

update_ui_modcluster_rule
update_apache_modcluster_rule

${IPTABLES} -F
${IP6TABLES} -F


exit 0
