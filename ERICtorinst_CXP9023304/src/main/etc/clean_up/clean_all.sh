#!/bin/bash

COBBLER=/usr/bin/cobbler
ECHO=/bin/echo
KILLALL=/usr/bin/killall
IPTABLES=/sbin/iptables
IP6TABLES=/sbin/ip6tables
PUPPETCA=/usr/sbin/puppetca
RM=/bin/rm
SERVICE=/sbin/service
UMOUNT=/bin/umount

start_service()
{
  local _service_=$1
  ${SERVICE} ${_service_} start
  if [ $? -ne 0 ] ; then
    ${ECHO} "Service ${_service_} failed to start"
    exit 1
  fi
}

stop_service()
{
  local _service_=$1
  ${SERVICE} ${_service_} stop
  if [ $? -ne 0 ] ; then
    ${ECHO} "Service ${_service_} failed to stop"
   # exit 1
  fi
}
#
# Check to see if ddc is already running
#
check_stop_service()
{
        local _service_=$1
        local _status_=${SERVICE} ${_service_} status | sed -n '/stopped/!p'
	local _running_==${SERVICE} ${_service_} status | sed -n '/running/!p'

        if [ -z "${_status_}" ]; then
                ${ECHO} "Service ${_service_} already stopped, nothing to do"
	elif [ -z "${_running_}" ]; then
		${SERVICE} ${_service_} stop
        else
                ${SERVICE} ${_service_} stop
       fi
}


check_start_service()
{
        local _service_=$1
        local _status_=${SERVICE} ${_service_} status | sed -n '/started/!p'
	local _running_==${SERVICE} ${_service_} status | sed -n '/running/!p'

        if [ -z "${_status_}" ]; then
                ${ECHO} "Service ${_service_} has already stopped, nothing to do"
	elif [ -z "${_running_}" ]; then
                 ${ECHO} "Service ${_service_} already running, nothing to do"
        else
                ${SERVICE} ${_service_} start
       fi
}


#
# Clean up cobbler
#
for _sysname_ in `${COBBLER} system list`; do
	${COBBLER} system remove --name "${_sysname_}"
done

for _distroname_ in `${COBBLER} distro list`; do
	${COBBLER} distro remove --name "${_distroname_}"
done

#
# Stop all necessary services
#
check_stop_service ddc
check_stop_service cobblerd
check_stop_service dhcpd
stop_service puppetmaster
stop_service puppet
stop_service landscaped
check_stop_service ddc

# un-mount all shares or extra disks
${UMOUNT} -a -t nfs

# Kill landscape if service didn't stop gracefully.
${KILLALL} landscape_service.py

#
# Remove current puppet certificate for MS1. New ones will be created in the
# next attempt
#

${PUPPETCA} --clean ms1

#
# Clean up all files created by last attempt
#
${RM} -rf /var/lib/puppet/ssl/*
${RM} -f /root/.ssh/known_hosts
${RM} -rf /var/puppet/inventory/*
${RM} -rf /opt/ericsson/nms/litp/etc/puppet/manifests/inventory/*
${RM} -rf /var/NASService/locks/*
${RM} -rf /exports/cluster/*
${RM} -rf /var/lib/cobbler/snippets/*ks*.snippet
${RM} -rf /etc/sysconfig/iptables
${RM} -rf /etc/sysconfig/ip6tables
${IPTABLES} -F
${IP6TABLES} -F

# Clean up. Remove any stored landscape config ...
${RM} -rf /var/lib/landscape/*

#
# Bring back up all stopped services
#

start_service landscaped
start_service puppet
start_service puppetmaster
check_start_service dhcpd
check_start_service cobblerd

# Restart network
stop_service network
start_service network

# Sync cobbler
${COBBLER} sync

# That should be it

exit 0

