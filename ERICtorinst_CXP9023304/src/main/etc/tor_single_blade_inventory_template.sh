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
# Inventory template for a singleblade installation of TOR including TOR software.
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


#we need to overwrite/define settings specific to singlenode installation
# The external TOR nework (network on which MS1 eth1 interface is accessible)
TOR_EXTERNAL_NETWORK="external"

# The SFS VIP used to mount the OSS segment share (This should be the same one as OSS uses to mount
#we mount all SFS filesystems from MS!
SFS_VIP_SEGMENT_1="%%LMS_IP%%"
# The SFS VIP used to mount the log file system
LMS_IP="%%LMS_IP%%"
# The SFS VIP used to mount any other file systems
SFS_VIP_GENERAL="%%LMS_IP%%"


#no need for enclosure discovery on singleblade installation
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
#create alias controller xml does not work for this
#we have it already in single node xml definition
#litp /definition/alias_controller create svc-alias-ctrl-def
litp /definition/rd_rsyslog_server/rsyslog_server/ update rlCentralHost="%%node1_hostname%%"
litp /definition/rd_rsyslog_client/rsyslog_client/ update rlCentralHost="%%node1_hostname%%"
litp /definition/rd_rsyslog_client/rsyslog_client/dest1 create rsyslog-destination-def host="%%node1_hostname%%" port=5000 relay=false
litp /definition/rd_rsyslog_client/rsyslog_client/dest2 create rsyslog-destination-def host="%%node2_hostname%%" port=5000 relay=false
#litp /definition/alias_controller materialise

#litp /definition/deployment1 materialise
# ---------------------------------------------
# ADD THE PHYSICAL SERVERS
# ---------------------------------------------
#no need to run discovery for singlenode installation
#discover_blades_from_ilo

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
litp /inventory/deployment1/ms1 load /opt/ericsson/torinst/etc/NetGraphMS-singleblade.xml

# Create IP address pools for TOR Services, Backup and Storage stuff.
create_ip_pools

# Allocate IPs to LMS
# Set a primary IP for the MS and also set the default gateway for br0 (eth0)
# NOTE: we gue LMS_gatewa_ext because we want the default traffic to go through the external network
#   otherwise we may loose contact with MS1 node
#litp /inventory/deployment1/${TOR_SERVICE_POOL} create ip-address-pool
litp /inventory/deployment1/${TOR_SERVICE_POOL}/ms_ip create ip-address \
  subnet=%%LMS_netmask%% address=%%LMS_IP%% gateway=%%LMS_gateway_ext%% net_name=${TOR_SERVICES_NETWORK} interface_id=0
litp /inventory/deployment1/${TOR_SERVICE_POOL}/ms_ip enable
litp /inventory/deployment1/ms1/ms_node/os/ip update pool=${TOR_SERVICE_POOL} net_name=${TOR_SERVICES_NETWORK}
litp /inventory/deployment1/ms1/ms_node/os/ip allocate
#litp /inventory/deployment1/alias_ms create svc-alias ip=%%LMS_IP%% aliases=ms1
# Create and allocate the external network - eth1 interface
litp /inventory/deployment1/${TOR_EXTERNAL_NETWORK} create ip-address-pool
litp /inventory/deployment1/${TOR_EXTERNAL_NETWORK}/ms_external_ip create ip-address \
  subnet=%%LMS_netmask_ext%% address=%%LMS_IP_ext%% gateway=%%LMS_gateway_ext%% net_name=${TOR_EXTERNAL_NETWORK}
litp /inventory/deployment1/${TOR_EXTERNAL_NETWORK}/ms_external_ip enable
litp /inventory/deployment1/ms1/ms_node/os/ip_ext update net_name=${TOR_EXTERNAL_NETWORK}
litp /inventory/deployment1/ms1/ms_node/os/ip_ext allocate

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
# should allow notifications between oss-rc and topsynch
litp ${SCFW}/fw_fm_sc1 ${ACTION} name="46 fmSC1address" dport="30000-65000"  source="%%node1_IP%%"
litp ${SCFW}/fw_fm_sc2 ${ACTION} name="47 fmSC1address" dport="30000-65000"  source="%%node2_IP%%"

litp ${SCFW}/fw_cache_ipV6MulticastS ${ACTION} name="44  ipV6 defaultMultiS" source="ff0e${IPV6_MULTICAST}" provider="ip6tables"
litp ${SCFW}/fw_cache_ipV6MulticastS_udp ${ACTION} name="45 udp ipV6 defaultMultiS" source="ff0e${IPV6_MULTICAST}" provider="ip6tables" proto="udp"
litp ${SCFW}/fw_cache_ipV6MulticastD ${ACTION} name="46  ipV6 defaultMultiD"  destination="ff0e${IPV6_MULTICAST}" provider="ip6tables"
litp ${SCFW}/fw_cache_ipV6MulticastD_udp ${ACTION} name="47 udp ipV6 defaultMultiD"  destination="ff0e${IPV6_MULTICAST}" provider="ip6tables" proto="udp"
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
## singleblade installation - use RHEL driver - nfs is on ms1 node
update_nas_settings singlenode

# This allocate call creates the neccessary VCS groups and resources
# cmw_cluster_config searches through the service groups for resources that cannot be controlled/monitored by CMW
litp /inventory/deployment1/cluster1/cmw_cluster_config allocate
# ---------------------------------------------
# ADD THE PHYSICAL SERVERS
# ---------------------------------------------

litp /inventory/deployment1/systems create generic-system-pool
litp /inventory/deployment1/systems/blade create generic-system macaddress=%%LMS_macaddress%% hostname=%%LMS_hostname%%
litp /inventory/deployment1/systems/blade enable
litp /inventory/deployment1/systems/blade update bridge_enabled=True

# ---------------------------------------------
# ADD THE VIRTUAL NODES
# ---------------------------------------------

#NOTE: we need at least four mac addresses for the two node installation, each node is going to have two interfaces attached to the br0 bridge interface
litp /inventory/deployment1/systems/vm_pool create vm-pool mac_start=%%VM_mac_pool_start%% mac_end=%%VM_mac_pool_end%%
litp /inventory/deployment1/systems/vm_pool update path='/var/lib/libvirt/images'
litp /inventory/deployment1/systems/vm_pool/hyper_visor create vm-host-assignment host='/inventory/deployment1/ms1/ms_node/libvirt/vmservice'

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

litp /inventory/deployment1 allocate

# ------------------------------------------------------------
# SET THIS PROPERTY FOR ALL SYSTEMS NOT TO BE ADDED TO COBBLER
# ------------------------------------------------------------
litp /inventory/deployment1/ms1 update add_to_cobbler="False"

#Add OSS-RC aliases
add_oss_rc_aliases

# Allocate some more h/w resources for VMs, by modifying default values.
litp /inventory/deployment1/systems/vm_pool/vm_deployment1_cluster1_sc1_control_1 update ram=%%VM_ram%% disk=%%VM_disk%% cpus=%%VM_cpus%% hostname="%%node1_hostname%%" systemname="vm_deployment1_cluster1_sc1_control_1"
litp /inventory/deployment1/systems/vm_pool/vm_deployment1_cluster1_sc2_control_2 update ram=%%VM_ram%% disk=%%VM_disk%% cpus=%%VM_cpus%% hostname="%%node2_hostname%%" systemname="vm_deployment1_cluster1_sc2_control_2"


# Updating hostnames of the systems. Workaround
litp /inventory/deployment1/cluster1/sc1/control_1/os/system update hostname="%%node1_hostname%%" systemname="vm_deployment1_cluster1_sc1_control_1"
litp /inventory/deployment1/cluster1/sc2/control_2/os/system update hostname="%%node2_hostname%%" systemname="vm_deployment1_cluster1_sc2_control_2"

# Update kiskstart information. Convention for kickstart filenames is node's
# hostname with a "ks" extension

litp /inventory/deployment1/cluster1/sc1/control_1/os/ks update ksname="%%node1_hostname%%.ks" path=/var/lib/cobbler/kickstarts

litp /inventory/deployment1/cluster1/sc2/control_2/os/ks update ksname="%%node2_hostname%%.ks" path=/var/lib/cobbler/kickstarts
# Update disk sizes - make sure all logical volumes fit on the disk
litp /inventory/deployment1/cluster1/sc1/control_1/os/boot_blockdevice/ update size=%%VM_disk%%
litp /inventory/deployment1/cluster1/sc2/control_2/os/boot_blockdevice/ update size=%%VM_disk%%


setup_LVM singlenode

# Update the verify user to root. Workaround, user litp_verify doesn't exist yet
litp /inventory/deployment1/ms1 update verify_user="root"
litp /inventory/deployment1/cluster1/sc1 update verify_user="root"
litp /inventory/deployment1/cluster1/sc2 update verify_user="root"

#we need to list the mac addresses for each of the nodes so that correct '/etc/udev/rules.d/70-persistent-net.rules' is generated

#we use the same method for calculating MAC addresses as in boot_mgr script
#interfaces on attached to br0:
#mac addresses for the interface eth1 on SC1 and SC2
vm_br0_mac_start=%%VM_mac_pool_start%%
vm_br0_mac_end=%%VM_mac_pool_end%%

#check if bc is installed, if not try to install it
which bc || find /profiles -name 'bc*.rpm' | head -1 | xargs rpm -ihv || { echo "'bc' not found, please install the bc package before proceedeng with installation"; exit 1; }

#convert MAC addresses to hex numbers
m_s=$(echo ${vm_br0_mac_start} | sed -e 's/://g' | tr '[:lower:]' '[:upper:]')
m_e=$(echo ${vm_br0_mac_end} | sed -e 's/://g' | tr '[:lower:]' '[:upper:]')

#convert MAC hex to decimal
h_s=$(echo "ibase=16;${m_s}" | bc)
h_e=$(echo "ibase=16;${m_e}" | bc)

#nothing to do for the eth0 on sc1
mac_sc1eth0=${vm_br0_mac_start}

#we increase the mac address by 1 for each next interface
sc2_eth0=$((h_s + 1))
sc1_eth1=$((h_s + 2))
sc2_eth1=$((h_s + 3))

if [[ (${sc2_eth1} > ${h_e}) ]]; then
    echo "The mac address pool is too small, we need at least four mac addresses for the installation"
    exit 1
fi

#convert the calculated numbers back to MAC addresses
mac_sc1eth1=$(echo "obase=16;${sc1_eth1}" | bc | sed -e 's/\(..\)/\1:/g' | sed -e 's/:$//')
mac_sc2eth0=$(echo "obase=16;${sc2_eth0}" | bc | sed -e 's/\(..\)/\1:/g' | sed -e 's/:$//')
mac_sc2eth1=$(echo "obase=16;${sc2_eth1}" | bc | sed -e 's/\(..\)/\1:/g' | sed -e 's/:$//')

#interfaces attached to llt0 - copied (must be same) from boot_mgr script
#We use local locally administered addresses - see also: https://en.wikipedia.org/wiki/MAC_address

mac_sc1eth2="02:AD:BE:EF:0A:12"
mac_sc1eth3="02:AD:BE:EF:0A:13"
mac_sc2eth2="02:AD:BE:EF:0A:22"
mac_sc2eth3="02:AD:BE:EF:0A:23"


#Update the mac address list for each of the nodes
litp /inventory/deployment1/cluster1/sc1/control_1/os/system update macaddresses=eth0=${mac_sc1eth0},eth1=${mac_sc1eth1},eth2=${mac_sc1eth2},eth3=${mac_sc1eth3}
litp /inventory/deployment1/cluster1/sc2/control_2/os/system update macaddresses=eth0=${mac_sc2eth0},eth1=${mac_sc2eth1},eth2=${mac_sc2eth2},eth3=${mac_sc2eth3}

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



# This is an intermediate step before applying the configuration to puppet
litp /inventory/deployment1 configure
litp /inventory/alias_controller configure


# --------------------------------------
# VALIDATE INVENTORY CONFIGURATION
# --------------------------------------
litp /inventory validate

# --------------------------------------
# APPLY CONFIGURATION TO PUPPET
# --------------------------------------
# Configuration's Manager (Puppet) manifests for the inventory will be created  after this
litp /cfgmgr apply scope=/inventory

# (check for puppet errors -> "grep puppet /var/log/messages")
# (use "service puppet restart" to force configuration now)

# --------------------------------------------
# INVENTORY ENDS HERE
# --------------------------------------------
hostname "%%LMS_hostname%%"
service puppet restart


${LOGGER} -t "tor_inst" "Finished /inventory at `${DATE} +%Y-%m-%d_%H:%M:%S`"
exit 0
