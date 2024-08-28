#!/bin/bash
# script to migrate sso_0 volume on sc1 to sso_1
# should be executed from 1.0.19 to 1.0.19/x upgrades only

ECHO=/bin/echo
MKDIR=/bin/mkdir
SSH=/usr/bin/ssh
GREP=/bin/grep
AWK=/bin/awk
RM=/bin/rm
MV=/bin/mv
TEE=/usr/bin/tee
CP=/bin/cp
SED=/bin/sed
UMOUNT=/bin/umount
MOUNT=/bin/mount
LVDISPLAY=/sbin/lvdisplay
LVRENAME=/sbin/lvrename
LITP=/usr/bin/litp
DIRNAME=/usr/bin/dirname
DATE=/bin/date

sso_1=SSO_su_1_jee_instance
sso_0=SSO_su_0_jee_instance
path=/var/ericsson
lvm="/inventory/deployment1/cluster1/sc2/control_2/os/lvm/"
fstab=/etc/fstab
amf_SSO="safSu=SSO_App-SuType-1,safSg=SSO,safApp=SSO_App"
SC="sc-2"

LOGDIR="/var/log/torinst"
LOGFILE="${LOGDIR}/migrate_SSO.log"


get_absolute_path()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/../ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
}

### Function: _date ###
#
# Get a date string for trace messages
#
# Arguments:
#       None
# Return Values:
#       None
_date()
{
  ${DATE} '+%Y-%b-%d_%H.%M.%S'
}


_trace()
{
  local _type_=$1
  local _tracemsg_=$2
  local _date_=`_date`
  local _msg_="${_date_} - ${_type_} : ${_tracemsg_}"
  if [ ${LOGFILE} ] ; then
    ${ECHO} "${_msg_}" | ${TEE} -a ${LOGFILE}
  else
    ${ECHO} "${_msg_}"
  fi
}

### Function: error ###
#
# Error to log.
#
# Arguments:
#       $1 - Error to trace
# Return Values:
#       None
error()
{
  _trace "ERROR" "${*}"
}

### Function: log ###
#
# Log a message.
#
# Arguments:
#       $1 - Message to log
# Return Values:
#       None
log()
{
  _trace "LOG" "${*}"
}

### Function: warning ###
#
# Log a warning.
#
# Arguments:
#       $1 - Message to log
# Return Values:
#       None
warning()
{
  _trace "WARNING" "${*}"
}


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

log "log into ${LOGFILE} has started"

result_=$($SSH $SC :)
if [ $? -ne 0 ]
then
	error "There is no SSH connectivity to $SC node"
	error "Please re-run script again after fixing problem:"
	error ${result_}
	exit 1
fi

result_=$($SSH $SC "ls $path/$sso_1| $GREP lost+found" 2>&1)
if [ $? -eq 0 ]
then
        result_second=$($SSH $SC "mount |$GREP $path/$sso_0" 2>&1)
        if [ $? -ne 0 ]
        then
        #       $ECHO "$path/$sso_0 already converted into $path/$sso_1, exiting"
                $ECHO "Script has already been successfully executed, exiting..."
                exit 0
        fi
fi


for k in $path $path/$sso_1 $fstab $path/$sso_1/data
do
	result_=$($SSH $SC "ls $k" 2>&1)
	if [ $? -ne 0 ]
	then
		error "Please check setup on $SC as $k can't be find on it."
		error $result_
		exit 1
	fi
	log "$k successfully tested on $SC"
done

result_=$($SSH $SC "ls $path/$sso_0| $GREP lost+found")
if [ $? -ne 0 ]
then
	warning "$path/$sso_0 is not mount point."
	warning "Possible SSO was already migrated, exiting"
	exit 1
fi

result_=$($SSH $SC "amf-state su| grep ${amf_SSO} -A4| $GREP saAmfSUPresenceState|$GREP =INSTANTIATED" 2>&1)
if [ $? -eq 0 ]
then
	result_lock=$($SSH $SC "amf-adm lock ${amf_SSO}" 2>&1)
	if [ $? -ne 0 ]
	then
		error "Failed to lock ${amf_SSO} on $SC"
		error "Please correct problem and re-run script:"
		error ${result_lock}
		exit 1
	fi
	log "${amf_SSO} successfully locked on $SC"
else
	result_again=$($SSH $SC "amf-state su| grep ${amf_SSO} -A4| $GREP saAmfSUPresenceState|$GREP UNINSTANTIATED" 2>&1)
	if [ $? -ne 0 ]
	then
		error "Please verify amf component SSO_App-SuType-1 status and re-run script."
		error "Current status is not INSTANTIATED or UNINSTANTIATED"
		exit 1
	fi
fi


result_=$($SSH $SC "$CP -prfP $path/$sso_1/data $path/$sso_0/" 2>&1)
if [ $? -ne 0 ]
then
	error "Failed to copy $path/$sso_1/* to $path/$sso_0 on $SC"
	error $result_
	exit 1
fi
log "$path/$sso_1/* successfully copied to $path/$sso_0 on $SC"

result_=$($SSH $SC "$LVDISPLAY /dev/mapper/vg_app-lv_$sso_1" 2>&1)
if [ $? -eq 0 ]
then
	error "/dev/mapper/vg_app-lv_$sso_1 already exist on $SC"
	error $result_
	exit 1
fi

result_=$($SSH $SC "$LVDISPLAY /dev/mapper/vg_app-lv_$sso_0" 2>&1)
if [ $? -ne 0 ]
then
	error "/dev/mapper/vg_app-lv_$sso_0 does NOT exist on $SC"
	error "Please check your setup and run script again!"
	error $result_
	exit 1
fi


result_=$($SSH $SC "$CP -pf $fstab $fstab.orig" 2>&1)
if [ $? -ne 0 ]
then
	error "Failed to copy $fstab to $fstab.orig on $SC"
	error $result_
	exit 1
else 
	log "$fstab successfully copied to $fstab.orig for backup."
fi

result_=$($SSH $SC "$RM -rf $path/$sso_1/*" 2>&1)
if [ $? -ne 0 ]
then
	error "Failed to clean $path/$sso_1/ to prepare it for re-mounting on $SC"
	error $result_
	exit 1
else 
	log "$path/$sso_1 successfully cleaned."
fi

result_=$($SSH $SC "$UMOUNT $path/$sso_0" 2>&1)
if [ $? -ne 0 ]
then
	error "Failed to umount $path/$sso_0 to prepare it for re-mounting on $SC."
	error $result_
	exit 1
else 
	log "$path/$sso_1 successfully unmounted on $SC."
fi

result_=$($SSH $SC "$LVRENAME /dev/vg_app/lv_$sso_0 /dev/vg_app/lv_$sso_1" 2>&1)
if [ $? -ne 0 ]
then
	error "Failed to rename /dev/vg_app/lv_$sso_0 to /dev/vg_app/lv_$sso_1 on $SC."
	error $result_
	exit 1
else 
	log "/dev/vg_app/lv_$sso_0 successfully renamed to /dev/vg_app/lv_$sso_1 on $SC."
fi

result_=$($SSH $SC "$SED -i 's/SSO_su_0_jee_instance/SSO_su_1_jee_instance/g' $fstab" 2>&1)
if [ $? -ne 0 ]
then
	error "Failed to update $fstab on $SC"
	error $result_
	exit 1
else 
	log "$fstab successfully updated."
	log "$sso_0 was changed to $sso_1"
fi

result_=$($SSH $SC "$MOUNT $path/$sso_1" 2>&1)
if [ $? -ne 0 ]
then
	result_again=$($ECHO $result_|$GREP "already mounted")
	if [ $? -ne 0 ]
	then
		error "Failed to mount $path/$sso_1 on $SC."
		error "Please mount it manually"
		error $result_
		exit 1
	else 
		log "$path/$sso_1 already mounted on $SC"
	fi
else 
	log "$path/$sso_1 successfully mounted on $SC."
fi

result_=$($SSH $SC "amf-adm unlock ${amf_SSO}" 2>&1)
if [ $? -ne 0 ]
then
	result_unlock=$($ECHO ${result_}|$GREP "command timed out")
	if [ $? -ne 0 ]
	then
		error "Some significant problem with AMF"
		error "Not possible to continue execution"
		error "Please correct problem with AMF:"
		error $result_
		error "To run this script again please rollback on $SC /etc/fstab from /etc/fstab.orig"
		error "delete if /dev/vg_app/lv_$sso_0 exists on $SC"
		error "unmount /dev/vg_app/lv_$sso_1"
		error "rename LV /dev/vg_app/lv_$sso_1 to /dev/vg_app/lv_$sso_0 on $SC"
		error "remount /dev/vg_app/lv_$sso_0"
		error "copy back data from $path/$sso_0/data $path/$sso_1/"
		error "re-run script again"
		exit 1
	else
		log "sleep next 60 seconds to get ${amf_SSO} back..."
		sleep 60
		for (( c=1; c<6; c++ ))
		do
		result_=$($SSH $SC "amf-state su| grep ${amf_SSO} -A4| $GREP saAmfSUPresenceState|$GREP =INSTANTIATED" 2>&1)
		if [ $? -ne 0 ] && [ $c -ne 5 ]
		then
			log "sleep next 60 seconds to get ${amf_SSO} back..."
			sleep 60
			continue
		elif [ $c -eq 5 ]
		then
			log "${amf_SSO} is INSTANTIATED now"
			break
		fi
		error "Some significant problem with AMF"
		error "Not possible to continue execution"
		error "After waiting, ${amf_SSO} still not INSTANTIATED"
		error "To run this script again please rollback on $SC /etc/fstab from /etc/fstab.orig"
		error "delete if /dev/vg_app/lv_$sso_0 exists on $SC"
		error "unmount /dev/vg_app/lv_$sso_1"
		error "rename LV /dev/vg_app/lv_$sso_1 to /dev/vg_app/lv_$sso_0 on $SC"
		error "remount /dev/vg_app/lv_$sso_0"
		error "copy back data from $path/$sso_0/data $path/$sso_1/"
		error "re-run script again"
		exit 1
		done
	fi
fi
log "${amf_SSO} successfully unlocked on $SC"
log "==========================="
log "Executing LITP update part."
log "==========================="

result_=$($LITP /inventory/deployment1/cluster1/sc2/control_2/os/lvm/lv_SSO_su_1_jee_instance show 2>&1)
if [ $? -eq 0 ]
then
	log "/inventory/deployment1/cluster1/sc2/control_2/os/lvm/lv_SSO_su_1_jee_instance already exist, skipping creation..."
else
	$LITP /inventory/deployment1/cluster1/sc2/control_2/os/lvm/lv_SSO_su_1_jee_instance create log-vol vg="vg_app" size="1G" snap_percent="0"	
fi

result_=$($LITP /inventory/deployment1/cluster1/sc2/control_2/os/lvm/fs_SSO_su_1_jee_instance show 2>&1)
if [ $? -eq 0 ]
then
	log "/inventory/deployment1/cluster1/sc2/control_2/os/lvm/fs_SSO_su_1_jee_instance already exist, skipping creation..."
else
	$LITP /inventory/deployment1/cluster1/sc2/control_2/os/lvm/fs_SSO_su_1_jee_instance create file-sys lv="lv_SSO_su_1_jee_instance" mount_point="/var/ericsson/SSO_su_1_jee_instance"	
fi

$LITP /inventory/deployment1/cluster1/sc2/control_2/os/lvm/fs_SSO_su_0_jee_instance delete
$LITP /inventory/deployment1/cluster1/sc2/control_2/os/lvm/lv_SSO_su_0_jee_instance delete



log "litp configure executing..."
result_=$($LITP /inventory configure 2>&1)
if [ $? -ne 0 ]
then
	error "$LITP /inventory configure failed to execute."
	error "Please check error messages and correct problem before re-running script"
	error $result_
	exit 1
fi

log "litp validate executing..."
result_=$($LITP /inventory validate 2>&1)
if [ $? -ne 0 ]
then
	error "$LITP /inventory validate failed to execute."
	error "Please check error messages and correct problem before re-running script"
	error $result_
	exit 1
fi

log "litp apply scope executing..."
result_=$($LITP /cfgmgr/ apply scope=/inventory 2>&1)
if [ $? -ne 0 ]
then
	error "$LITP /inventory apply scope failed to execute."
	error "Please check error messages and correct problem before re-running script"
	error $result_
	exit 1
fi
#CLEAN UP
result_=$($SSH $SC "$LVDISPLAY /dev/mapper/vg_app-lv_$sso_0" 2>&1)
if [ $? -eq 0 ]
then
	log "/dev/mapper/vg_app-lv_$sso_0 exist on $SC and need to be removed"
	$SSH $SC "lvremove -f /dev/vg_app/lv_SSO_su_0_jee_instance"
fi
$SSH $SC "rm -rf /var/ericsson/$sso_0"