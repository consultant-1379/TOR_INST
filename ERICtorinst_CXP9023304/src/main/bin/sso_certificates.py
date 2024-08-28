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
openssl = '/usr/bin/openssl'
pkiadmin = '/opt/ericsson/cadm/bin/pkiAdmin'
sso_dir = '/opt/ericsson/nms/litp/etc/puppet/modules/cmw/files/certificates/sso'
ssl_config = '/opt/ericsson/torinst/etc/sslconfig.cnf'
ds_cert = '/opt/ericsson/csa/certs/DSCertCA.pem'
mgmt_cert = '/opt/ericsson/csa/certs/TORMgmtRootCA.pem'

def send_command(command):
  (status, output) = commands.getstatusoutput(command)
  if status:
    raise IOError(output)
  else: 
    print output

def ftp_file(ip, pw, remotefile, localfile, op = 'get'):
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username="root", password=pw)
  ftp = ssh.open_sftp() 
  if op == 'get':
    ftp.get(remotefile, localfile) 
  if op == 'put':
    ftp.put(localfile, remotefile)  
  ftp.close()
  ssh.close()  

def create_dir(sso_dir):
  result = os.path.exists(sso_dir)
  if result:
    shutil.rmtree(sso_dir)
  send_command('mkdir -p ' + sso_dir)	

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

def openssl_req_key(cn):
  cert_list = {'ssoserverapache': cn , 'ssoserverjboss': 'sso.' + cn}
  for cert in cert_list:
    print '\n=> Generating Certificate Signing Request and Private Key for {0}'.format(cert)
    command = openssl + ' req -nodes -sha256 -newkey rsa:2048 -keyout ' + sso_dir + '/' + cert + '.key -out ' + sso_dir + '/' + cert + '.csr -subj \"/O=Ericsson/OU=ericssonTOR=/CN=' + cert_list[cert] + '\" -extensions v3_ca_req -config ' + ssl_config 
    print command
    send_command(command)

def check_cert_exist(ip, pw, signing_auth, cn):
  command = pkiadmin + ' cred torsbi list'
  print '=> Listing already generated {0} certificates'.format(signing_auth)
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, username="root", password=pw)
  stdin, stdout, stderr = ssh.exec_command(pkiadmin + ' cred ' + signing_auth +' list')
  cert_list = stdout.read()
  print cert_list
  match = re.search(signing_auth + '\s+' + cn + '\s+', cert_list)
  if match:
    print '=> Certificate already generated for the user {0}/{1}'.format(signing_auth, cn)
    print '=> Revoking certificate {0}'.format(cn)
    stdin, stdout, stderr = ssh.exec_command(pkiadmin + ' cred ' + signing_auth + ' revoke -cn ' + cn + ' -reason 1')
    print stdout.read()
    print stderr.read()	
  match = re.search(signing_auth + '\s+sso\.' + cn + '\s+', cert_list)
  if match:
    print '=> Certificate already generated for the user {0}/sso.{1}'.format(signing_auth, cn)
    print '=> Revoking certificate sso.{0}'.format(cn)
    stdin, stdout, stderr = ssh.exec_command(pkiadmin + ' cred ' + signing_auth + ' revoke -cn sso.' + cn + ' -reason 1')
    print stdout.read()
    print stderr.read()	
  ssh.close()

def sign_cert_request(ip, pw, signing_auth, cert_req_name, cn):
  command = 'ssh -oStrictHostKeyChecking=no root@' + ip
  print '=> Loggin to OMSAS server'
  p = pexpect.spawn(command)
  p.expect('Password:')
  #print p.after
  p.sendline(pw)
  p.expect('#')
  #print p.after
  print '=> Signing certificate request for {0}'.format(cert_req_name)
  p.sendline(pkiadmin + ' cred ' + signing_auth + ' generate -csr /var/tmp/' + cert_req_name + '.csr -out /var/tmp/' + cert_req_name + '.crt')
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
    print '\n  If you see a message...'
    print '    Generate is not applicable. Certificate already generated for the user: {0}/{1}'.format(signing_auth, cn)
    print '  Follow the procedure:\n\n'  
    print '  1. Login to OMSAS and revoke the certificate for particular deployment. On the OMSAS execute commands.'
    print '    # /opt/ericsson/cadm/bin/pkiAdmin cred {0} list'.format(signing_auth)
    print '    # /opt/ericsson/cadm/bin/pkiAdmin cred {0} revoke -cn {1} -reason 1'.format(signing_auth, cn)
    print '  2. Run the following command again to generate certificates:'
    print '    # /opt/ericsson/torinst/bin/fm_certificates.py <omsas_ip_address> <site_data>\n'
    sys.exit(1)
  p.sendline('exit')
  
def main():
  if len(sys.argv) != 2:
  	  print 'usage: ./sso_certificates.py <Site Engineering Document> '
          print 'legth sys.argv'+ len(sys.argv)
	  sys.exit(1)

  site_data = sys.argv[1]
  omsas_ip =  get_value(site_data, 'ip_OMSAS')
  print omsas_ip
  print site_data
  print 'Enter OMSAS root password.'
  omsas_pw = getpass.getpass('Password: ')
  cn = get_value(site_data, 'httpd_fqdn')
  create_dir(sso_dir)
  openssl_req_key(cn)
  check_cert_exist(omsas_ip, omsas_pw, 'tormgmt', cn)
  print '=> Uploading certificate requests to OMSAS'
  ftp_file(omsas_ip, omsas_pw, '/var/tmp/ssoserverapache.csr', sso_dir + '/ssoserverapache.csr', 'put')
  ftp_file(omsas_ip, omsas_pw, '/var/tmp/ssoserverjboss.csr', sso_dir + '/ssoserverjboss.csr', 'put')
  sign_cert_request(omsas_ip, omsas_pw, 'tormgmt', 'ssoserverapache', cn)
  sign_cert_request(omsas_ip, omsas_pw, 'tormgmt', 'ssoserverjboss', 'sso.' + cn)
  print '=> Transferring certificates from OMSAS to MS'
  ftp_file(omsas_ip, omsas_pw, '/var/tmp/ssoserverapache.crt', sso_dir + '/ssoserverapache.crt')
  ftp_file(omsas_ip, omsas_pw, '/var/tmp/ssoserverjboss.crt', sso_dir + '/ssoserverjboss.crt')
  ftp_file(omsas_ip, omsas_pw, mgmt_cert, sso_dir + '/mgmtrootca.cer')
  ftp_file(omsas_ip, omsas_pw, ds_cert, sso_dir + '/rootca.cer')
  send_command('rm -f ' + sso_dir + '/*.csr')
  send_command('chmod 644 ' + sso_dir + '/*')
  print '=> Certificates location on MS -> {0}'.format(sso_dir)
  print '\n  Certificates have been installed successfully\n'
  sys.exit(0)  
    
if __name__ == '__main__':
  main()
