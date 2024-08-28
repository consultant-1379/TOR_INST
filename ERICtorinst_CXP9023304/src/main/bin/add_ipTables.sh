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
ACTION="create firewalls-def"

STEP=0
LOGDIR="/var/log/torinst"

if [ ! -d "${LOGDIR}" ]; then
    ${MKDIR} -p ${LOGDIR}
fi
LOGFILE="${LOGDIR}/landscape_firewall.log"
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

create_path()
{
  local _path_=$1
  if [ $# -eq 2 ] ; then
    _type_=$2
  else
    _type_="component-def"
  fi
  ${LITP} ${_path_} show > /dev/null 2>&1
  if [ $? -ne 0 ] ; then
    litp ${_path_} create ${_type_}
  fi
}

create_fwrule()
{
  local _path_=$1
  local _name_=$2
  local _dport_=$3
  local _proto_=$4
  local _provider_=$5
  local _action_=$6
  ${LITP} ${_path_} show > /dev/null 2>&1
  if [ $? -ne 0 ] ; then
    litp ${_path_} create firewalls-def
  fi
  litp ${_path_} update name="${_name_}"
  if [ "${_dport_}" != "none" ] ; then
    litp ${_path_} update dport="${_dport_}"
  fi
  if [ "${_proto_}" != "none" ] ; then
    litp ${_path_} update proto="${_proto_}"
  fi
  if [ "${_provider_}" != "none" ] ; then
    litp ${_path_} update provider="${_provider_}"
  fi
  if [ "${_action_}" != "none" ] ; then
    litp ${_path_} update action="${_action_}"
  fi
}
#
# Create firewallsmain role
#
create_path /definition/firewallsmain
create_path /definition/firewallsmain/config firewalls-main-def
# -----------------------------------------------------------
# DEFINE SOLUTION AND ASSIGN ROLES
# -----------------------------------------------------------
#primary controller
create_path /definition/primary_node/firewallsmain component-ref
litp /definition/primary_node/firewallsmain update component-name=firewallsmain
#secondary controller
create_path /definition/litp_sc_node/firewallsmain component-ref
litp /definition/litp_sc_node/firewallsmain update component-name=firewallsmain
#ms node
create_path /definition/ms_node/firewallsmain component-ref
litp /definition/ms_node/firewallsmain update component-name=firewallsmain

#############################################################################
#
#  NOTE:
#  All iptable rules should have a three number prefix: "XXX some_name"
#  to avoid any mistakes in the ordering of the rules
#
#############################################################################

# Create firewall rules and a reference to the OS role for MS
#Default Rules
create_fwrule ${MSFW}/fw_basetcp "001 basetcp" "21,22,80,111,443,3000,25151,9999,2163,6389" none none none
create_fwrule ${MSFW}/fw_nfstcp "002 nfstcp" "662,875,2020,2049,4001,4045"  none none none
create_fwrule ${MSFW}/fw_hyperic "003 hyperic" "57004,57005,57006" none none none
create_fwrule ${MSFW}/fw_syslog "004 syslog" "514" none none none
create_fwrule ${MSFW}/fw_syslogudp "004 syslogudp" "514" "udp" none none
create_fwrule ${MSFW}/fw_baseudp "010 baseudp" "67,69,111,123,623,25151" "udp" none none
create_fwrule ${MSFW}/fw_nfsudp "011 nfsudp" "662,875,2020,2049,4001,4045" "udp" none none
create_fwrule ${MSFW}/fw_netbackup "012 netbackup" "13724,1556,13783,13722" "udp" none none
create_fwrule ${MSFW}/fw_icmp "100 icmp" none "icmp" "iptables" none
create_fwrule ${MSFW}/fw_icmpv6 "100 icmpv6" none "ipv6-icmp" "ip6tables" none
#SNP and SMTP Rules
create_fwrule ${MSFW}/fw_dns_tcp "101 Nameservices tcp" "53" none none none
create_fwrule ${MSFW}/fw_dns_udp "102 Nameservices udp" "53" "udp" none none
create_fwrule ${MSFW}/fw_smtp_tcp "103 Mail services tcp" "25" none none none
create_fwrule ${MSFW}/fw_smtp_udp "104 Mail services udp" "25" "udp" none none
create_fwrule ${MSFW}/fw_snmp_tcp "105 SNMP tcp" "161,162" none none none
create_fwrule ${MSFW}/fw_snmp_udp "106 SNMP udp" "161,162" "udp" none none
create_fwrule ${MSFW}/fw_logstash_forward_tcp "40 logstash ms forward tcp" "2514" none none none
#jboss management forward
create_fwrule ${MSFW}/fw_jbossMgmt "107 Jboss Mgmt" "9990" none none none
#ombs
create_fwrule ${MSFW}/fw_ombs_tcp "108 OMBS tcp" "13724" "tcp" none none
create_fwrule ${MSFW}/fw_ombs_udp "108 OMBS udp" "13724" "udp" none none

# Create rules and a reference to the OS role for SCs
create_fwrule ${SCFW}/fw_tor_basic "000 tor Jboss" "8080,9990,9999,4447,5445,5455" none none none
create_fwrule ${SCFW}/fw_basetcp "001 basetcp" "22,80,111,161,162,443,1389,3000,25151,7788,2163,6389" none none none
create_fwrule ${SCFW}/fw_tor_oss "001 tor oss" "4569,4570,50042,65532,12468,50057,49786" none none none
create_fwrule ${SCFW}/fw_apps "001 custom ports" "636,389,1494" none none none
create_fwrule ${SCFW}/fw_nfstcp "002 nfstcp" "662,875,2020,2049,4001,4045" none none none
create_fwrule ${SCFW}/fw_hyperic "003 hyperic" "57004,57005,57006" none none none
create_fwrule ${SCFW}/fw_syslog "004 syslog" "514" none none none
create_fwrule ${SCFW}/fw_syslogudp "004 syslogudp" "514" "udp" none none
create_fwrule ${SCFW}/fw_baseudp "010 baseudp" "111,123,623,1129,9876,25151" "udp" none none
#create_fwrule ${SCFW}/fw_nfsudp "011 nfsudp" "662,875,2020,2049,4001,4045" "udp" none none
create_fwrule ${SCFW}/fw_netbackup "012 netbackup" "13724,1556,13783,13722" none none none
create_fwrule ${SCFW}/fw_SSO1 "039 SSO1" "1699,4445,10389" none none none
create_fwrule ${SCFW}/fw_logstash_tcp "040 logstash" "9200" none none none
create_fwrule ${SCFW}/fw_logstash_forward_tcp "041 logstash forward tcp" "2514" none none none
create_fwrule ${SCFW}/fw_icmp "100 icmp" none "icmp" "iptables" none
create_fwrule ${SCFW}/fw_icmpv6 "100 icmpv6" none "ipv6-icmp" "ip6tables" none
create_fwrule ${SCFW}/fw_igmp "100 igmp" none "igmp" none none
create_fwrule ${SCFW}/fw_dns_tcp "101 Nameservices tcp" "53" none none none
create_fwrule ${SCFW}/fw_dns_udp "102 Nameservices udp" "53" "udp" none none
create_fwrule ${SCFW}/fw_Streaming "120 Streaming TCP external" "1233,1234" none none none

litp /definition/deployment1 materialise

${IPTABLES} -F
${IP6TABLES} -F

exit 0

