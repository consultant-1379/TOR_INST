#!/usr/bin/python
  
import commands
import sys
import paramiko
import pexpect
import re
import os
import shutil
import getpass

keytool = '/usr/java/default/bin/keytool'
pkiadmin = '/opt/ericsson/cadm/bin/pkiAdmin'
fm_dir = '/opt/ericsson/nms/litp/etc/puppet/modules/cmw/files/certificates/fm'

def create_fm_dir():
  result = os.path.exists(fm_dir)
  if result:
    shutil.rmtree(fm_dir)
  send_command('mkdir -p ' + fm_dir)	
  
def download_certificates(ip, pw):
  command = "cat /ericsson/sdee/ldap_domain_settings/*.default_domain | grep MS_HOSTNAME"
  cert_dir = '/opt/ericsson/csa/certs/'
  
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username="root", password=pw)
  stdin, stdout, stderr = ssh.exec_command(command)
  data = stdout.readline()
  if not data:
    print '=> Not possible to get MS_HOSTNAME from /ericsson/sdee/ldap_domain_settings/<ldap_domain_name>.default_domain file'
    sys.exit(1)	
  ms_hostname = re.search(r'MS_HOSTNAME=(.+)', data)
  print '=> MS_HOSTNAME => {0}'.format(ms_hostname.group(1))
  ftp = ssh.open_sftp() 
  ftp.get(cert_dir + ms_hostname.group(1) + 'RootCA.pem', fm_dir + '/' + ms_hostname.group(1) + 'RootCA.pem')
  ftp.get(cert_dir + ms_hostname.group(1) + 'TORSbiCA.pem', fm_dir + '/' + ms_hostname.group(1) + 'TORSbiCA.pem')
  ftp.get(cert_dir + ms_hostname.group(1) + 'NECertCA.pem', fm_dir + '/' + ms_hostname.group(1) + 'NECertCA.pem')
  ftp.close()
  ssh.close()
  print '=> Following certificates were downloaded from OMSAS:'
  print '  =>  {0}RootCA.pem'.format(ms_hostname.group(1))
  print '  =>  {0}TORSbiCA.pem'.format(ms_hostname.group(1))
  print '  =>  {0}NECertCA.pem'.format(ms_hostname.group(1))
  return ms_hostname.group(1)

def gen_ks_priv_key(deploy_name):
  print '=> Generating a keystore with a private key'
  command = keytool + ' -genkey -v -alias ' + deploy_name + '_corba_sec -validity 1800 -keyalg RSA -keysize 2048 -keystore ' + fm_dir + '/fm.keystore -storepass changeit -keypass changeit -dname ' + '\"CN=' + deploy_name + '_FM, OU=EricssonOAM, O=Ericsson, L=bentdura, S=linkoping, C=SW\"'
  print command
  (status, output) = commands.getstatusoutput(keytool + ' -genkey -v -alias ' + deploy_name + '_corba_sec -validity 1800 -keyalg RSA -keysize 2048 -keystore ' + fm_dir + '/fm.keystore -storepass changeit -keypass changeit -dname ' + '\"CN=' + deploy_name + '_FM, OU=EricssonOAM, O=Ericsson, L=bentdura, S=linkoping, C=SW\"')
  if status:
    raise IOError(output)
  else:
    print output



def get_value(site_data, variable_name):
  f = open(site_data, 'rU')
  value = 0
  for line in f:
    match = re.search(variable_name + '=(.+)', line)
    if match:
      value = match.group(1)
  f.close()
  if not value:
    print '=> Missing parameter {0} in SiteEngineering document'.format(variable_name)
    print '=> Update SiteEngineering document and execute this script again'
    sys.exit(1)
  return value







def check_torsbi_exists(ip, pw, deploy_name):
  command = pkiadmin + ' cred torsbi list'
  print '=> Listing already generated torsbi certificates'
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username="root", password=pw)
  stdin, stdout, stderr = ssh.exec_command(pkiadmin + ' cred torsbi list')
  cert_list = stdout.read()
  print cert_list
  match = re.search(r'torsbi\s+' + deploy_name + '_FM\s+', cert_list)
  if match:
    print '=> Certificate already generated for the user torsbi/{0}_FM'.format(deploy_name)
    print '=> Revoking certificate {0}_FM'.format(deploy_name)
    stdin, stdout, stderr = ssh.exec_command(pkiadmin + ' cred torsbi revoke -cn ' + deploy_name + '_FM -reason 1')
    print stdout.read()
    print stderr.read()	
  ssh.close()

def import_keys_into_ks(deploy_name, MS_HOSTNAME):
  alias_list = ['root_ca', 'tor_sbi_ca', 'ne_cert_ca', deploy_name + '_corba_sec']
  alias_certfile = {'root_ca': MS_HOSTNAME + 'RootCA.pem', 'tor_sbi_ca': MS_HOSTNAME + 'TORSbiCA.pem', 'ne_cert_ca': MS_HOSTNAME + 'NECertCA.pem', deploy_name + '_corba_sec': 'fm.crt'}
  print '=> Importing certificates into a keystore'
  for alias in alias_list:
    command = keytool + ' -noprompt -importcert -alias ' + alias + ' -storepass changeit -file ' + fm_dir + '/' + alias_certfile[alias] + ' -keystore ' + fm_dir + '/fm.keystore'
    print command
    (status, output) = commands.getstatusoutput(command)
    if status:
      raise IOError(output)
    else:
      print output
      os.unlink(fm_dir + '/' + alias_certfile[alias])	  
  
def cert_request(deploy_name):
  print '=> Generating certificate request'
  command = keytool + ' -noprompt -v -certreq -alias ' + deploy_name + '_corba_sec -storepass changeit -sigalg sha256WithRSA -keystore ' + fm_dir + '/fm.keystore -keypass changeit -file ' + fm_dir + '/fm.csr'
  print command
  (status, output) = commands.getstatusoutput(command)
  if status:
    raise IOError(output)
  else:
    print output 
  
def upload_csr_to_omsas(ip, pw):
  localfile = '/opt/ericsson/nms/litp/etc/puppet/modules/cmw/files/certificates/fm/fm.csr'
  remotefile = '/var/tmp/fm.csr'

  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username="root", password=pw)
  ftp = ssh.open_sftp() 
  ftp.put(localfile, remotefile) 
  ftp.close()
  ssh.close()
  print '=> Certificate request uploaded to OMSAS'
  
def gen_torsbi_cert(ip, pw, deploy_name):
  command = 'ssh -oStrictHostKeyChecking=no root@' + ip
  print '=> Loggin to OMSAS server'
  p = pexpect.spawn(command)
  p.expect('Password:')
  #print p.after
  p.sendline(pw)
  p.expect('#')
  #print p.after
  print '=> Generating a new certificate for the user torsbi/{0}_FM'.format(deploy_name)
  p.sendline(pkiadmin + ' cred torsbi generate -csr /var/tmp/fm.csr -out /var/tmp/fm.crt')
  p.expect('Are these values ok\? \[Y\]/N:')
  print p.before
  print p.after
  p.sendline('Y')
  index = p.expect(['Certificate was generated successfully:', pexpect.TIMEOUT])
  if index == 0:
    print p.before
    print p.after
  elif index == 1:
    print p.before
    print """
    If you see message 
    "Generate is not applicable. Certificate already generated for the user: torsbi/<deployment_name>_FM"
    follow the procedure:
	2. Login to OMSAS and revoke the certificate for particular deployment. On the OMSAS execute commands.
     # /opt/ericsson/cadm/bin/pkiAdmin cred torsbi list 
     # /opt/ericsson/cadm/bin/pkiAdmin cred torsbi revoke -cn <<deployment_name>>_FM -reason 1
    3. Run the following command again to generate certificates:
	   /opt/ericsson/torinst/bin/fm_certificates.py <omsas_ip_address> <deployment_name>      
		  """
    sys.exit(1)
  p.sendline('exit')
  
def get_cert(ip, pw):
  remotefile = '/var/tmp/fm.crt'
  localfile = fm_dir + '/fm.crt'
  
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username="root", password=pw)
  
  ftp = ssh.open_sftp() 
  ftp.get(remotefile, localfile) 
  ftp.close()
  ssh.close()
  print '=> fm.crt downloaded successfully' 
  
def send_command(command):
  (status, output) = commands.getstatusoutput(command)
  if status:
    raise IOError(output)

def main():
  if len(sys.argv) != 2:
    print 'usage: ./fm_certificates.py <Site Engineering Document>'
    sys.exit(1)

  site_data = sys.argv[1]
  omsas_ip = get_value(site_data, 'ip_OMSAS')
  print omsas_ip
  deploy_name = get_value(site_data, 'IDENTIFIER')
  print deploy_name
  print 'Enter OMSAS root password.'
  password = getpass.getpass('Password: ')
  create_fm_dir()
  MS_HOSTNAME = download_certificates(omsas_ip, password)
  gen_ks_priv_key(deploy_name)
  cert_request(deploy_name)
  upload_csr_to_omsas(omsas_ip, password)
  check_torsbi_exists(omsas_ip, password, deploy_name)
  gen_torsbi_cert(omsas_ip, password, deploy_name)
  get_cert(omsas_ip, password)
  import_keys_into_ks(deploy_name, MS_HOSTNAME)
  send_command('rm -f ' + fm_dir + '/fm.csr')
  send_command('chmod 644 ' + fm_dir + '/*')
  print '=> The fm.keystore location on MS -> {0}'.format(fm_dir)
  print '\n  Certificates have been installed successfully\n'
  sys.exit(0)
  
if __name__ == '__main__':
  main()
