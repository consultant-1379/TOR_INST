#!/usr/bin/python

import commands, paramiko, json, sys, re

newLunSize = 170    ### new boot device size in GB
currLunSize = 120   ### boot device default size is 120G for 13B - 1.0.17/3 systems
newPvSize = 173476  ### new physical volume size in MB
newVarSize = 50     ### new size of lv_var in GB
minPoolSize = 110   ### minimum VNX Pool size in GB
updateLandscape = 0 ### if 0 no need to update dbSize in LAST_KNOWN_CONFIG

def send_command(command):
  #print '    command:{0}'.format(command)
  (status, output) = commands.getstatusoutput(command)
  return [status, output]
  
def send_command_exit_error(command):
  #print '    command:{0}'.format(command)
  (status, output) = commands.getstatusoutput(command)
  if status:
    print 'Command failed: {0}'.format(command)	
    print '{0}'.format(status)
    sys.exit(1)  

def conn_exec_command(peer, command):
  #print '    command: {0}'.format(command)
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(peer)
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  ssh.close()	
  return [status, out, err, input]

def test_conn_to_sp(storeIPv4IP1, storeIPv4IP2, storeUser, storePassword, storeLoginScope):
  cmd_timeout = 10
  print '\n  => Checking connection to SPA'
  command = '/opt/Navisphere/bin/naviseccli -h {0} -User {1} -Password {2} -Scope {3} -Timeout {4} getsptime -spa'.format(storeIPv4IP1, storeUser, storePassword, storeLoginScope, cmd_timeout)
  result = send_command(command)
  if result[0]:
    print '    Cannot connect to SPA, trying SPB'
    command = '/opt/Navisphere/bin/naviseccli -h {0} -User {1} -Password {2} -Scope {3} -Timeout {4} getsptime -spb'.format(storeIPv4IP2, storeUser, storePassword, storeLoginScope, cmd_timeout)
    result = send_command(command)
    if result[0]:
      print '    Cannot connect to SPB either. Exiting'
      sys.exit(1)
    else:
      print '    Connection to SPB successful'	
      return storeIPv4IP2	  
  else:
    print '    Connection to SPA successful'
    return storeIPv4IP1

def check_pool_size(storeIP, storeUser, storePassword, storeLoginScope, sanPoolId):
  command = '/opt/Navisphere/bin/naviseccli -h {0} -User {1} -Password {2} -Scope {3} storagepool -list -id {4} -availableCap'.format(storeIP, storeUser, storePassword, storeLoginScope, sanPoolId)
  result = send_command(command)
  match = re.search(r'Available Capacity \(GBs\):\s+(\d+\.\d+)', result[1])
  availPoolSize = float(match.group(1))
  if availPoolSize > minPoolSize:
    print '\n  => Pool number {0} available capacity {1}G'.format(sanPoolId, availPoolSize)
    return 0
  else:
    return 1
	
def resize_san():
  global updateLandscape
  command = 'litp /inventory/deployment1/sanBase show -j'
  sanBaseJson = send_command(command)
  sanBaseDict = json.loads(sanBaseJson[1])
  storeSiteId = sanBaseDict['properties']['storeSiteId']
  storeLoginScope = sanBaseDict['properties']['storeLoginScope']
  storeUser = sanBaseDict['properties']['storeUser']
  storePassword = sanBaseDict['properties']['storePassword']
  storeIPv4IP2 = sanBaseDict['properties']['storeIPv4IP2']
  storeIPv4IP1 = sanBaseDict['properties']['storeIPv4IP1']
  storeIP = test_conn_to_sp(storeIPv4IP1, storeIPv4IP2, storeUser, storePassword, storeLoginScope)

  command = 'litp /inventory/deployment1/sanBase/bootvg show -j'
  sanPoolIdJson = send_command(command)
  sanPoolId = json.loads(sanPoolIdJson[1])['properties']['storePoolId']

  command = 'litp /inventory/deployment1/sanBase/bootvg show -lj'
  lunList = json.loads(send_command(command)[1])

  poolState  = 1
  poolState = check_pool_size(storeIP, storeUser, storePassword, storeLoginScope, sanPoolId)
  
  for lun in lunList:
    print '\n  => Resizing {0}'.format(lun)
    command = '/opt/Navisphere/bin/naviseccli -h {0} -User {1} -Password {2} -Scope {3} lun -list -name {4}'.format(storeIP, storeUser, storePassword, storeLoginScope, lun)
    result = send_command(command)
    match = re.search(r'User Capacity \(GBs\):\s+(\d+\.\d+)', result[1])
    lunSize = float(match.group(1))
    if lunSize < newLunSize and poolState == 0:
      print '    Current size of {0} is {1}G. The size of this LUN will be increase to {2}G'.format(lun, lunSize, newLunSize)
    elif lunSize < newLunSize and poolState == 1:
      print '    Not enough space in pool number {0} to resize {1}'.format(sanPoolId, lun)
      continue 	  
    elif lunSize == newLunSize:
      print '    Current size of {0} is already {1}G. No need to resize'.format(lun, newLunSize)
      continue  
    else:
	  print '    Incorrect LUN size {0}. Exiting'.format(lun)
	  sys.exit(1)
    command = '/opt/Navisphere/bin/naviseccli -h {0} -User {1} -Password {2} -Scope {3} lun -expand -name {4} -capacity {5} -sq gb -o'.format(storeIP, storeUser, storePassword, storeLoginScope, lun, newLunSize)
    result = send_command(command)
    if result[0]:
      print '  Unable to resize {0}'.format(lun)
      print '  ERROR:\n  {0}'.format(result[1])
      sys.exit(1)
    else:
      print '{0}'.format(result[1])
      print '    {0} has been resized successfully'.format(lun)
      updateLandscape = 1	  

def result_error_exit(peer, command):
  result = conn_exec_command(peer, command)
  if result[0]:
    print 'Command failed: {0}'.format(command)	
    print '{0}'.format(result[2])
    sys.exit(1)  

def rescan_dev(peer):
  print '\n  => Rescanning scsi disk devices on {0}'.format(peer) 
  command = 'multipath -ll boot_device'
  result = conn_exec_command(peer, command)
  matchSize = re.search(r'boot_device.*\nsize=(\d+)G', result[1])
  if int(matchSize.group(1)) == newLunSize:
    print '    No need to rescan devices'
    return 0
  devices = re.findall(r'.*\s(sd.)\s.*active ready running', result[1])
  for device in devices:
    command = 'echo 1 > /sys/block/{0}/device/rescan'.format(device)
    result_error_exit(peer, command)	
  for device in devices:
    command = 'multipathd -d del path {0}'.format(device)
    result_error_exit(peer, command) 
    command = 'multipathd -d add path {0}'.format(device)
    result_error_exit(peer, command)
  command = 'multipathd -d resize map boot_device' 
  result_error_exit(peer, command)
  command = 'multipath -ll boot_device'
  result = conn_exec_command(peer, command)
  matchSize = re.search(r'boot_device.*\nsize=(\d+)G', result[1])
  print '    boot_device size is {0}G'.format(matchSize.group(1))
  if int(matchSize.group(1)) == newLunSize:
    print '    Device rescan successful'  

def disk_partition(peer):
  print '\n  => Repartitioning boot_device on {0}'.format(peer)
  command = 'multipath -ll boot_device'
  result = conn_exec_command(peer, command)
  matchSize = re.search(r'.*\s(sd.)\s.*active ready running', result[1])
  diskDevice = matchSize.group(1)
  command = 'parted /dev/{0} print'.format(diskDevice)
  result = conn_exec_command(peer, command)
  matchPartSize = re.search(r'2\s+\d+MB\s+\d+GB\s+(\d+)GB.+primary\s+\lvm', result[1])
  partSize = matchPartSize.group(1)
  if int(partSize) >= 182:
    print '    /dev/{0} already partitioned correctly'.format(diskDevice)
    return 0
  command = 'parted /dev/{0} unit s print'.format(diskDevice)
  result = conn_exec_command(peer, command)
  matchPartStart = re.search(r'2\s+(\d+s)\s+.+primary\s+\lvm', result[1])
  partStart = matchPartStart.group(1)
  command = 'parted /dev/{0} rm 2'.format(diskDevice)
  result = conn_exec_command(peer, command)
  if result[0]:
    print result[1]
  command = 'parted /dev/{0} mkpart primary {1} 100%'.format(diskDevice, partStart)
  result = conn_exec_command(peer, command)
  if result[0]:
    print result[1]
  command = 'parted /dev/{0} set 2 lvm on'.format(diskDevice)
  result = conn_exec_command(peer, command)
  if result[0]:
    print result[1]
  command = 'partprobe /dev/{0}'.format(diskDevice)
  result = conn_exec_command(peer, command)
  if result[0]:
    print result[1]  
  print '    {0} /dev/{1} repartitioned successfully'.format(peer, diskDevice)

def install_parted(peer):
  print '\n  => Installing parted.x86_64 rpm on {0}'.format(peer)
  command = 'yum list installed parted.x86_64'
  result = conn_exec_command(peer, command)
  if result[0]:
    command = 'yum -y install parted.x86_64'	
    result_error_exit(peer, command)
    print '    parted.x86_64 installed successfully'
  else:
    print '    parted.x86_64 already installed'      

def resize_pv_lv_fs(peer):
  command = 'lvs vg_root'	
  result = conn_exec_command(peer, command)
  matchLvSize = re.search(r'lv_var.+\s+(\d+\.\d+)g', result[1])
  currentLvSize = float(matchLvSize.group(1))
  if currentLvSize == newVarSize:
    print '\n    No need to resize lv_var on {0}. Current size is {1}'.format(peer, currentLvSize)
    return 0	
  print '\n  => Resizing physical volume on {0}'.format(peer)
  command = 'pvs --units m'
  result = conn_exec_command(peer, command)
  matchPvSize = re.search(r'boot_device.+\s+(\d+\.\d+)m\s+\d+\.\d+m', result[1])
  currentPvSize = float(matchPvSize.group(1))
  if currentPvSize < newPvSize:
    command = 'pvresize --setphysicalvolumesize {0}m /dev/mapper/boot_devicep2'.format(newPvSize)
    print '    Setting /dev/mapper/boot_devicep2 size to {0}m'.format(newPvSize)
    result_error_exit(peer, command)
    print '    PV resized successfully'
    print '\n  => Extending {0} lv_var volume to {1}G'.format(peer, newVarSize)
    command = 'lvs vg_root'	
    result = conn_exec_command(peer, command)
    matchLvSize = re.search(r'lv_var.+\s+(\d+\.\d+)g', result[1])
    currentLvSize = float(matchLvSize.group(1))	
    extendLvSize = newVarSize - currentLvSize
    if extendLvSize > 0:	
      command = 'lvextend -L+{0}G /dev/vg_root/lv_var'.format(extendLvSize) 
      result_error_exit(peer, command)
      print '    The lv_var extended to {0}G'.format(newVarSize)
      print '\n  => Resizing /dev/vg_root/lv_var file system on {0}'.format(peer)
      command = 'resize2fs /dev/vg_root/lv_var' 
      result_error_exit(peer, command)
      print '    File system resized successfully on {0}'.format(peer)	  

def check_lvm_snapshot(peer):
  print '\n  => Check there\'s no LVM snapshots created'
  command = 'lvs -o lv_attr'
  result = conn_exec_command(peer, command)
  match = re.findall(r'\s+s.+', result[1])
  if match:
    print '    LVM snapshots exist on {0}. Delete Snapshots before resizing LUNs and volumes'.format(peer)
    sys.exit(1)

def update_inventory():
  print '\n  => Updating inventory with new boot_device size value'
  command = 'litp /inventory/deployment1/sanBase/bootvg update storeBlockDeviceDefaultSize={0}G'.format(newLunSize)
  send_command_exit_error(command)
  command = 'litp /inventory/deployment1/sanBase/bootvg show -lj'
  lunList = json.loads(send_command(command)[1])
  for lun in lunList:
    command = 'litp /inventory/deployment1/sanBase/bootvg/{0} update size={1}G'.format(lun, newLunSize)
    send_command_exit_error(command)
  command = 'litp /inventory/deployment1/cluster1/sc1/control_1/os/boot_blockdevice update size={0}G'.format(newLunSize)
  send_command_exit_error(command)
  command = 'litp /inventory/deployment1/cluster1/sc2/control_2/os/boot_blockdevice update size={0}G'.format(newLunSize)
  send_command_exit_error(command)
  command = 'litp /inventory/deployment1/cluster1/sc1/control_1/os/lvm/lv_var update size={0}G'.format(newVarSize)
  send_command_exit_error(command)
  command = 'litp /inventory/deployment1/cluster1/sc1/control_1/os/lvm configure'
  send_command_exit_error(command)
  command = 'litp /cfgmgr apply scope=/inventory/deployment1/cluster1/sc1/control_1/os/lvm'
  send_command_exit_error(command)
  command = 'litp /inventory/deployment1/cluster1/sc2/control_2/os/lvm/lv_var update size={0}G'.format(newVarSize)
  send_command_exit_error(command)
  command = 'litp /inventory/deployment1/cluster1/sc2/control_2/os/lvm configure'
  send_command_exit_error(command)
  command = 'litp /cfgmgr apply scope=/inventory/deployment1/cluster1/sc2/control_2/os/lvm'
  send_command_exit_error(command)
  print '    Inventory updated successfully'

def update_landscape():
  global updateLandscape
  if updateLandscape == 0:
    print '\n    No need to update LAST_KNOWN_CONFIG with new bdSize'
    return 0	
  print '\n  => Updating landscape configuration'
  print '    Backing up LAST_KNOWN_CONFIG to /var/tmp/LAST_KNOWN_CONFIG_var_resize'
  command = 'service landscaped stop'
  send_command_exit_error(command)
  command = '/bin/cp /var/lib/landscape/LAST_KNOWN_CONFIG /var/tmp/LAST_KNOWN_CONFIG_var_resize'
  send_command_exit_error(command)
  print '    Updating bdSize for bootvg_1 and bootvg_2'
  f = open('/var/lib/landscape/LAST_KNOWN_CONFIG', 'r')
  f_string = f.read()
  f.close()
  newString = '\g<1>{0}\g<2>'.format(newLunSize)
  f_string = re.sub('(\s+"bdName": "bootvg_[12]",\s+\n\s+"bdSize": ")\d+(G",)', newString, f_string)
  f = open('/var/lib/landscape/LAST_KNOWN_CONFIG', 'w')
  f.write(f_string)
  f.close()
  command = 'service landscaped start'
  send_command_exit_error(command)
  print '    Landscape configuration updated'  
  	  
def main():
  check_lvm_snapshot('sc-1')
  check_lvm_snapshot('sc-2')
  install_parted('sc-1')
  install_parted('sc-2')
  resize_san()
  update_landscape()
  rescan_dev('sc-1')
  rescan_dev('sc-2')
  disk_partition('sc-1')
  disk_partition('sc-2')
  resize_pv_lv_fs('sc-1')
  resize_pv_lv_fs('sc-2')
  update_inventory()
  print '\n    Script executed successfully'
  sys.exit(0)

if __name__ == '__main__':
  main()
