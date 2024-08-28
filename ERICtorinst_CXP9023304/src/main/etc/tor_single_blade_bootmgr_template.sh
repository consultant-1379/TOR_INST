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


INTERACTIVE=Off
# Parsing arguments to check for non-interactive mode. Ignoring unspecified
# arguments
while getopts :i opt; do
    case $opt in
        i)
            INTERACTIVE=Off
            ;;
    esac
done

# pause function to allow for user confirmation in interactive mode
function pause() {
case $INTERACTIVE in
    [Yy]es|[Oo]n|[Tt]rue)
        read -s -n 1 -p "Press any key to continue or Ctrl-C to abort."
        echo
        ;;
esac
}

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
    pause
}

# --------------------------------------------
# BOOT MANAGER STARTS HERE
# --------------------------------------------

# -------------------------------------------------------------
# APPLY CONFIGURATION TO COBBLER & START (BOOT) NODES
# -------------------------------------------------------------

#
# Cobbler must have been configured before running the following commands
# check /var/log/messages for next puppet iteration, 'cobbler sync' should not
# fail after this
#

# Cobbler's management interface
litp /bootmgr update server_url="http://127.0.0.1/cobbler_api" username="cobbler" password="litpc0b6lEr"
service dhcpd stop
rm -f /etc/cobbler/dhcp.template
service puppet restart

# Find the CobblerService object in landscape
landscape_path=$(/usr/bin/litp / find --resource cobbler_server.service.CobblerService)
# Check the value of the "manage_dhcp" setting
manage_dhcp=$(/usr/bin/litp $landscape_path show properties --json|awk -F\" '/\"manage_dhcp\"/{print $4}')
# Only call wait_for_dhcp function if manage_dhcp = 1
[ "$manage_dhcp" = "1" ] && wait_for_dhcp

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

# --------------------------------------------
# BOOT MANAGER ENDS HERE
# --------------------------------------------

#echo "Check 'cobbler list' to see if cluster installation has been kickstarted."
#
# A function that checks if cobbler is ready with a profile and distro
# before starting to create systems
#
function wait_for_vm_stared() {
    c=0 # attempt timer
    TEMPO=2 # interval between checks
    started=0 #1 means vm sc1, sc2 are started

    #!!! hardcoded MAC addresses !!!
    #these are attached to llt0 which is a local bridge
    #these addresses should never be announced beyond MS1 station
    #We use local locally administered addresses - see also: https://en.wikipedia.org/wiki/MAC_address

        mac_sc1eth2="02:AD:BE:EF:0A:12"
        mac_sc1eth3="02:AD:BE:EF:0A:13"
        mac_sc2eth2="02:AD:BE:EF:0A:22"
        mac_sc2eth3="02:AD:BE:EF:0A:23"

    #mac addresses for the interface eth1 on SC1 and SC2 - will be attached to br0
    vm_br0_mac_start=%%VM_mac_pool_start%%
    vm_br0_mac_end=%%VM_mac_pool_end%%

    #convert MAC addresses to hex numbers
    m_s=$(echo ${vm_br0_mac_start} | sed -e 's/://g' | tr '[:lower:]' '[:upper:]')
    m_e=$(echo ${vm_br0_mac_end} | sed -e 's/://g' | tr '[:lower:]' '[:upper:]')

    #convert MAC hex to decimal
    h_s=$(echo "ibase=16;${m_s}" | bc)
    h_e=$(echo "ibase=16;${m_e}" | bc)

    #nothing to do for the eth0 on sc1 and sc2

    #we increase the mac address by 1 for each next interface
    sc1_eth1=$((h_s + 2))
    sc2_eth1=$((h_s + 3))

    if [[ (${sc2_eth1} > ${h_e}) ]]; then
        echo "The mac address pool is too small, we need at least four mac addresses for the installation"
        exit 1
    fi

    #convert the calculated numbers back to MAC addresses
    mac_sc1eth1=$(echo "obase=16;${sc1_eth1}" | bc | sed -e 's/\(..\)/\1:/g' | sed -e 's/:$//')
    mac_sc2eth1=$(echo "obase=16;${sc2_eth1}" | bc | sed -e 's/\(..\)/\1:/g' | sed -e 's/:$//')

    echo "Waiting for vm: sc1 sc2 to be started ..."

    time_elapsed $(( $c * $TEMPO ))

    while sleep $TEMPO; do
        let c++
        time_elapsed $(( $c * $TEMPO ))

        #network interfaces can be attached only to running interfaces
        virsh list | grep sc1 | grep running 2>&1 1>/dev/null && virsh list | grep sc2 | grep running 2>&1 1>/dev/null && let started++

        #there may be problems with booting vm with multiple interfaces, give vm abot a minute after they are running before adding interfaces
        if [[ ${started} == 30 ]]; then
            #find full names of virtual machines
            vmsc1=$(virsh list | grep sc1 | awk '{print $2}')
            vmsc2=$(virsh list | grep sc2 | awk '{print $2}')

            file=$(mktemp -t llt.XXXXX.xml)

            #define a bridge not connected to any physical interface
            echo '
            <network>
            <name>vcs_llt</name>
            <bridge name="llt0" />
            </network>' > ${file}

            #for network setup see http://wiki.libvirt.org/page/Networking#NAT_forwarding_.28aka_.22virtual_networks.22.29
            virsh net-define ${file}

            rm ${file}

            #mark network for autostart
            virsh net-autostart vcs_llt
            #start it
            virsh net-start vcs_llt

            #attach eth1 interface to br0 bridge, and next two to llt0
            #VCS llt traffic should go via llt0 bridge
            virsh attach-interface ${vmsc1} bridge br0 --mac ${mac_sc1eth1} --persistent
            virsh attach-interface ${vmsc1} bridge llt0 --mac ${mac_sc1eth2} --persistent
            virsh attach-interface ${vmsc1} bridge llt0 --mac ${mac_sc1eth3} --persistent
            virsh attach-interface ${vmsc2} bridge br0 --mac ${mac_sc2eth1} --persistent
            virsh attach-interface ${vmsc2} bridge llt0 --mac ${mac_sc2eth2} --persistent
            virsh attach-interface ${vmsc2} bridge llt0 --mac ${mac_sc2eth3} --persistent

            break
        fi
    done

    echo
    echo "eth1, eth2 and eth3 interfaces added to vm sc1 an sc2"
}

function configure_ebtables {
    ebtables=`which ebtables`
    if [[ $? == 1 ]]; then
        echo "Could not find ebtables executable on the syste. Is the ebtables package installed?"
        echo "ebtable firewall will not be confiugred ..."
        echo "You can try to configure it manually after installing ebtables package. Install rules:"
        echo "
        ebtables -t filter -A INPUT -p IPv4 -i eth0 --pkttype-type ! multicast -j ACCEPT
        ebtables -t filter -A INPUT -p ARP -i eth0 -j ACCEPT
        ebtables -t filter -A INPUT -i eth0 -j DROP
        ebtables -t filter -A FORWARD -p IPv4 -i eth0 --pkttype-type ! multicast -j ACCEPT
        ebtables -t filter -A FORWARD -p ARP -i eth0 -j ACCEPT
        ebtables -t filter -A FORWARD -p IPv4 -o eth0 --pkttype-type ! multicast -j ACCEPT
        ebtables -t filter -A FORWARD -p ARP -o eth0 -j ACCEPT
        ebtables -t filter -A FORWARD -i eth0 -j DROP
        ebtables -t filter -A FORWARD -o eth0 -j DROP
        ebtables -t filter -A OUTPUT -p IPv4 -o eth0 --pkttype-type ! multicast -j ACCEPT
        ebtables -t filter -A OUTPUT -p ARP -o eth0 -j ACCEPT
        ebtables -t filter -A OUTPUT -o eth0 -j DROP"
        echo

        return 1
    fi

    echo
    echo "Flushing current ebtables rules ..."
    ebtables -F

    echo "Blocking all but unicast IP and arp traffic on the eth0 interface"
    ebtables -t filter -P INPUT ACCEPT
    ebtables -t filter -P OUTPUT ACCEPT
    ebtables -t filter -P FORWARD ACCEPT
    ebtables -t filter -A INPUT -p IPv4 -i eth0 --pkttype-type ! multicast -j ACCEPT
    ebtables -t filter -A INPUT -p ARP -i eth0 -j ACCEPT
    ebtables -t filter -A INPUT -i eth0 -j DROP
    ebtables -t filter -A FORWARD -p IPv4 -i eth0 --pkttype-type ! multicast -j ACCEPT
    ebtables -t filter -A FORWARD -p ARP -i eth0 -j ACCEPT
    ebtables -t filter -A FORWARD -p IPv4 -o eth0 --pkttype-type ! multicast -j ACCEPT
    ebtables -t filter -A FORWARD -p ARP -o eth0 -j ACCEPT
    ebtables -t filter -A FORWARD -i eth0 -j DROP
    ebtables -t filter -A FORWARD -o eth0 -j DROP
    ebtables -t filter -A OUTPUT -p IPv4 -o eth0 --pkttype-type ! multicast -j ACCEPT
    ebtables -t filter -A OUTPUT -p ARP -o eth0 -j ACCEPT
    ebtables -t filter -A OUTPUT -o eth0 -j DROP

    echo
    echo "Making the rules permament between node reboots:"
    /etc/init.d/ebtables save
    echo
    #make sure the ebtables is started after reboot
    chkconfig ebtables on

    echo "Updating br0 settings - if you reboot the MS1 node you will have to restore settings by issuing following commands:"
    echo "      brctl setmcrouter br0 0"
    echo "      brctl setmcsnoop br0 0"

    #configure br0 to allow multicast
    #disable ports as having multicast routers attached
    brctl setmcrouter br0 0
    #switch off icmp snooping
    brctl setmcsnoop br0 0

    #we make sure nfs is started on ms1
    echo "Checking configuration to make sure nfs service is started ..."
    /etc/init.d/nfs status || /etc/init.d/nfs start
    chkconfig nfs on

}

#configure ebtable firewall rules
configure_ebtables

#attach additional interfaces to the vm-s
wait_for_vm_stared

exit 0
