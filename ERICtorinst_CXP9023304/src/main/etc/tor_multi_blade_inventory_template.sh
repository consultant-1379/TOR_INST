#!/bin/bash
# ********************************************************************
# Ericsson LMI                                    SCRIPT
# ********************************************************************
#
# (c) Ericsson LMI 2013 - All rights reserved.
#
# The copyright to the computer program(s) herein is the property
# of Ericsson LMI. The programs may be used
# and/or copied only with the written permission from Ericsson LMI or in accordance with the terms and conditions stipulated
# in the agreement/contract under which the program(s) have been
# supplied.
#
# ********************************************************************
# Name    : tor_multi_blade_inventory_template.sh
# Date    : 15/03/13
# Revision: v1.0.11
# Purpose : Inventory template for a multi-blade installation of TOR including TOR software.
# Designed for use with TOR SiteEngineering XLS and createSiteSpecificInventory.pl script.
#
# Usage   : N/A
#
# ********************************************************************
ACTION="create firewalls-def"
AWK=/bin/awk
CAT=/bin/cat
DIRNAME=/usr/bin/dirname
CP=/bin/cp
DATE=/bin/date
ECHO=/bin/echo
GETOPT=/usr/bin/getopt
GREP=/bin/grep
LITP=/usr/bin/litp
LOGGER=/usr/bin/logger
MKDIR=/bin/mkdir
SCFW=/definition/os/ossc
SED=/bin/sed
RM=/bin/rm
MANAGEMENT_PASSWORD='shroot'

HOSTS_FILE=/etc/hosts


#Check if the installatin directory variable is set
#if not set it to default value
if [[ ${_TORINST_BASE_DIR_} == "" ]]; then
    _TORINST_BASE_DIR_=/opt/ericsson/torinst
fi

#source the settings and functions
. "${_TORINST_BASE_DIR_}/etc/inventory_common_env.sh"

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


BASE_DEF_ONLY=""
while true ; do
  case "${1}" in
    -d | --site_data)
      SSD="${2}"
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

if [ ! ${SSD} ] ; then
  usage
  exit 2
fi
if [ ! ${_tor_sw_base_} ] ; then
  usage
  exit 2
fi
if [ ! -f ${SSD} ] ; then
  ${ECHO} "${SSD} not found"
  exit 2
fi



# Check there are no undefined value in the script
_check_=`${CAT} $0 | ${GREP} "%%" | ${GREP} -v grep`
if [ $? -eq 0 ] ; then
  ${ECHO} "Undefined values still present, is the Site Engineering the correct version?"
  ${ECHO} "${_check_}"
  exit 1
fi

get_absolute_path

_cfl_=${SCRIPT_HOME}/bin/common_functions.lib
if [ ! -f ${_cfl_} ] ; then
  ${ECHO} "Cant find ${_cfl_}"
  exit 1
else
  . ${_cfl_}
fi

TOR_NETMASK=$(cidr2netmask $TOR_SERVICES_SUBNET)
if [ $? -ne 0 ] ; then
    ${ECHO} "Unable to calculate netmask from TORservices_subnet value in SED ($TOR_SERVICES_SUBNET)" 
    exit 1
fi

STEP=0
LOGDIR="/var/log/torinst"
LOGFILE="${LOGDIR}/landscape_inventory.log"
function litp() {
  STEP=$(( ${STEP} + 1 ))
  printf "Step %03d: litp %s\n" ${STEP} "$*" | tee -a "${LOGFILE}"
  command litp "$@" 2>&1 | tee -a "${LOGFILE}"
  if [ "${PIPESTATUS[0]}" -gt 0 ]; then
    exit 1;
  fi
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
  ${CP} "${LOGFILE}" "${NEWLOG}"
fi

> "${LOGFILE}"



#------------------------------------------------------------------------------------
#Torinst Logger
${LOGGER} -t "tor_inst" "Started /inventory modifications at `${DATE} +%Y-%m-%d_%H:%M:%S`"




# --------------------------------------------
# INVENTORY STARTS HERE
# --------------------------------------------

#---------------------------------------------------
# REPOSITORIES
#----------------------------------------------------
#update nodes with information about TOR sw repos
update_tor_sw_repo ${_tor_sw_base_}

#must be updated to function taking patch/url as an argument
litp /inventory/deployment1/ms1/repository/patch62_v1 create repository name="patch62_v1" url="file:///var/www/html/patches/rhel_1_2_3"
litp /inventory/deployment1/cluster1/sc1/repository/patch62_v1 create repository name="patch62_v1" url="http://MS1/patches/rhel_1_2_3"
litp /inventory/deployment1/cluster1/sc2/repository/patch62_v1 create repository name="patch62_v1" url="http://MS1/patches/rhel_1_2_3"

litp /definition/rd_rsyslog_server/rsyslog_server/ update rlCentralHost="%%node1_hostname%%"
litp /definition/rd_rsyslog_server/ materialise

litp /definition/rd_rsyslog_client/rsyslog_client/ update rlCentralHost="%%node1_hostname%%"
litp /definition/rd_rsyslog_client/ materialise

litp /definition/alias_controller materialise
# ---------------------------------------------
# ADD THE PHYSICAL SERVERS
# ---------------------------------------------
discover_blades_from_ilo

litp /inventory/deployment1/cluster1 update HA_manager=CMW

# ---------------------------------------------
# NETWORKING
# ---------------------------------------------
update_hostname_network


# Load NetGraphs
VLANID_STORAGE="%%VLAN_ID_storage%%"
VLANID_BACKUP="%%VLAN_ID_backup%%"
${CP} -p /opt/ericsson/torinst/etc/NetGraphSC.xml /opt/ericsson/torinst/etc/NetGraphSC_local.xml 
${SED} -i "s/vlanidstorage/$VLANID_STORAGE/g;s/vlanidbackup/$VLANID_BACKUP/g" /opt/ericsson/torinst/etc/NetGraphSC_local.xml
litp /inventory/deployment1/cluster1/sc1 load /opt/ericsson/torinst/etc/NetGraphSC_local.xml
litp /inventory/deployment1/cluster1/sc2 load /opt/ericsson/torinst/etc/NetGraphSC_local.xml
litp /inventory/deployment1/ms1 load /opt/ericsson/torinst/etc/NetGraphMS.xml

# Create IP address pools for TOR Services, Backup and Storage stuff.
create_ip_pools

# Allocate IPs to LMS
# Set a primary IP for the MS and also set the default gateway for bond0
litp /inventory/deployment1/${TOR_SERVICE_POOL}/lms_ip create ip-address \
  subnet=${TOR_SERVICES_SUBNET} address=%%LMS_IP%% gateway=${TOR_SERVICES_GATEWAY} net_name=${TOR_SERVICES_NETWORK}
litp /inventory/deployment1/${TOR_SERVICE_POOL}/lms_ip enable
litp /inventory/deployment1/ms1/ms_node/os/ip update pool=${TOR_SERVICE_POOL} net_name=${TOR_SERVICES_NETWORK}
litp /inventory/deployment1/ms1/ms_node/os/ip allocate
litp /inventory/deployment1/alias_ms create svc-alias ip=%%LMS_IP%% aliases=ms1
# allocate an IP from the storage network
litp /inventory/deployment1/${TOR_STORAGE_POOL}/lms_ip_storage create ip-address address=%%LMS_IP_storage%% \
    subnet=${TOR_STORAGE_SUBNET} net_name=${TOR_STORAGE_NETWORK}
litp /inventory/deployment1/${TOR_STORAGE_POOL}/lms_ip_storage enable
litp /inventory/deployment1/ms1/ms_node/ip_storage create ip-address pool=${TOR_STORAGE_POOL} net_name=${TOR_STORAGE_NETWORK}
litp /inventory/deployment1/ms1/ms_node/ip_storage allocate


# allocate an IP from the backup network
ms1_allocate_backup_network_ip

#Allocate IPs to control nodes
sc_allocate_ip_addresses

#update Hyperic network
update_hyperic_network

# Update boot network
litp /inventory/deployment1/ms1/ms_node/ms_boot/bootservice update boot_network=${TOR_SERVICES_NETWORK}

litp /inventory/deployment1/ms1/ms_node/os/system/linuxnetconfig create linux-net-conf
litp /inventory/deployment1/cluster1/sc1/control_1/os/system/linuxnetconfig create linux-net-conf
litp /inventory/deployment1/cluster1/sc2/control_2/os/system/linuxnetconfig create linux-net-conf

# DNS resolv.conf
update_resolv_conf /inventory/deployment1/site_resolver %%nameserverA%% %%nameserverB%% %%dns_domainName%%
update_resolv_conf /inventory/deployment1/ms1/ms_node/os/node_resolver %%nameserverA%% %%nameserverB%% %%dns_domainName%%
update_resolv_conf /inventory/deployment1/cluster1/sc1/control_1/os/node_resolver %%nameserverA%% %%nameserverB%% %%dns_domainName%%
update_resolv_conf /inventory/deployment1/cluster1/sc2/control_2/os/node_resolver %%nameserverA%% %%nameserverB%% %%dns_domainName%%

###### End of networking #####################


#------------------------------------
#Firewall update for tor addresses in definition
#------------------------------------
litp ${SCFW}/fw_oss_notif_FMPMServ_su_0 ${ACTION} name="001 OSS NOTIF FMPMServ 0" dport="15554" provider=iptables proto="tcp" destination="%%FMPMServ_su_0_ipaddress%%"
litp ${SCFW}/fw_oss_notif_FMPMServ_su_1 ${ACTION} name="001 OSS NOTIF FMPMServ 1" dport="15554" provider=iptables proto="tcp" destination="%%FMPMServ_su_1_ipaddress%%"

litp ${SCFW}/fw_FMPMServ_su_0 ${ACTION} name="42 FMPMServ su 0" source="%%FMPMServ_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_FMPMServ_su_1 ${ACTION} name="42 FMPMServ su 1" source="%%FMPMServ_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MSFM_su_0 ${ACTION} name="42 MSFM su 0" source="%%MSFM_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MSFM_su_1 ${ACTION} name="42 MSFM su 1" source="%%MSFM_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MSPM0_su_0 ${ACTION} name="42 MSPM0 su 0" source="%%MSPM0_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MSPM0_su_1 ${ACTION} name="42 MSPM0 su 1" source="%%MSPM0_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MSPM1_su_0 ${ACTION} name="42 MSPM1 su 0" source="%%MSPM1_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MSPM1_su_1 ${ACTION} name="42 MSPM1 su 1" source="%%MSPM1_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MedCore_su_0 ${ACTION} name="42 MedCore su 0" source="%%MedCore_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_MedCore_su_1 ${ACTION} name="42 MedCore su 1" source="%%MedCore_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_UIServ_su_0 ${ACTION} name="42 UIServ su 0" source="%%UIServ_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_UIServ_su_1 ${ACTION} name="42 UIServ su 1" source="%%UIServ_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_httpd ${ACTION} name="42 httpd" source="%%httpd_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_logstash ${ACTION} name="42 logstash" source="%%logstash_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_ms ${ACTION} name="42 ms" source="%%LMS_IP%%" provider=iptables proto=all
litp ${SCFW}/fw_nasconsole ${ACTION} name="42 nasconsole" source="%%sfs_console_IP%%" provider=iptables proto=all
litp ${SCFW}/fw_sc1 ${ACTION} name="42 sc1" source="%%node1_IP%%" provider=iptables proto=all
litp ${SCFW}/fw_sc2 ${ACTION} name="42 sc2" source="%%node2_IP%%" provider=iptables proto=all
litp ${SCFW}/fw_SSO_su_0 ${ACTION} name="42 SSO su 0" source="%%SSO_su_0_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_SSO_su_1 ${ACTION} name="42 SSO su 1" source="%%SSO_su_1_ipaddress%%" provider=iptables proto=all
litp ${SCFW}/fw_ctx_farm_master_host ${ACTION} name="42 ctx farm master host" source="%%alias_ctx_farm_master_host%%" provider=iptables proto=all
litp ${SCFW}/fw_masterservice ${ACTION} name="42 masterservice" source="%%alias_masterservice%%" provider=iptables proto=all
litp ${SCFW}/fw_ossrc_ldap_1 ${ACTION} name="42 ossrc ldap 1" source="%%alias_ossrc_ldap_1%%" provider=iptables proto=all
litp ${SCFW}/fw_ossrc_ldap_2 ${ACTION} name="42 ossrc ldap 2" source="%%alias_ossrc_ldap_2%%" provider=iptables proto=all
litp ${SCFW}/fw_sc1_backup ${ACTION} name="42 sc1 backup ip" source="%%node1_IP_backup%%" provider=iptables proto=all
litp ${SCFW}/fw_sc1_storage ${ACTION} name="42 sc1 storage ip" source="%%node1_IP_storage%%" provider=iptables proto=all
litp ${SCFW}/fw_sc2_backup ${ACTION} name="42 sc2 backup ip" source="%%node2_IP_backup%%" provider=iptables proto=all
litp ${SCFW}/fw_sc2_storage ${ACTION} name="42 sc2 storage ip" source="%%node2_IP_storage%%" provider=iptables proto=all
litp ${SCFW}/fw_ms_backup ${ACTION} name="42 ms backup ip" source="%%LMS_IP_backup%%" provider=iptables proto=all
litp ${SCFW}/fw_ms_storage ${ACTION} name="42 ms storage ip" source="%%LMS_IP_storage%%" provider=iptables proto=all
# SFS VIPs
sfs_vip_1="%%nas_vip_seg1%%"
sfs_vip_2="%%nas_vip_clog%%"
sfs_vip_3="%%nas_vip_tor_1%%"
litp ${SCFW}/fw_sfs_vip_1 create firewalls-def name="42 sfs vip 1" source=${sfs_vip_1} provider=iptables proto=all
litp ${SCFW}/fw_sfs_vip_2 create firewalls-def name="42 sfs vip 2" source=${sfs_vip_2} provider=iptables proto=all
litp ${SCFW}/fw_sfs_vip_3 create firewalls-def name="42 sfs vip 3" source=${sfs_vip_3} provider=iptables proto=all

# Global link rules for SC-1 & SC-2
sc1IPv6Global="%%node1_IPv6%%"
${ECHO} ${sc1IPv6Global} | ${GREP} "[a-fA-F0-9]\{0,4\}[:]" >/dev/null
if (( $? == 0 )); then 
  litp ${SCFW}/fw_sc1_ipv6_global ${ACTION} name="48 sc1 ipv6 global link" source="${sc1IPv6Global}" provider="ip6tables" proto=all
fi
sc2IPv6Global="%%node2_IPv6%%"
${ECHO} ${sc2IPv6Global} | ${GREP} "[a-fA-F0-9]\{0,4\}[:]" >/dev/null
if (( $? == 0 )); then
  litp ${SCFW}/fw_sc2_ipv6_global ${ACTION} name="48 sc2 ipv6 global link" source="${sc2IPv6Global}" provider="ip6tables" proto=all
fi

# Local link rules for SC-1 & SC-2
sc1_serial="%%node1_serial%%"
sc2_serial="%%node2_serial%%"
sc1_mac_path=$(/usr/bin/litp /inventory/deployment1/systems/ find --name ${sc1_serial})
sc1_boot_device=$(/usr/bin/litp ${sc1_mac_path} show | ${AWK} -F\" '/boot_dev:/ {print $2}')
sc1_mac=$(/usr/bin/litp ${sc1_mac_path} show | ${SED} -n 's/.\+macaddresses:.\+'$sc1_boot_device'=\(\([a-zA-Z0-9]\{1,2\}[:]\)\{5\}[a-zA-Z0-9]\{1,2\}\).\+/\1/p')

sc2_mac_path=$(/usr/bin/litp /inventory/deployment1/systems/ find --name ${sc2_serial})
sc2_boot_device=$(/usr/bin/litp ${sc2_mac_path} show | ${AWK} -F\" '/boot_dev:/ {print $2}')
sc2_mac=$(/usr/bin/litp ${sc2_mac_path} show | ${SED} -n 's/.\+macaddresses:.\+'$sc2_boot_device'=\(\([a-zA-Z0-9]\{1,2\}[:]\)\{5\}[a-zA-Z0-9]\{1,2\}\).\+/\1/p')

sc1IPv6Local=$(${_TORINST_BASE_DIR_}/bin/convMacIPv6.py ${sc1_mac})
sc2IPv6Local=$(${_TORINST_BASE_DIR_}/bin/convMacIPv6.py ${sc2_mac})

litp ${SCFW}/fw_sc1_ipv6_local ${ACTION} name="48 sc1 ipv6 local link" source="${sc1IPv6Local}" provider="ip6tables" proto=all
litp ${SCFW}/fw_sc2_ipv6_local ${ACTION} name="48 sc2 ipv6 local link" source="${sc2IPv6Local}" provider="ip6tables" proto=all

#----------------------------------------------------------------------
#ASSIGN IP ADRRESES AND HOSTNAME ALIASES TO SERVICE GROUP CONTAINERS
# takes the list of TOR Service Groups as an argument
#----------------------------------------------------------------------
#updates multicast containers
update_multicast_containers

assign_service_groups ${TOR_JEE_SERVICEGROUP_LIST[*]}

litp /definition/deployment1 materialise






# ---------------------------------------------
# CREATE A TIPC ADDRESS POOL
# ---------------------------------------------
litp /inventory/deployment1/tipc create tipc-address-pool netid="%%tipc_netid%%"


## ---------------------------------------------
## VCS updates
## ---------------------------------------------
litp /inventory/deployment1/cluster1/vcs_config update vcs_csgvip="%%vcs_config_vcs_csgvip%%" \
  vcs_csgnic="bond0" vcs_lltlinklowpri1="bond0" \
  vcs_lltlink2="eth3" vcs_lltlink1="eth2" \
  vcs_csgnetmask="$TOR_NETMASK" vcs_clusterid="%%vcs_config_vcs_clusterid%%" \
  vcs_gconetmask="$TOR_NETMASK" vcs_gconic="bond0" \
  vcs_gcovip="%%vcs_config_vcs_gcovip%%" gco="%%vcs_config_gco%%"

# ---------------------------------------------
# UPDATE NFS SERVER DETAILS
# ---------------------------------------------
# "SFS" driver is used for NAS storage device and "RHEL" for when an extra RHEL
# Linux node is used.
update_nas_settings
# This allocate call creates the neccessary VCS groups and resources
# cmw_cluster_config searches through the service groups for resources that cannot be controlled/monitored by CMW
litp /inventory/deployment1/cluster1/cmw_cluster_config allocate
# ---------------------------------------------
# CREATE NAS API for storage.ini
# ---------------------------------------------
litp /inventory/deployment1/cluster1/sc1/control_1/os/nasapi_sc1 create nas-api path=/cluster storage_pool="%%tor_sfs_storage_pool%%"
litp /inventory/deployment1/cluster1/sc2/control_2/os/nasapi_sc2 create nas-api path=/cluster storage_pool="%%tor_sfs_storage_pool%%"

# ---------------------------------------------
# ADD THE SAN STORAGE DEVICE FOR NODES
# ---------------------------------------------
litp /inventory/deployment1/sanBase create storage-pool-san-base storeName="%%sanBase_storeName%%" \
  storeIPv4IP1="%%sanBase_storeIPv4IP1%%" storeIPv4IP2="%%sanBase_storeIPv4IP2%%" \
  storeUser="%%sanBase_storeUser%%" storePassword="%%sanBase_storePassword%%" \
  storeType="%%sanBase_storeType%%" storeLoginScope="%%sanBase_storeLoginScope%%" \
  storeSiteId="%%sanBase_storeSiteId%%"

litp /inventory/deployment1/sanBase/bootvg create storage-pool-san \
  storeBlockDeviceDefaultSize="${BOOT_DEVICE_SIZE}" \
  storeBlockDeviceDefaultNamePrefix="bootvg" \
  storePoolId="%%storage_POOL_ID%%" \
  poolModes="private_boot" \
  poolType="pool" \
# Create private data lun pool
litp /inventory/deployment1/sanBase/appvg create storage-pool-san \
 storeBlockDeviceDefaultSize="${APP_DEVICE_SIZE}" \
 storeBlockDeviceDefaultNamePrefix="appvg" \
 storePoolId="%%storage_POOL_ID%%" poolModes="private_data" poolType="pool" \


 #Need this for some unknown reason
litp /inventory/deployment1/systems/sfsmachine create generic-system macaddress="80:C1:6E:7A:CA:49" hostname="nasconsole" domain="%%LMS_domain%%"
litp /inventory/deployment1/systems/sfsmachine enable

#create properties files for UI and SSO
generate_ui_properties $SSD

#Copy rsyslog configuration files to Puppet cmw-file directory 
update_rsyslog_conf $SSD

# ---------------------------------------------
# ADD AN NTP SERVER
# ---------------------------------------------
# Systems updating time directly from ntp server
litp /inventory/deployment1/ntp_1 update ipaddress="%%ntp_1_IP%%"

# ------------------------------------------------------------
# SET THIS PROPERTY FOR ALL SYSTEMS NOT TO BE ADDED TO COBBLER
# ------------------------------------------------------------
litp /inventory/deployment1/ms1 update add_to_cobbler="False"

# Update the user's passwords
# The user's passwords must be encrypted, the encryption method is Python's 2.6.6
# crypt function. The following is an example for encrypting the phrase 'passw0rd'
#
# [cmd_prompt]$ python
# Python 2.6.6 (r266:84292, May 20 2011, 16:42:11)
# [GCC 4.4.5 20110214 (Red Hat 4.4.5-6)] on linux2
# Type "help", "copyright", "credits" or "license" for more information.
# >>> import crypt
# >>> crypt.crypt("passw0rd")
# '$6$VbIEnv1XppQpNHel$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ.'
#
# Symbol '$' is a shell metacharacter and needs to be "escaped" with '\\\'
#
litp /inventory/deployment1/ms1/ms_node/users/litp_admin update password=$(crypt "%%litp_admin_password%%")
litp /inventory/deployment1/ms1/ms_node/users/litp_user update password=$(crypt "%%litp_user_password%%")
litp /inventory/deployment1/ms1/ms_node/users/litp_jboss update password=$(crypt "%%litp_user_jboss_password%%")
litp /inventory/deployment1/ms1/ms_node/users/logstash_user update password=$(crypt "%%logstash_user_password%%")
litp /inventory/deployment1/ms1/ms_node/users/storadm update password="\\\$6\\\$VbIEnv1XppQpNHel\\\$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ."
litp /inventory/deployment1/ms1/ms_node/users/storobs update password="\\\$6\\\$VbIEnv1XppQpNHel\\\$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ."

litp /inventory/deployment1/cluster1/sc1/control_1/users/litp_admin update password=$(crypt "%%litp_admin_password%%")
litp /inventory/deployment1/cluster1/sc1/control_1/users/litp_user update password=$(crypt "%%litp_user_password%%")
litp /inventory/deployment1/cluster1/sc1/control_1/users/litp_jboss update password=$(crypt "%%litp_user_jboss_password%%")
litp /inventory/deployment1/cluster1/sc1/control_1/users/logstash_user update password=$(crypt "%%logstash_user_password%%")
litp /inventory/deployment1/cluster1/sc1/control_1/users/storadm update password="\\\$6\\\$VbIEnv1XppQpNHel\\\$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ."
litp /inventory/deployment1/cluster1/sc1/control_1/users/storobs update password="\\\$6\\\$VbIEnv1XppQpNHel\\\$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ."

litp /inventory/deployment1/cluster1/sc2/control_2/users/litp_admin update password=$(crypt "%%litp_admin_password%%")
litp /inventory/deployment1/cluster1/sc2/control_2/users/litp_user update password=$(crypt "%%litp_user_password%%")
litp /inventory/deployment1/cluster1/sc2/control_2/users/litp_jboss update password=$(crypt "%%litp_user_jboss_password%%")
litp /inventory/deployment1/cluster1/sc2/control_2/users/logstash_user update password=$(crypt "%%logstash_user_password%%")
litp /inventory/deployment1/cluster1/sc2/control_2/users/storadm update password="\\\$6\\\$VbIEnv1XppQpNHel\\\$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ."
litp /inventory/deployment1/cluster1/sc2/control_2/users/storobs update password="\\\$6\\\$VbIEnv1XppQpNHel\\\$/ikRQIa5i/cNJR2BYucNkTjHmO/HBzHdvDbsXa7fprXILrGYa.xMOPI9b.y5HrfqWHfVyfXK7AffI9DrkUBWJ."

# Encrypting passwords for the JEE container instances
litp /inventory/deployment1/cluster1/FMPMServ/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/FMPMServ/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

litp /inventory/deployment1/cluster1/SSO/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/SSO/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

litp /inventory/deployment1/cluster1/MSFM/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/MSFM/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

litp /inventory/deployment1/cluster1/MedCore/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/MedCore/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

litp /inventory/deployment1/cluster1/MSPM0/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/MSPM0/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

litp /inventory/deployment1/cluster1/MSPM1/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/MSPM1/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

litp /inventory/deployment1/cluster1/UIServ/su_0/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}
litp /inventory/deployment1/cluster1/UIServ/su_1/jee/instance/ update management-password=${MANAGEMENT_PASSWORD}

# ---------------------------------------------
# CONFIGURE & ALLOCATE THE RESOURCES
# ---------------------------------------------
#
# Set MySQL Password
#
litp /inventory/deployment1/ms1/ms_node/mysqlserver/config update password="%%mysqlserver_config_password%%"

# MS to allocate first and "secure" the blade hw for this node.
litp /inventory/deployment1/ms1 allocate
litp /inventory/deployment1/ms1/ms_node/os/system update hostname="%%LMS_hostname%%"


# Allocate remmaining blades
# LITP-1808 workaround: enable blade used for controller 1 and allocate immediately
if [ ! ${NODE1_ENC_PATH} ] ; then
  ${ECHO} "No landscape enclosure path for controller_1 defined, was blade discovery executed?"
  exit 1
fi
litp ${NODE1_ENC_PATH} enable
litp /inventory/deployment1/cluster1/sc1 allocate

# LITP-1808 workaround: Enable blade used for controller 2 and allocate immediately
if [ ! ${NODE2_ENC_PATH} ] ; then
  ${ECHO} "No landscape enclosure path for controller_2 defined, was blade discovery executed?"
  exit 1
fi
litp ${NODE2_ENC_PATH} enable
litp /inventory/deployment1/cluster1/sc2 allocate


litp /inventory/deployment1 allocate

# WA: Add the nasconsole alias to the LMS /etc/hosts file so the sfs keys can be defined
litp /inventory/deployment1/alias_nasconsole create svc-alias ip="%%sfs_console_IP%%" aliases=%%sfssetup_hostname%%,${SFS_ALIAS}
# Now setup the stuff to get the storadm/storobj keys defined for OMBS
litp /inventory/deployment1/ms1/ms_node/os/sfssetup create sfs-setup-keys \
  server="${SFS_ALIAS}" username="%%sfssetup_username%%" password="%%sfssetup_password%%"

#Add OSS-RC aliases
add_oss_rc_aliases

# Updating hostnames of the systems. Workaround
litp /inventory/deployment1/cluster1/sc1/control_1/os/system update hostname="%%node1_hostname%%" systemname="deployment1_cluster1_sc1"
litp /inventory/deployment1/cluster1/sc2/control_2/os/system update hostname="%%node2_hostname%%" systemname="deployment1_cluster1_sc2"

# Update kiskstart information. Convention for kickstart filenames is node's
# hostname with a "ks" extension

litp /inventory/deployment1/cluster1/sc1/control_1/os/ks update ksname="%%node1_hostname%%.ks" path=/var/lib/cobbler/kickstarts

litp /inventory/deployment1/cluster1/sc2/control_2/os/ks update ksname="%%node2_hostname%%.ks" path=/var/lib/cobbler/kickstarts

# Allocate boot block device for each node
litp /inventory/deployment1/cluster1/sc1/control_1/os/mpather create multipather
litp /inventory/deployment1/cluster1/sc1/control_1/os/boot_blockdevice create block-device-san \
  pool="bootvg" mode="private_boot" size="${BOOT_DEVICE_SIZE}" \
  lunType="thick" \
  net_name=${TOR_STORAGE_NETWORK} bladePowerManaged="True"
litp /inventory/deployment1/cluster1/sc1/control_1/os/boot_blockdevice/mpath create mpath \
  device_path="/dev/mapper/boot_device"

litp /inventory/deployment1/cluster1/sc2/control_2/os/mpather create multipather
litp /inventory/deployment1/cluster1/sc2/control_2/os/boot_blockdevice create block-device-san \
  pool="bootvg" mode="private_boot" size="${BOOT_DEVICE_SIZE}" \
  lunType="thick" \
  net_name=${TOR_STORAGE_NETWORK} bladePowerManaged="True"
litp /inventory/deployment1/cluster1/sc2/control_2/os/boot_blockdevice/mpath create mpath \
  device_path="/dev/mapper/boot_device"



# Allocate a private block device for each node to act as app-vg at mount /op/ericsson does not work
litp /inventory/deployment1/cluster1/sc1/control_1/os/data_blockdevice_app create block-device-san \
  pool="appvg" mode="private_data" size="${APP_DEVICE_SIZE}" \
  lunType="thick" \
  net_name=${TOR_STORAGE_NETWORK} bladePowerManaged="True"
litp /inventory/deployment1/cluster1/sc1/control_1/os/data_blockdevice_app/mpath_app create mpath \
  device_path="/dev/mapper/app_vg"
litp /inventory/deployment1/cluster1/sc1/control_1/os/data_blockdevice_app allocate

litp /inventory/deployment1/cluster1/sc2/control_2/os/data_blockdevice_app create block-device-san \
  pool="appvg" mode="private_data" size="${APP_DEVICE_SIZE}" \
  lunType="thick" \
  net_name=${TOR_STORAGE_NETWORK} bladePowerManaged="True"
litp /inventory/deployment1/cluster1/sc2/control_2/os/data_blockdevice_app/mpath_app create mpath \
  device_path="/dev/mapper/app_vg"
litp /inventory/deployment1/cluster1/sc2/control_2/os/data_blockdevice_app allocate


setup_LVM

# Update the verify user to root. Workaround, user litp_verify doesn't exist yet
litp /inventory/deployment1/ms1 update verify_user="root"
litp /inventory/deployment1/cluster1/sc1 update verify_user="root"
litp /inventory/deployment1/cluster1/sc2 update verify_user="root"

# Allocate the complete site
litp /inventory/deployment1 allocate


# Update JBoss VCS configuration##########################Put in when running with tor apps##############################
if [ ! ${BASE_DEF_ONLY} ]; then
  for _sg_ in ${TOR_JEE_SERVICEGROUP_LIST[*]} ; do
    for _si_ in `${LITP} /inventory/deployment1/cluster1/${_sg_} show -l | ${GREP} -v pib_notification` ; do
      _si_instance_path_=/inventory/deployment1/cluster1/${_sg_}/${_si_}/vcsgrp_jee
      #assign an IP from the pool
      litp ${_si_instance_path_}/vcsip_ip update device="bond0"
      litp ${_si_instance_path_}/vcsnic_ip update device="bond0"
    done
  done

  # Update other components (i.e. non JBoss ones)
  for _si_ in `${LITP} /inventory/deployment1/cluster1/httpd show -l` ; do
    litp /inventory/deployment1/cluster1/httpd/${_si_}/vcsgrp_apache_server/vcsip_ip update device="bond0"
    litp /inventory/deployment1/cluster1/httpd/${_si_}/vcsgrp_apache_server/vcsnic_ip update device="bond0"
  done

  # Update other components (i.e. non JBoss ones)
  for _si_ in `${LITP} /inventory/deployment1/cluster1/logstash show -l` ; do
    litp /inventory/deployment1/cluster1/logstash/${_si_}/vcsgrp_logstash/vcsip_ip update device="bond0"
    litp /inventory/deployment1/cluster1/logstash/${_si_}/vcsgrp_logstash/vcsnic_ip update device="bond0"
  done
fi


hostname "%%LMS_hostname%%"
service puppet restart

# This is an intermediate step before applying the configuration to puppet

litp /inventory/deployment1 configure

#configure service alias
litp /inventory/alias_controller configure



# --------------------------------------
# VALIDATE INVENTORY CONFIGURATION
# --------------------------------------
litp /inventory validate

# --------------------------------------
# APPLY CONFIGURATION TO PUPPET
# --------------------------------------
# Configuration's Manager (Puppet) manifests for the inventory will be created after this
litp /cfgmgr apply scope=/inventory

# --------------------------------------------
# INVENTORY ENDS HERE
# --------------------------------------------

#${LOGGER}
exit 0