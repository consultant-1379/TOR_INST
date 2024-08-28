#!/usr/bin/env python

from hp_ilo.SystemHPiLO import *
from functions import *
import os
import re
import subprocess
import sys

# example of 1 x MWS
#
# export MWS_LIST=10.44.86.41
# export DICTIONARY="'10.44.86.41':{'NFS_SHARE_LIST':[sys_test],'NFS_SHARE_IP_LIST':[10.44.86.23,10.44.86.24],'SFS_CONNECTIVITY_INFO':[10.44.86.31,master,master,/var/NFSService/locks/SFS/],'MWS_CONNECTIVITY_INFO':[10.44.86.41,root,@dm1nS3rv3r,10.44.86.30],'SAN_GROUP_LIST':[LITP_Site1SysDD_SC-1_GRP],'SAN_HOST_LIST':[LITP_Site1SysDD_SC-1_HST],'SAN_NODES_ILO_IP_LIST':[10.44.84.10],'SAN_NODES_ILO_USER_LIST':[root],'SAN_NODES_ILO_PASSWORD_LIST':[shroot12],'SAN_CONNECTIVITY_INFO':[10.44.84.27,root,shroot12,local,/opt/Navisphere/bin/naviseccli]}"
#
# example to create filesystem and shares
#
# storage fs create simple sys_test 2048M SFS_Pool
# nfs share add rw,sync,no_root_squash /vx/sys_test 10.44.86.23
# nfs share add rw,sync,no_root_squash /vx/sys_test 10.44.86.24
#
# list of luns
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local getlun -name
#
# list of storage groups
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -list
#
# list of HBA ports	
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local port -list -hba
#
# create lun
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local bind r5 -rg 0 -rc 1 -wc 1 -sp auto -sq gb -cap 10 -name LITP_Site1SysDD_SysDD_1_LUN
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local bind r5 -rg 0 -rc 1 -wc 1 -sp auto -sq gb -cap 10 -name LITP_Site1SysDD_SysDD_2_LUN
# bind:
# r5:		RAID 5
# -rg 0: 	RAID group identification number - this group must already exist
# -rc 1:	enables read-cache functionality for this LUN (1 is default can be omitted?)
# -wc 1:	enables write-cache functionality for this LUN (again 1 is default can be omitted?)
# -sp auto:	set the default owner of the LUN (documentation says a|b no auto is mentioned is it working or it just takes default?)
# -sq gb:	size-qualifier will be in gb (again it is default)
# -cap 10:	capacity of usable space in the LUN 10GB in this case
# -name:	LUN name
#
# create group
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -create -gname LITP_Site1SysDD_SC-1_GRP
# storagegroup:
# -create:	creates the storage group
# -gname:	name of the storage group
#
# get WWN respectively hbauid
# HBA port 1: 50:01:43:80:14:0D:67:B0
# HBA port 2: 50:01:43:80:14:0D:67:B2
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local port -list -hba | grep 50:01:43:80:14:0D:67:B0
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local port -list -hba | grep 50:01:43:80:14:0D:67:B2
# WWN port 1: 50:01:43:80:14:0D:67:B1:50:01:43:80:14:0D:67:B0
# WWN port 2: 50:01:43:80:14:0D:67:B3:50:01:43:80:14:0D:67:B2
# other information you can get from grep -C25
#
# register paths
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -setpath -o -gname LITP_Site1SysDD_SC-1_GRP -hbauid 50:01:43:80:14:0D:67:B1:50:01:43:80:14:0D:67:B0 -sp A -spport 1 -type 3 -host LITP_Site1SysDD_SC-1_HST -ip 10.44.86.21 -failovermode 4 -arraycommpath 1
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -setpath -o -gname LITP_Site1SysDD_SC-1_GRP -hbauid 50:01:43:80:14:0D:67:B1:50:01:43:80:14:0D:67:B0 -sp B -spport 1 -type 3 -host LITP_Site1SysDD_SC-1_HST -ip 10.44.86.21 -failovermode 4 -arraycommpath 1
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -setpath -o -gname LITP_Site1SysDD_SC-1_GRP -hbauid 50:01:43:80:14:0D:67:B3:50:01:43:80:14:0D:67:B2 -sp A -spport 4 -type 3 -host LITP_Site1SysDD_SC-1_HST -ip 10.44.86.21 -failovermode 4 -arraycommpath 1
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -setpath -o -gname LITP_Site1SysDD_SC-1_GRP -hbauid 50:01:43:80:14:0D:67:B3:50:01:43:80:14:0D:67:B2 -sp B -spport 4 -type 3 -host LITP_Site1SysDD_SC-1_HST -ip 10.44.86.21 -failovermode 4 -arraycommpath 1
#
# add LUN to group
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -addhlu -gname LITP_Site1SysDD_SC-1_GRP -hlu 0 -alu 53
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -addhlu -gname LITP_Site1SysDD_SC-1_GRP -hlu 1 -alu 56
#
# parse the ID of the luns and keep them for deletition
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -list -gname LITP_Site1SysDD_SC-1_GRP
#
# remove LUN from group
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -removehlu -o -gname LITP_Site1SysDD_SC-1_GRP -hlu 0
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -removehlu -o -gname LITP_Site1SysDD_SC-1_GRP -hlu 1
#
# disconnect hosts
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -disconnecthost -o -host LITP_Site1SysDD_SC-1_HST -gname LITP_Site1SysDD_SC-1_GRP
#
# delete group
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local storagegroup -destroy -o -gname LITP_Site1SysDD_SC-1_GRP
#
# delete LUN
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local unbind 53 -o
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local unbind 56 -o
#
# deregister paths
# /opt/Navisphere/bin/naviseccli -Address 10.44.84.27 -User root -Password shroot12 -Scope local port -removeHBA -o -host LITP_Site1SysDD_SC-1_HST

MWS_LIST=[]
DICTIONARY={}
KEYS=('NFS_SHARE_LIST', 'NFS_SHARE_IP_LIST', 'SFS_CONNECTIVITY_INFO', 'MWS_CONNECTIVITY_INFO', 'SAN_GROUP_LIST', 'SAN_HOST_LIST', 'SAN_CONNECTIVITY_INFO', 'SAN_NODES_ILO_IP_LIST', 'SAN_NODES_ILO_USER_LIST', 'SAN_NODES_ILO_PASSWORD_LIST')


def load_cfg():
	timeStamp('load_cfg start')

	# List of MWSs
	mws_list = os.getenv('MWS_LIST')
        mws_list = mws_list.split(',')
        for mws in mws_list:
        	MWS_LIST.append(mws)

	dictionary = os.getenv('DICTIONARY')
	# parse it to multi-dimensional associative array
	pre_dictionary = filter(None, re.split("['][0-9]+[.][0-9]+[.][0-9]+[.][0-9]+['][:]", dictionary))
	if len(pre_dictionary) == len(MWS_LIST):
		counter = 0
		for mws in pre_dictionary:
			print(pre_dictionary)
			DICTIONARY[MWS_LIST[counter]] = {}
			# for list items in dictionary
			for item in KEYS:
				ITEM_LIST = []
				match_item_list = re.search("(" + item + "{1})['][:][[]([^]]+)[]]", mws)
				if match_item_list:
					item_split = match_item_list.group(2).split(',')
					for items in item_split:
						ITEM_LIST.append(items)
					DICTIONARY[MWS_LIST[counter]][match_item_list.group(1)] = ITEM_LIST
			counter = counter + 1
		print('\nConfiguration variables successfully loaded\n')
	else:
		print('\nConfiguration variables do NOT match MWS list\n')

	print('\nDICTIONARY:')
	print(DICTIONARY)
	for mws in range (len(MWS_LIST)):
		print('\n' + str(mws+1) + '. MWS to prepare:')
		print('IP - ' + MWS_LIST[mws])
		for item in KEYS:
			if DICTIONARY[MWS_LIST[mws]].has_key(item):
				dict2list = ''
				dict2list = ', '.join(DICTIONARY[MWS_LIST[mws]][item])
				print(item + ' - ' + dict2list) 
			else:
				print('No key value for ' + item)
		print('End of definition of ' + str(mws+1) + '. MWS\n')

	# Remove the script name from arguments
	sys.argv.remove(sys.argv[0])
	timeStamp('load_cfg end')


def nfs_shares_delete(filesystems=False):
	try:
		timeStamp('nfs_shares_delete start')
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][2])
			# Connect to SFS server
			ssh._sshConnect()
			print('Deleting NFS shares on ' + DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][0])
			for share in DICTIONARY[mws]['NFS_SHARE_LIST']:
				for ip in DICTIONARY[mws]['NFS_SHARE_IP_LIST']:
					cmd_text = 'nfs share delete /vx/' + share + ' ' + ip
					result = ssh._runCmd(cmd_text, False)
					result_list = ''.join(result)
					print(result_list.rstrip('\r\n'))
				if filesystems:
					timeStamp('nfs_filesystem_destroy start')
					nfs_filesystem_destroy(ssh,mws,share)
					timeStamp('nfs_filesystem_destroy end')
			ssh._sshDisconnect()
		timeStamp('nfs_shares_delete end')
	except Exception as exception:
		print('\nnfs_shares_delete ERROR\n')
		handleException(exception)
			

def nfs_filesystem_destroy(ssh=None,mws=None,share=None):
	try:
		if (ssh != None) and (mws != None) and (share != None):
			print('Destroying NFS filesystems on ' + DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][0])
			print('Destroying filesystem ' + share)
			cmd_text = 'storage fs destroy ' + share
			result = ssh._runCmd(cmd_text, False)
			result_list = ''.join(result)
			print(result_list.rstrip('\r\n'))
		else:
			if (ssh == None) and (mws == None) and (share == None):
				timeStamp('nfs_filesystem_destroy start')
				for mws in MWS_LIST:
					# Create the connection class
					ssh = SystemHPiLO()
					# Set properties for ssh
					ssh.setHost(DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][0])
					ssh.setUser(DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][1])
					ssh.setPassword(DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][2])
					# Connect to SFS server
					ssh._sshConnect()
					for share in DICTIONARY[mws]['NFS_SHARE_LIST']:
						nfs_filesystem_destroy(ssh,mws,share)
					ssh._sshDisconnect()
				timeStamp('nfs_filesystem_destroy end')
	except Exception as exception:
		print('\nnfs_filesystem_destroy ERROR\n')
		handleException(exception)


def luns_and_groups_delete():
	try:
		timeStamp('luns_and_groups_delete start')
		for mws in MWS_LIST:
			for node in DICTIONARY[mws]['SAN_NODES_ILO_IP_LIST']:
				# Create the connection class
				ssh = SystemHPiLO()
				# Set properties for ssh
				ssh.setHost(node)
				ssh.setUser(DICTIONARY[mws]['SAN_NODES_ILO_USER_LIST'][DICTIONARY[mws]['SAN_NODES_ILO_IP_LIST'].index(node)])
				ssh.setPassword(DICTIONARY[mws]['SAN_NODES_ILO_PASSWORD_LIST'][DICTIONARY[mws]['SAN_NODES_ILO_IP_LIST'].index(node)])
				# Power off the node
				power_on_off = ssh.iLOPowerStatus()
				for item in power_on_off:
					if item.find('power: server power is currently: On') > -1:
						result = ssh.iLOPowerOFF()
			print('Deleting groups on ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][0])
			for group in DICTIONARY[mws]['SAN_GROUP_LIST']:
				base_cmd  = DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][4] + ' -Address ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][0] + ' -User ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][1] + \
					    ' -Password ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][2] + ' -Scope ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][3]
				# get the information about LUNs in the storage group before deletition
				cmd_text = base_cmd + ' storagegroup -list -gname ' + group
				print('executing command: ' + cmd_text)
				result = subprocess.Popen(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
				stdout, stderr = result.communicate()
				print(stdout.rstrip('\r\n'))
				match = re.findall("^\s+([0-9]+)\s+([0-9]+)", stdout, re.MULTILINE)
				if match:
					# remove luns from the group
					for item in match:
						cmd_text = base_cmd + ' storagegroup -removehlu -o -gname ' + group + ' -hlu ' + item[0]
						print('executing command: ' + cmd_text)
						result = subprocess.Popen(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
						stdout, stderr = result.communicate()
						if len(stdout.rstrip('\r\n')) == 0:
							print('Success')
						else:
							print(stdout.rstrip('\r\n'))
					# disconnect host from the group
					cmd_text = base_cmd + ' storagegroup -disconnecthost -o -host ' + DICTIONARY[mws]['SAN_HOST_LIST'][DICTIONARY[mws]['SAN_GROUP_LIST'].index(group)] + ' -gname ' + group
					print('executing command: ' + cmd_text)
					result = subprocess.Popen(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
					stdout, stderr = result.communicate()
					if len(stdout.rstrip('\r\n')) == 0:
						print('Success')
					else:
						print(stdout.rstrip('\r\n'))
					# delete the group
					cmd_text = base_cmd + ' storagegroup -destroy -o -gname ' + group
					print('executing command: ' + cmd_text)
					result = subprocess.Popen(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
					stdout, stderr = result.communicate()
					if len(stdout.rstrip('\r\n')) == 0:
						print('Success')
					else:
						print(stdout.rstrip('\r\n'))
					# delete the luns
					for item in match:
						cmd_text = base_cmd + ' lun -destroy -l ' + item[1] + ' -o'
						print('executing command: ' + cmd_text)
						result = subprocess.Popen(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
						stdout, stderr = result.communicate()
						if len(stdout.rstrip('\r\n')) == 0:
							print('Success')
						else:
							print(stdout.rstrip('\r\n'))
		timeStamp('luns_and_groups_delete end')
	except Exception as exception:
		print('\nluns_and_groups_delete ERROR\n')
		handleException(exception)


def wwpn_deregister():
	try:
		timeStamp('wwpn_deregister start')
		for mws in MWS_LIST:
			print('Deregistering paths on ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][0])
			for node in DICTIONARY[mws]['SAN_NODES_ILO_IP_LIST']:
				# Create the connection class
				ssh = SystemHPiLO()
				# Set properties for ssh
				ssh.setHost(node)
				ssh.setUser(DICTIONARY[mws]['SAN_NODES_ILO_USER_LIST'][DICTIONARY[mws]['SAN_NODES_ILO_IP_LIST'].index(node)])
				ssh.setPassword(DICTIONARY[mws]['SAN_NODES_ILO_PASSWORD_LIST'][DICTIONARY[mws]['SAN_NODES_ILO_IP_LIST'].index(node)])
				# Power off the node
				power_on_off = ssh.iLOPowerStatus()
				for item in power_on_off:
					if item.find('power: server power is currently: On') > -1:
						result = ssh.iLOPowerOFF()
						power_on_off_2 = ssh.iLOPowerStatus()
						for item in power_on_off_2:
							if item.find('power: server power is currently: On') > -1:
								print 'WORKAROUND >>> Blade could not power off so Resetting...'
								ssh.iLOPowerReset()
			for host in DICTIONARY[mws]['SAN_HOST_LIST']:
				base_cmd  = DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][4] + ' -Address ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][0] + ' -User ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][1] + \
					    ' -Password ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][2] + ' -Scope ' + DICTIONARY[mws]['SAN_CONNECTIVITY_INFO'][3]
				cmd_text = base_cmd + ' port -removeHBA -o -host ' + host
				print('executing command: ' + cmd_text)
				result = subprocess.Popen(cmd_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
				stdout, stderr = result.communicate()
				if len(stdout.rstrip('\r\n')) == 0:
					print('Success')
				else:
					print(stdout.rstrip('\r\n'))
		timeStamp('wwpn_deregister end')
	except Exception as exception:
		print('\nwwpn_deregister ERROR\n')
		handleException(exception)


def virsh_clean():
	try:
		timeStamp('virsh_clean start')
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			# Virsh list clean up
			cmd_text = 'cobbler system list'
			print('executing command: ' + cmd_text)
			result = ssh._runCmd(cmd_text, False)
			if result != []:
				result_list = ''.join(result)
				print(result_list.rstrip('\r\n'))
			# For each VM
			for vm_name in result:
				print(vm_name[1])
				for commands in ('virsh destroy ' + vm_name, 'virsh undefine ' + vm_name):
					print('executing command: ' + commands)
					result_virsh = ssh._runCmd(commands, False)
					if result_virsh != []:
						result_list = ''.join(result_virsh)
						print(result_list.rstrip('\r\n'))
			# Clean up after VM creation
			for commands in ('rm -rf /var/lib/libvirt/qemu/save/*', 'rm -rf /etc/libvirt/qemu/*.xml', 'rm -rf /var/lib/libvirt/images/*'):
				print('executing command: ' + commands)
				result_virsh = ssh._runCmd(commands, False)
				if result_virsh != []:
					result_list = ''.join(result_virsh)
					print(result_list.rstrip('\r\n'))
			ssh._sshDisconnect()
		timeStamp('virsh_clean end')
	except Exception as exception:
		print('\nvirsh_clean ERROR\n')
		handleException(exception)


def mws_time_sync():
	try:
		timeStamp('mws_time_sync')
		for mws in MWS_LIST:	
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			ntp_set = False
			for commands in ('service puppet stop', 'service puppetmaster stop', 'puppetca --clean $(hostname)', 'grep "' + DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][3] + '" /etc/ntp.conf', 'echo server ' + DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][3] + ' >> /etc/ntp.conf', 'service ntpd stop', 'ntpdate ' + DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][3], 'service ntpd start', 'service puppetmaster start', 'service puppet start'):
				if ntp_set and commands == 'echo server ' + DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][3] + ' >> /etc/ntp.conf':
					print('skipping command: ' + commands)
				else:
					print('executing command: ' + commands)
					result = ssh._runCmd(commands, False)
				if result != []:
					if commands == 'grep "' + DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][3] + '" /etc/ntp.conf':
						ntp_set = True
					result_list = ''.join(result)
					print(result_list.rstrip('\r\n'))
					result = []
			ssh._sshDisconnect()
		timeStamp('mws_time_sync end')
	except Exception as exception:
		print('\nmws_time_sync ERROR\n')
		handleException(exception)


def puppet_ssl_mws_clean():
	try:
		timeStamp('puppet_ssl_mws_clean start')
		for mws in MWS_LIST:	
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			for commands in ('service puppet stop', 'service puppetmaster stop', 'puppetca --clean $(hostname)', 'service puppetmaster start', 'service puppet start'):
				print('executing command: ' + commands)
				result = ssh._runCmd(commands, False)
				if result != []:
					result_list = ''.join(result)
					print(result_list.rstrip('\r\n'))
			ssh._sshDisconnect()
		timeStamp('puppet_ssl_mws_clean end')
	except Exception as exception:
		print('\npuppet_ssl_mws_clean ERROR\n')
		handleException(exception)


def puppet_ssl_node_clean():
	try:
		timeStamp('puppet_ssl_node_clean start')
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			# Cobbler system list 
			cmd_text = 'cobbler system list'
			print('executing command: ' + cmd_text)
			result = ssh._runCmd(cmd_text, False)
			if result != []:
				result_list = ''.join(result)
				print(result_list.rstrip('\r\n'))
			for system_name in result:
				# Parse the hostnames
				cmd_text = 'cobbler system report --name ' + system_name.rstrip('\r\n') + ' |grep Hostname'
				hostname = ssh._runCmd(cmd_text, False)
				match = re.match("Hostname{1}[^:]+[: ](.*)", hostname[0])
				if match:
					system_name_stripped = match.group(1).strip()
				for commands in ('ssh ' + system_name_stripped + ' service puppet stop', 'puppetca --clean ' + system_name_stripped, 'ssh ' + system_name_stripped + ' rm -rf /var/lib/puppet/ssl/*', 'ssh ' + system_name_stripped + ' service puppet start'):
					print('executing command: ' + commands)
					result = ssh._runCmd(commands, False)
					if result != []:
						result_list = ''.join(result)
						print(result_list.rstrip('\r\n'))
			ssh._sshDisconnect()
		# Idea is to connect to node one by one stop puppet on it, run puppetca --clean nodename on mws, remove /var/lib/puppet/ssl/* on node and start a puppet again
		timeStamp('puppet_ssl_node_clean end')
	except Exception as exception:
		print('\npuppet_ssl_node_clean ERROR\n')
		handleException(exception)


def cobbler_clean():
	try:
		timeStamp('cobbler_clean start')
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			# Cobbler system list clean up
			cmd_text = 'cobbler system list'
			print('executing command: ' + cmd_text)
			result = ssh._runCmd(cmd_text, False)
			if result != []:
				result_list = ''.join(result)
				print(result_list.rstrip('\r\n'))
			for system_name in result:
				cmd_text = 'cobbler system remove --name ' + system_name
				print('executing command: ' + cmd_text)
				result_remove = ssh._runCmd(cmd_text, False)
			# Cobbler distro list clean up
			cmd_text = 'cobbler distro list'
			print('executing command: ' + cmd_text)
			result = ssh._runCmd(cmd_text, False)
			if result != []:
				result_list = ''.join(result)
				print(result_list.rstrip('\r\n'))
			for distro_name in result:
				cmd_text = 'cobbler distro remove --name ' + distro_name
				print('executing command: ' + cmd_text)
				result_remove = ssh._runCmd(cmd_text, False)
			ssh._sshDisconnect()
		timeStamp('cobbler_clean end')
	except Exception as exception:
		print('\ncobbler_clean ERROR\n')
		handleException(exception)


def known_hosts_delete():
	try:
		timeStamp('known_hosts_delete start')
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			cmd_text = 'rm -rf ~/.ssh/known_hosts'
			print('executing command: ' + cmd_text)
			result = ssh._runCmd(cmd_text, False)
			ssh._sshDisconnect()
		timeStamp('known_hosts_delete end')
	except Exception as exception:
		print('\nknown_hosts_delete ERROR\n')
		handleException(exception)


def etc_hosts_default():
	try:
		timeStamp('etc_hosts_default start')
		backup_dir = 'mws_prepare_backup'
		# Run before or after landscape but bare in mind this will restore the /etc/hosts file only if you save it beforehand
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			cmd_text = 'ls -ltr ~/' + backup_dir + '/hosts'
			file_exists = ssh._runCmd(cmd_text, False)
			# If the file exists in the specified location then
			if len(file_exists) == 1:
				# Overwrite the original /etc/hosts with the backup one
				cmd_text = 'cp -f ~/' + backup_dir + '/hosts /etc/hosts'
				print('executing command: ' + cmd_text)
				result = ssh._runCmd(cmd_text, False)
			else:
				# Create backup directory
				cmd_text = 'mkdir -p ' + backup_dir
				print('executing command: ' + cmd_text)
				result = ssh._runCmd(cmd_text, False)
				# Copy /etc/hosts to backup directory
				cmd_text = 'cp /etc/hosts ~/' + backup_dir + '/'
				print('executing command: ' + cmd_text)
				result = ssh._runCmd(cmd_text, False)			
			ssh._sshDisconnect()
		timeStamp('etc_hosts_default end')
	except Exception as exception:
		print('\netc_hosts_default ERROR\n')
		handleException(exception)


def nfs_locks_clean():
	try:
		timeStamp('nfs_locks_clean start')
		for mws in MWS_LIST:
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			if DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][3].strip() <> '':
				print('Deleting SFS locks in ' + DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][3])
				# To prevent executing rm -rf * command if manifest_dir determination fails
				cmd_text = 'rm -rf ' + DICTIONARY[mws]['SFS_CONNECTIVITY_INFO'][3] + '*'
				print('executing command: ' + cmd_text)
				result = ssh._runCmd(cmd_text, False)
				if result != []:
					result_list = ''.join(result)
					print(result_list.rstrip('\r\n'))
			else:
				print('Please supply NFS locks path first')
			ssh._sshDisconnect()
		timeStamp('nfs_locks_clean end')
	except Exception as exception:
		print('\nnfs_locks_clean ERROR\n')
		handleException(exception)


def landscaped_to_initial():
	try:
		timeStamp('landscaped_to_initial start')
		for mws in MWS_LIST:
			rm_rf_manifest_dir_text = ''
			# Create the connection class
			ssh = SystemHPiLO()
			# Set properties for ssh
			ssh.setHost(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][0])
			ssh.setUser(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][1])
			ssh.setPassword(DICTIONARY[mws]['MWS_CONNECTIVITY_INFO'][2])
			# Connect to MWS
			ssh._sshConnect()
			# Determine the landscaped service directory is cat /etc/init.d/landscaped |grep EXPORT_DIR ... is that the only location where it resides?
			# Determine the manifest directory
			cmd_text = 'puppet config print all |grep manifestdir'
			result = ssh._runCmd(cmd_text, False)
			match = re.match("(manifestdir = {1})(.*)", result[0])
			if match:
				manifest_dir = match.group(2)
			# To prevent executing rm -rf * command if manifest_dir determination fails
			if manifest_dir.strip() <> '':
				rm_rf_manifest_dir_text = 'rm -rf ' + manifest_dir + '/*'
			for commands in ('service puppet stop', 'service landscaped stop', 'rm -rf /var/lib/landscape/*', rm_rf_manifest_dir_text, 'service landscaped start', 'service puppet start'):
				print('executing command: ' + commands)
				result = ssh._runCmd(commands, False)
				if result != []:
					result_list = ''.join(result)
					print(result_list.rstrip('\r\n'))
			ssh._sshDisconnect()
		timeStamp('landscaped_to_initial end')
	except Exception as exception:
		print('\nlandscaped_to_initial ERROR\n')
		handleException(exception)

def default_mb():
	luns_and_groups_delete()
	wwpn_deregister()
	nfs_shares_delete(True)

def clean_mb():
	puppet_ssl_node_clean()
	luns_and_groups_delete()
	wwpn_deregister()
	landscaped_to_initial()
	nfs_shares_delete(True)
	nfs_locks_clean()
	cobbler_clean()
	known_hosts_delete()
	etc_hosts_default()

def clean_sb():
	landscaped_to_initial()
	nfs_locks_clean()
	puppet_ssl_node_clean()
	virsh_clean()
	cobbler_clean()
	known_hosts_delete()
	etc_hosts_default()
		
def main():
	try:
		# Load configuration
		load_cfg()
		for argument in sys.argv:
			# Deletes the given shares
			if argument == 'nfs_shares_delete': nfs_shares_delete()
			# Deletes the given shares + filesystems
			if argument == 'nfs_delete': nfs_shares_delete(True)		
			# Deletes the given filesystems
			if argument == 'nfs_filesystem_destroy': nfs_filesystem_destroy()
			# Deletes the given luns and groups
			if argument == 'luns_and_groups_delete': luns_and_groups_delete()
			# Power down the given blades and deregisters all paths
			if argument == 'wwpn_deregister': wwpn_deregister()
			# Destroys and undefine all VM's, removes images and related data
			if argument == 'virsh_clean': virsh_clean()
			# Synchronizes the time on MWS with given server
			if argument == 'mws_time_sync': mws_time_sync()
			# Connects to the MWS and regenerate the ssl keys
			if argument == 'puppet_ssl_mws_clean': puppet_ssl_mws_clean()
			# Connects to the nodes and regenerates the ssl keys
			if argument == 'puppet_ssl_node_clean': puppet_ssl_node_clean()
			# Clear the cobbler contents
			if argument == 'cobbler_clean': cobbler_clean()
			# Removes ~/.ssh/known_hosts
			if argument == 'known_hosts_delete': known_hosts_delete()
			# Restores /etc/hosts to default status which have been saved by running this function in initial state
			if argument == 'etc_hosts_default': etc_hosts_default()
			# Removes locks for SFS shares
			if argument == 'nfs_locks_clean': nfs_locks_clean()
			# Brings landscaped service to initial state
			if argument == 'landscaped_to_initial': landscaped_to_initial()

			# Default MB
			if argument == 'defaultMB': default_mb()
				
			# Clean MB with already installed MWS
			if argument == 'cleanMB': clean_mb()
				
			# Clean SB with already installed MWS
			if argument == 'cleanSB': clean_sb()
				
	except Exception as exception:
		print('\nTHERE WAS AN ERROR\n')
		handleException(exception)


if __name__ == "__main__":
	main()
