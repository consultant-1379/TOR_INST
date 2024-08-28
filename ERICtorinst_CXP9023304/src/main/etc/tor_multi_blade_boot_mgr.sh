#!/bin/bash

CP=/bin/cp
COBBLER=/usr/bin/cobbler
CREATEREPO=/usr/bin/createrepo
DATE=/bin/date
DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
GETOPT=/usr/bin/getopt
GREP=/bin/grep
LITP=/usr/bin/litp
MKDIR=/bin/mkdir
TEE=/usr/bin/tee
UMOUNT=/bin/umount


STEP=0
LOGDIR="/var/log/torinst"

if [ ! -d "${LOGDIR}" ]; then
    ${MKDIR} -p ${LOGDIR}
fi
LOGFILE="${LOGDIR}/landscape_bootmgr.log"
if [ -f "${LOGFILE}" ]; then
  _moddate_=`${DATE} +%Y%m%d_%H%M%S -r "${LOGFILE}"`
  _prevlog_="${LOGFILE%.log}-${_moddate_}.log"
  if [ -f "${_prevlog_}" ]; then  # in case ntp has reset time and log exists
    _prevlog_="${LOGFILE%.log}-${_moddate_}_1.log"
  fi
  ${CP} "${LOGFILE}" "${_prevlog_}"
fi

> "${LOGFILE}"

function litp() {
  STEP=$(( ${STEP} + 1 ))
  printf "Step %03d: litp %s\n" ${STEP} "$*" | tee -a "${LOGFILE}"
  local _result_=`command ${LITP} "$@" | ${TEE} -a "${LOGFILE}"`
  if ${ECHO} "${_result_}" | ${GREP} -i error; then
    exit 1;
  fi
}

# Function to show elapsed time in human readable format (minutes:seconds)
function time_elapsed() {
	local secs=$1
	local mins=$(( ${secs} / 60 ))
	local secs=$(( ${secs} % 60 ))
	printf "Time elapsed: %02d:%02d\r" ${mins} ${secs}
}

#
# A function that checks if cobbler is ready with a profile and distro
# before starting to create systems
#
function wait_for_cobbler() {
	local c=0 # attempt timer
	local TEMPO=1 # interval between checks

	${ECHO}
	${ECHO} "Waiting for cobbler distro/profile to be loaded..."

	time_elapsed $(( ${c} * ${TEMPO} ))
	while sleep ${TEMPO}; do
		let c++
		time_elapsed $(( ${c} * ${TEMPO} ))

		_output_=`${COBBLER} distro list`
		if [[ -n "${_output_}" ]]; then
			_output_=`${COBBLER} profile list`
			if [[ -n "${_output_}" ]]; then
				break
			fi
		fi
	done
	${ECHO}
	${ECHO} "Cobbler is now ready with a distro & profile."
}

# A function that checks if dhcp is ready for distro import
# before starting to import distro
#
function wait_for_dhcp() {
    c=0 # attempt timer
    TEMPO=1 # interval between checks

    echo
    echo "Waiting for dhcp to be configured..."

    time_elapsed $(( $c * $TEMPO ))
    while sleep $TEMPO; do
        let c++
        time_elapsed $(( $c * $TEMPO ))
        pidof dhcpd > /dev/null
        if [ $? -eq 0 ]; then
            break
        fi
    done
    echo
    echo "Cobbler is now ready for distro import."
}

litp /bootmgr update server_url="http://127.0.0.1/cobbler_api" username="cobbler" password="litpc0b6lEr" boot_network="TORservices"

# Adding a distribution and a profile to cobbler
litp /bootmgr/distro1 create boot-distro arch='x86_64' breed='redhat' path='/profiles/node-iso/' name='node-iso-x86_64'

#
# We must wait a few seconds for profile and distro to be imported to cobbler
#
wait_for_cobbler

# Add profile to landscape
litp /bootmgr/distro1/profile1 create boot-profile name='node-iso-x86_64' distro='node-iso-x86_64' kopts='' kopts_post='console=ttyS0,115200'

#
# Now that Cobbler has imported the distro, we can create systems
#
litp /bootmgr boot scope=/inventory

${ECHO} "Check 'cobbler list' to see if cluster installation has been kickstarted."
exit 0

