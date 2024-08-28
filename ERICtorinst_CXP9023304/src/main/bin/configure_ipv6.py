#!/usr/bin/python

import commands, paramiko, sys, re, time, fileinput, os, logging

def send_command(log, command):
  msg = '{0}'.format(command)
  log.debug(msg)
  (status, output) = commands.getstatusoutput(command)
  return [status, output]

def if_ipv6_exists_delete(log, sc_num):
  msg = 'If exists remove current IPv6 sc-{0} configuration from definition and inventory'.format(sc_num)
  log.debug(msg)
  commands = ['litp /definition/os/ossc/fw_sc{0}_ipv6_global {1}',
    'litp /inventory/deployment1/cluster1/sc{0}/ipv6 {1}',
    'litp /inventory/deployment1/ipv6_pool/sc{0}_ipv6 {1}',
    'litp /inventory/deployment1/cluster1/sc{0}/control_{0}/os/fw_sc1_ipv6_global {1}',
    'litp /inventory/deployment1/cluster1/sc{0}/control_{0}/os/fw_sc2_ipv6_global {1}',
	'litp /inventory/deployment1/alias_sc{0}_ipv6 {1}',
	'litp /inventory/deployment1/alias_sc{0}_ipv6 {1}']	
  for command in commands:
    rc = send_command(log, command.format(sc_num, 'show'))
    if rc[0] == 0:
      rc = send_command(log, command.format(sc_num, 'delete -f'))
      if rc[0]:
        print rc[1]
        sys.exit(1)		

def materialise_conf_apply(log):
  commands = ['litp /definition materialise',
    'litp /inventory configure',
    'litp /cfgmgr apply scope=/inventory']
  for command in commands:
    rc = send_command(log, command)
    if rc[0]:
      print rc[1]
      sys.exit(1)	  

def count_applying():
  command = "litp /inventory/ show -rp | grep Applying | grep -vE '^\[|ericmon_config|cmw_cluster_config' | wc -l"
  rc = commands.getstatusoutput(command)
  if rc[0]:
    print rc[1]
    sys.exit(1) 
  return int(rc[1])

def wait_to_get_applied(log):
  while True:
    current_applying_num = count_applying()
    if current_applying_num == 0:
      msg = 'Configuration has been applied successfully'
      log.debug(msg)	  
      return 0
    else:
      msg = 'New configuration is being applied to /inventory. {0} items still applying...'.format(current_applying_num)
      log.debug(msg)
      time.sleep(45)

def configure_ipv6_landscape(log, sc_num, sed_data):
  msg = 'Configure definition and inventory with IPv6 sc-{0} data'.format(sc_num)
  log.debug(msg)
  node_ipv6 = sed_data['node{0}_IPv6'.format(sc_num)]
  ipv6subnet = sed_data['TORIPv6_subnet']
  ipv6gateway = sed_data['TORservices_IPv6gateway']
  node_hostname = sed_data['node{0}_hostname'.format(sc_num)]
  commands = ['litp /definition/os/ossc/fw_sc{0}_ipv6_global create firewalls-def \
name="48 sc{0} ipv6 global link" source={1} provider="ip6tables" proto=all'.format(sc_num, node_ipv6),
    'litp /inventory/deployment1/ipv6_pool/sc{0}_ipv6 create ipv6-address address={1} \
subnet={2} gateway={3} net_name=TORservices'.format(sc_num, node_ipv6, ipv6subnet, ipv6gateway),
    'litp /inventory/deployment1/ipv6_pool/sc{0}_ipv6 enable'.format(sc_num),
    'litp /inventory/deployment1/cluster1/sc{0}/ipv6 create ipv6-address pool=ipv6_pool net_name=TORservices'.format(sc_num),
    'litp /inventory/deployment1/cluster1/sc{0}/ipv6 allocate'.format(sc_num),
    'litp /inventory/deployment1/alias_sc{0}_ipv6 create svc-alias ip={1} aliases={2}-v6'.format(sc_num, node_ipv6, node_hostname)]
  for command in commands:
    rc = send_command(log, command)
    if rc[0]:
      print rc[1]
      sys.exit(1)
	
def get_value(sed_file, variable_list):
  var_value = {}
  f = open(sed_file, 'rU')
  file_string = f.read()
  f.close()
  for var in variable_list:
    match = re.search(var + '=(.+)\s+', file_string)
    var_value[var] = match.group(1)	
  return var_value

def stop_puppet_peer(log, sc_num):
  peer = 'sc-{0}'.format(sc_num)
  msg = 'Stop puppet agent on {0}...'.format(peer)
  log.debug(msg)
  command = 'service puppet stop; pkill -9 puppetd; rm /var/run/puppet/agent.pid /var/lock/subsys/puppet'
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(peer)
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  ssh.close()

def flush_ip6tables_peer(log, sc_num):
  peer = 'sc-{0}'.format(sc_num)
  msg = 'Flushing ip6tables on {0}...'.format(peer)
  log.debug(msg)
  command = 'ip6tables --flush'
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(peer)
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  if status:
    log.debug(err)	
    sys.exit(1)
  ssh.close()	  

def add_ipv6_to_ifcfg_bond(log, sc_num, sed_data):
  msg = 'Update ifcfg-bond0 config file on sc-{0}'.format(sc_num)
  log.debug(msg)
  peer = 'sc-{0}'.format(sc_num)
  ipv6_defaultgw = sed_data['TORservices_IPv6gateway']
  ipv6addr = sed_data['node{0}_IPv6'.format(sc_num)]
  ipv6init = 'yes'
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(peer)
  sftp = ssh.open_sftp()
  sftp.get('/etc/sysconfig/network-scripts/ifcfg-bond0', 'ifcfg-bond0')
  for line in fileinput.input('ifcfg-bond0', inplace=1):
    if 'IPV6' in line:
      continue
    else:
      print line,
  for line in fileinput.input('ifcfg-bond0', inplace=1):
    print line,
    if line.startswith('DEVICE'):
      print 'IPV6_DEFAULTGW={0}'.format(ipv6_defaultgw)
      print 'IPV6ADDR={0}'.format(ipv6addr)
      print 'IPV6INIT={0}'.format(ipv6init)	
  sftp.put('ifcfg-bond0', '/etc/sysconfig/network-scripts/ifcfg-bond0')	  
  sftp.close()
  ssh.close()
  if os.path.isfile('ifcfg-bond0'):
    os.remove('ifcfg-bond0')

def config_ipv6_peer(log, sc_num, sed_data):
  peer = 'sc-{0}'.format(sc_num)
  msg = 'Configure IPv6 on {0}'.format(peer) 
  log.debug(msg)  
  ipv6_defaultgw = sed_data['TORservices_IPv6gateway']
  ipv6addr = sed_data['node{0}_IPv6'.format(sc_num)]
  ipv6subnet = sed_data['TORIPv6_subnet']
  match = re.search(r'.+/(.+)', ipv6subnet)
  ipv6prefix = match.group(1)
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(peer) 
  command = 'ifconfig bond0'  
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  match = re.search(r'inet6 addr:\s(.+)\sScope:Global', out)
  if match:
    msg = 'Removing currently defined global link address {0} on {1}'.format(match.group(1), peer)
    log.debug(msg)	
    command = 'ip -6 addr del {0} dev bond0'.format(match.group(1))
    stdin, stdout, stderr = ssh.exec_command(command)
    status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
    if status:
      log.debug(err)	
      sys.exit(1)	  
  command = 'ip -6 route | grep default'  
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  match = re.search(r'default via\s(.+)\sdev bond0', out)
  if match:
    msg = 'Removing currently defined default route {0} on {1}'.format(match.group(1), peer)
    log.debug(msg)	
    command = 'ip -6 route del default'
    stdin, stdout, stderr = ssh.exec_command(command)
    status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
    if status:
      log.debug(err)	
      sys.exit(1)
  msg = 'Configuring IPv6 global link address {0} on {1}'.format(ipv6addr, peer)
  log.debug(msg)
  command = 'ip -6 addr add {0}/{1} dev bond0'.format(ipv6addr, ipv6prefix)
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  if status:
    log.debug(err) 
    sys.exit(1)
  msg = 'Configuring IPv6 default route {0} on {1}'.format(ipv6_defaultgw, peer)
  log.debug(msg)
  command = 'ip -6 route add default via {0}'.format(ipv6_defaultgw)
  stdin, stdout, stderr = ssh.exec_command(command)
  status, out, err = stdout.channel.recv_exit_status(), stdout.read(), stderr.read()
  if status:
    log.debug(err)	
    sys.exit(1)
  ssh.close()

def function_logger():
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)
  log_paramiko = logging.getLogger('paramiko')
  log_paramiko.setLevel(logging.ERROR)

  ch = logging.StreamHandler()
  ch.setLevel(logging.DEBUG)
  ch_format = logging.Formatter('%(asctime)s - %(message)s', datefmt='%b %d %H:%M:%S')
  ch.setFormatter(ch_format)
  logger.addHandler(ch)

  if os.path.isfile('/var/log/torinst/configure_ipv6.log'):
    os.rename('/var/log/torinst/configure_ipv6.log', '/var/log/torinst/configure_ipv6.log_{0}'.format(time.strftime('%Y%m%d_%H%M%S')))	
  fh = logging.FileHandler('/var/log/torinst/configure_ipv6.log')
  fh.setLevel(logging.DEBUG)
  fh_format = logging.Formatter('%(asctime)s - %(message)s', datefmt='%b %d %H:%M:%S')
  fh.setFormatter(fh_format)
  logger.addHandler(fh)
  
  return logger
	
def main():
  if len(sys.argv) != 2:
    print 'usage: {0} SITE_DATA'.format(sys.argv[0])
    sys.exit(1)
  sed_file = sys.argv[1]
  log = function_logger()
  log.info('*** Start script execution ***')
  try:
    sed_data = get_value(sed_file, ['node1_IPv6', 'node2_IPv6', 'TORIPv6_subnet', 'TORservices_IPv6gateway', 'node1_hostname', 'node2_hostname'])
    stop_puppet_peer(log, 1)
    stop_puppet_peer(log, 2)
    flush_ip6tables_peer(log, 1)
    flush_ip6tables_peer(log, 2)	
    config_ipv6_peer(log, 1, sed_data)
    config_ipv6_peer(log, 2, sed_data)	
    add_ipv6_to_ifcfg_bond(log, 1, sed_data)
    add_ipv6_to_ifcfg_bond(log, 2, sed_data)
	
    if_ipv6_exists_delete(log, 1)
    if_ipv6_exists_delete(log, 2)
    configure_ipv6_landscape(log, 1, sed_data)
    configure_ipv6_landscape(log, 2, sed_data)
    materialise_conf_apply(log)
    wait_to_get_applied(log)
  except Exception, e:
    log.error('ERROR:', exc_info=True)
	
  sys.exit(0)
  
if __name__ == '__main__':
  main()