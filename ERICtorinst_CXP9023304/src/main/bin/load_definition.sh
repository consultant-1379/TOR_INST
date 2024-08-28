#!/bin/bash

AWK=/bin/awk
BASENAME=/bin/basename
CP=/bin/cp
CREATEREPO=/usr/bin/createrepo
DATE=/bin/date
DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
FIND=/bin/find
GETOPT=/usr/bin/getopt
GREP=/bin/grep
LITP=/usr/bin/litp
LS=/bin/ls
MKDIR=/bin/mkdir
MOUNT=/bin/mount
MV=/bin/mv
PYTHON=/usr/bin/python
RM=/bin/rm
RSYNC=/usr/bin/rsync
TEE=/usr/bin/tee
UMOUNT=/bin/umount

trap "cleanup; exit $?" EXIT


### Function: get_absolute_path ###
#
# Determine absolute path to software
#
# Arguments:
#   none
# Return Values:
#   none
get_absolute_path()
{
  _dir_=`${DIRNAME} $0`
  SCRIPT_HOME=`cd ${_dir_}/../ 2>/dev/null && pwd || ${ECHO} ${_dir_}`
  . ${SCRIPT_HOME}/bin/common_functions.lib
}


### Function: setup_env ###
#
# Set up environment variables for script.
#
# Arguments:
#   none
# Return Values:
#   none
setup_env()
{
  get_absolute_path
  STEP=0
  MOUNT_DIR="/var/tmp/tor_iso.$$"

  TOR_DEF_BASE="${SCRIPT_HOME}/etc/tor_multi_blade_base_definition.xml"
  XML_MERGER="${SCRIPT_HOME}/lib/xml_utils/xml_merge.py"
  XML_VERSIONER="${SCRIPT_HOME}/lib/xml_utils/pkg_auto_version.py"
  XML_VERIFIER="${SCRIPT_HOME}/lib/xml_utils/definition_pkg_check.py"
  export PYTHONPATH=${PYTHONPATH}:${SCRIPT_HOME}/lib

  if [[ ${SINGLE_BLADE} == 1 ]]; then
      TOR_DEF_BASE="${SCRIPT_HOME}/etc/tor_single_blade_base_definition_template.xml"
      if [ ! -f ${TOR_DEF_BASE} ] ; then
          exit 2
      fi
  fi

  LOGDIR="/var/log/torinst"
  if [ ! -d "${LOGDIR}" ]; then
      ${MKDIR} ${LOGDIR}
  fi
  LOGFILE="${LOGDIR}/tor_definition.log"
  if [ -f "${LOGFILE}" ]; then
    _mod_date_=`${DATE} +%Y%m%d_%H%M%S -r "${LOGFILE}"`
    NEWLOG="${LOGFILE%.log}-${_mod_date_}.log"
    if [ -f "${NEWLOG}" ]; then  # in case ntp has reset time and log exists
      NEWLOG="${LOGFILE%.log}-${_mod_date_}_1.log"
    fi
    ${MV} "${LOGFILE}" "${NEWLOG}"
  fi
}

cleanup()
{
  if [ -d ${MOUNT_DIR} ] ; then
    ${UMOUNT} ${MOUNT_DIR} > /dev/null 2>&1
    ${RM} -rf ${MOUNT_DIR} > /dev/null 2>&1
  fi
}

function litp() {
  STEP=$(( ${STEP} + 1 ))
  printf "Step %03d: litp %s\n" ${STEP} "$*" | ${TEE} -a "${LOGFILE}"
  command ${LITP} "$@" 2>&1 | ${TEE} -a "${LOGFILE}"
  if [ "${PIPESTATUS[0]}" -ne 0 ] ; then
    exit 1;
  fi
}

usage()
{
  ${ECHO} "$0 --single --sw_base <tor_iso>"
  ${ECHO} " Where <tor_iso> is the TOR Sw ISO or a directory containing the TOR Sw Packages"
  ${ECHO} " --single specifies singlenode installation"
}


# TODO : Replace this with a litp import call
import_tor_sw()
{
  local _iso_=$1
  local _umount_=0
  local _mount_
  if [ -d ${_iso_} ] ; then
    _mount_=${_iso_}
  else
    _umount_=1
    _mount_=/mnt/`${BASENAME} ${_iso_}`
    mount_iso ${_iso_} ${_mount_}
  fi
  local _tor_vrepo_=`get_iso_pkg_dir ${_mount_}`
  if [ -d ${_tor_vrepo_} ] ; then
    ${RM} -rf ${_tor_vrepo_}
  fi
  # Import the iso contents using the litp import command
  import_iso ${_mount_}
  if [ ${_umount_} -eq 1 ] ; then
    umount_iso ${_mount_} "delete"
  fi
}

create_sw_repo_entries()
{
  local _iso_=$1
  local _umount_=0
  if [ -d ${_iso_} ] ; then
    _mount_=${_iso_}
  else
    _umount_=1
    _mount_=/mnt/`${BASENAME} ${_iso_}`
    mount_iso ${_iso_} ${_mount_}
  fi
  local _tor_vrepo_
  _tor_vrepo_=`get_iso_pkg_dir ${_mount_}`
  if [ $? -ne 0 ] ; then
    error "${_tor_vrepo_}"
    exit 1
  fi
  local _vname_=`get_repo_name ${_tor_vrepo_}`
  if [ ${_umount_} -eq 1 ] ; then
    umount_iso ${_mount_} "delete"
  fi
}

merge_and_version()
{
  if [ ${NO_MERGE} -eq 0 ] ; then
    local _iso_=$1
    local _umount_=0
    if [ -d ${_iso_} ] ; then
      _mount_=${_iso_}
    else
      _umount_=1
      _mount_=/mnt/`${BASENAME} ${_iso_}`
      mount_iso ${_iso_} ${_mount_}
    fi
    local _tor_vrepo_=`get_iso_pkg_dir ${_mount_}`
    local _reponame_=`get_repo_name ${_tor_vrepo_}`
    ${ECHO} "Using [${_mount_}] as TOR Sw Base" >> ${LOGFILE}
    ${ECHO} "Merging snippets ..."
    _merged_def_="${SCRIPT_HOME}/etc/merged_tor_definition.xml"
    _merge_results_=`${PYTHON} ${XML_MERGER} -d ${TOR_DEF_BASE} \
      -s ${SCRIPT_HOME}/etc/xml_snippets \
      --auto_version -o ${_merged_def_} 2>&1`
    _rc_=$?
    ${ECHO} "${_merge_results_}" >> ${LOGFILE}
    if [ ${_rc_} -ne 0 ] ; then
      ${ECHO} "${_merge_results_}"
      ${ECHO} "XML merge failed." | ${TEE} -a ${LOGFILE}
      exit ${_rc_}
    fi
    ${ECHO} "Merge completed OK, results in ${_merged_def_}" | ${TEE} -a ${LOGFILE}
    ${ECHO} "Versioning ${_merged_def_}" | ${TEE} -a ${LOGFILE}
    _versioned_def_="${SCRIPT_HOME}/etc/versioned_tor_definition.xml"
    _tor_vrepo_=`get_iso_pkg_dir ${_mount_}`
    _tor_repo_name_=`get_repo_name ${_tor_vrepo_}`
    _version_results_=`${PYTHON} ${XML_VERSIONER} -d ${_merged_def_} \
      -s ${_tor_vrepo_} -o ${_versioned_def_} --repo ${_tor_repo_name_}  2>&1`
    _rc_=$?
    ${ECHO} "${_version_results_}" >> ${LOGFILE}
    if [ ${_rc_} -ne 0 ] ; then
      ${ECHO} "${_version_results_}"
      ${ECHO} "XML Veringing failed." | ${TEE} -a ${LOGFILE}
      exit ${_rc_}
    fi
    ${ECHO} "Versioning completed OK, results in ${_versioned_def_}" | ${TEE} -a ${LOGFILE}

    ${ECHO} "Verifying pkg versions in versioned file ${_versioned_def_}" | ${TEE} -a ${LOGFILE}
    _check_result_=`${PYTHON} ${XML_VERIFIER} -d ${_versioned_def_} -s ${_tor_vrepo_} -e 2>&1`
    _rc_=$?
    ${ECHO} "${_check_result_}" >> ${LOGFILE}
    if [ ${_rc_} -ne 0 ] ; then
      ${ECHO} "${_check_result_}"
      exit ${_rc_}
    else
      ${ECHO} "Pkg version check was OK" | ${TEE} -a ${LOGFILE}
    fi
    if [ ${_umount_} -eq 1 ] ; then
      umount_iso ${_mount_} "delete"
    fi
  else
    _versioned_def_=${TOR_DEF_BASE}
  fi
}

# ********************************************************************
#
#   Main body of program
#
# ********************************************************************
NO_MERGE=0
CHECK_ONLY=0
SINGLE_BLADE=0

if [ $# -eq 0 ] ; then
  usage
  exit 2
fi

ARGS=`${GETOPT} -o "s:cbg" -l "sw_base:,check_only,base_only,single_blade" -n "load_definition.sh" -- "$@"`

if [ $? -ne 0 ] ; then
  usage
  exit 2
fi
eval set -- ${ARGS}

while true ; do
  case "${1}" in
    -s | --sw_base)
      _tor_sw_base_="${2}"
      shift 2;;
    -c | --check_only)
      CHECK_ONLY=1
      shift;;
    -b | --base_only)
      NO_MERGE=1
      shift;;
    -g | --single_blade)
      SINGLE_BLADE=1
      shift;;
    --)
      shift; break;;
  esac
done


setup_env


if [ ${NO_MERGE} -eq 0 ] ; then
  if [ ! ${_tor_sw_base_} ] ; then
    usage
    exit 2
  fi
fi


import_tor_sw ${_tor_sw_base_}
merge_and_version ${_tor_sw_base_}

if [ ${CHECK_ONLY} -eq 1 ] ; then
  ${ECHO} "Checking only, not loading." | ${TEE} -a ${LOGFILE}
  exit 0
fi

${ECHO} "Loading defintion ..." | ${TEE} -a ${LOGFILE}
litp / load ${_versioned_def_}
if [ $? -ne 0 ] ; then
  exit 1
fi

#We need to import the TOR software before materializing (or after the SC nodes are upt)
#if not you will see error like:
#Jun 18 11:22:16 err ms1 litp.nms.ericsson.com: litp.LitpSoftwareMgr: 21640: Error rebuilding yum cache on /inventory/deployment1/cluster1/sc1: LitpNode.execute()Node has no management IP address
#Jun 18 11:22:16 err ms1 litp.nms.ericsson.com: litp.LitpSoftwareMgr: 21640: Error rebuilding yum cache on /inventory/deployment1/cluster1/sc2: LitpNode.execute()Node has no management IP address
#Jun 18 11:22:16 err ms1 litp.nms.ericsson.com: litp.LitpSoftwareMgr: 21640: Error rebuilding yum cache on /inventory/deployment1/ms1: LitpNode.execute()Node has no management IP address

#we need to pass the mount point of the TOR software

litp /definition materialise

create_sw_repo_entries ${_tor_sw_base_}
