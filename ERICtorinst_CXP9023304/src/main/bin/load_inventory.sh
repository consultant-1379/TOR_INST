#!/bin/bash
DIRNAME=/usr/bin/dirname
ECHO=/bin/echo
GETOPT=/usr/bin/getopt

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
}

usage()
{
  ${ECHO} "$0 --site_data <site_data> --sw_base <tor_iso>"
    ${ECHO} " Where <site_data> is the TOR Site Specific Data file"
    ${ECHO} " Where <tor_iso> is the TOR Sw ISO or a directory containing the TOR Sw Packages"
}

if [ $# -eq 0 ] ; then
  usage
  exit 2
fi
ARGS=`${GETOPT} -o "s:d:b" -l "site_data:,sw_base:,base_only" -n "load_inventory.sh" -- "$@"`
if [ $? -ne 0 ] ; then
  usage
  exit 2
fi
eval set -- ${ARGS}

#by default it is multiblade installation
SINGLE_BLADE=0

BASE_DEF_ONLY=""
while true ; do
  case "${1}" in
    -d | --site_data)
      _tor_site_data_="${2}"
      shift 2;;
    -s | --sw_base)
      _tor_sw_base_="${2}"
      shift 2;;
    -b | --base_only)
      BASE_DEF_ONLY="-b"
      shift;;
    --)
      shift; break;;
  esac
done

if [ ! ${_tor_site_data_} ] ; then
  usage
  exit 2
fi
if [ ! ${_tor_sw_base_} ] ; then
  usage
  exit 2
fi
if [ ! -f ${_tor_site_data_} ] ; then
  ${ECHO} "${_tor_site_data_} not found"
  exit 2
fi

get_absolute_path

_cfl_=${SCRIPT_HOME}/bin/common_functions.lib
if [ ! -f ${_cfl_} ] ; then
  ${ECHO} "Cant find ${_cfl_}"
  exit 1
else
  . ${_cfl_}
fi

dos2unix ${_tor_site_data_}
if [ $? -ne 0 ] ; then
  ${ECHO} "Failed to run dos2unix on ${_tor_site_data_}"
  exit 1
fi


#We update the values in the /opt/ericsson/torinst/etc/inventory_common_env.sh
#TODO: import the values directly from the SiteEngineering file and get rid
#   of the processing of template
SSI="${SCRIPT_HOME}/etc/inventory_common_env.sh"

INVENTORY_TEMPLATE="${SCRIPT_HOME}/etc/inventory_common_env.sh.template"

${ECHO} "Processing inventory_common_env.sh.template"
${SCRIPT_HOME}/bin/createSiteSpecificInventory.pl \
  ${_tor_site_data_} \
  ${INVENTORY_TEMPLATE} \
  ${SSI}
_rc_=$?
if [ ${_rc_} -ne 0 ] ; then
  exit ${_rc_}
fi
if [ ! -f ${SSI} ] ; then
  exit 2
fi



#TODO: get rid of template processing, source the settings and call correct
# inventory script
SSI="${SCRIPT_HOME}/bin/generated_inventory.bsh"


INVENTORY_TEMPLATE="${SCRIPT_HOME}/etc/tor_multi_blade_inventory_template.sh"

#check if we are installing the single blade
grep -q -s  VM_mac_pool_start  ${_tor_site_data_} && SINGLE_BLADE=1

if [[ ${SINGLE_BLADE} == 1 ]]; then
    INVENTORY_TEMPLATE="${SCRIPT_HOME}/etc/tor_single_blade_inventory_template.sh"
fi


${ECHO} "Generating site specific inventory script ..."
${SCRIPT_HOME}/bin/createSiteSpecificInventory.pl \
  ${_tor_site_data_} \
  ${INVENTORY_TEMPLATE} \
  ${SSI}
_rc_=$?
if [ ${_rc_} -ne 0 ] ; then
  exit ${_rc_}
fi
if [ ! -f ${SSI} ] ; then
  exit 2
fi


if [[ ${SINGLE_BLADE} == 1 ]]; then
    SSBM="${SCRIPT_HOME}/bin/tor_single_blade_boot_mgr.sh"
    ${ECHO} "Generating site specific boot manager ..."
    ${SCRIPT_HOME}/bin/createSiteSpecificInventory.pl \
        ${_tor_site_data_} \
        ${SCRIPT_HOME}/etc/tor_single_blade_bootmgr_template.sh \
        ${SSBM}
    _rc_=$?
    if [ ${_rc_} -ne 0 ] ; then
        exit ${_rc_}
    fi
    if [ ! -f ${SSBM} ] ; then
        exit 2
    fi
    chmod +x ${SSBM}
fi

${ECHO} "Running site specific ${SSI} ..."
bash ${SSI} --sw_base ${_tor_sw_base_} ${BASE_DEF_ONLY} --site_data ${_tor_site_data_}
_rc_=$?
if [ ${_rc_} -ne 0 ] ; then
  exit ${_rc_}
fi
