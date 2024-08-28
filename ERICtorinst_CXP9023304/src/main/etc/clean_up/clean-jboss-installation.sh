#!/bin/bash


DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
RM=/bin/rm
SSH=/usr/bin/ssh

### Function: get_absolute_path ###
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
}

setup_env
_controllers_=( `get_controller_list` )
if [ $? -ne 0 ] ; then
  error "${_controllers_}"
  exit 1
fi
for _node_ in ${_controllers_[*]} ; do
	${SSH} ${_node_} "${RM} -rvf /home/jboss && ${RM} -rvf /var/log/jboss"
done