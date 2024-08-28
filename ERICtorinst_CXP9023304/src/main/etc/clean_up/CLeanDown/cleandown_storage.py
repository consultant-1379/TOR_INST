#!/usr/bin/env python
from ConfigParser import ConfigParser
from optparse import OptionParser
from socket import gethostbyaddr
from sys import argv, stdout
from util.SFS import SFS


def create_cleandown_export(sfs_pool, console_ip, console_user, console_password):
	ini = ConfigParser()
	# Keep the keys at the same case.
	ini.optionxform = str
	ini.add_section('SFS')
	ini.set('SFS', 'address', console_ip)
	ini.set('SFS', 'username', console_user)
	ini.set('SFS', 'password', console_password)

	sfs = SFS()
	sfs.init(console_ip, username, password)
	pools = sfs.storage_pool_list()
	if sfs_pool not in pools:
		print('No SFS pool called \'{0}\' exists.'.format(sfs_pool))
		exit(1)
	pool_filesystems = sfs.storage_fs_list(pool_name=sfs_pool)
	share_clients = sfs.nfs_share_show(pool_name=sfs_pool)
	ini.add_section('SFS_FILESYSTEMS')
	for fsname, details in pool_filesystems.items():
		if fsname.startswith('%s-' % sfs_pool):
			ini.set('SFS_FILESYSTEMS', fsname, '')
	ini.add_section('SFS_SHARE_CLIENTS')
	for client, paths in share_clients.items():
		ini.set('SFS_SHARE_CLIENTS', client, '')
		for share_path in paths:
			ini.set('SFS_FILESYSTEMS', share_path['name'], share_path['path'])
	ini_file = 'C:/ftp_transfers/ENV1 (Multi Enclosure Deployment 1)/storage.ini'
	with open(ini_file, 'wb') as configfile:
		ini.write(configfile)


def list_storage(sfs_pool, console_ip, username, password):
	print('SFS Pool \'{0}\' details on {1}'.format(sfs_pool, console_hostname))
	sfs = SFS()
	sfs.init(console_ip, username, password)
	pools = sfs.storage_pool_list()
	if sfs_pool not in pools:
		print('No SFS pool called \'{0}\' exists.'.format(sfs_pool))
		exit(1)
	pool_filesystems = sfs.storage_fs_list(pool_name=sfs_pool)
	pool_shares = sfs.nfs_share_show(pool_name=sfs_pool)
	pool_snapshots = sfs.storage_rollback_list(pool_name=sfs_pool)
	filesystems = pool_filesystems.keys()
	filesystems.sort()
	print('SFS Pool {0} filesystems:'.format(sfs_pool))
	for fs in filesystems:
		pool = pool_filesystems[fs]['POOL LIST']
		print('\t{0}'.format(fs))

	print('SFS Pool {0} snaphots:'.format(sfs_pool))
	snaps = pool_snapshots.keys()
	for snap in snaps:
		print('\t{0} ({1})'.format(snap, pool_snapshots[snap]['FILESYSTEM']))
	share_addresses = pool_shares.keys()
	share_addresses.sort()
	print('SFS Pool {0} shares:'.format(sfs_pool))
	for ip in share_addresses:
		hostname = None
		try:
			_ip = ip
			if '/' in ip:
				_ip = ip.split('/', 1)[0]
			hostname = gethostbyaddr(_ip)[0]
		except:
			pass
		stdout.write('\t{0}'.format(ip))
		if ip != hostname:
			stdout.write(' ({0})'.format(hostname))
		stdout.write('\n')
		ip_shares = pool_shares[ip]
		ip_shares.sort()
		for share in ip_shares:
			print('\t\t{0}'.format(share['path']))


if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option("--sfs_pool", dest="sfs_pool",
	                  help='The SFS Pool containing the filesystems and shares to delete')
	parser.add_option('--cip', dest='console_ip', help='The SFS console IP address')
	parser.add_option('--cu', dest='console_user', help='The SFS console user (master)')
	parser.add_option('--cp', dest='console_password', help='The SFS console password')
	parser.add_option('--list', action="store_true", help='Show storage info')
	parser.add_option('--cleandown', action="store_true", help='Show storage info')
	(options, args) = parser.parse_args()
	if len(argv) == 0:
		parser.print_help()
		exit(2)
	if not options.console_ip:
		print('No console IP specified')
		parser.print_help()
		exit(2)
	if not options.console_user:
		print('No console user specified')
		parser.print_help()
		exit(2)
	if not options.console_password:
		print('No console password specified')
		parser.print_help()
		exit(2)
	if not options.sfs_pool:
		print('No SFS pool specified')
		parser.print_help()
		exit(2)
	console_ip = options.console_ip
	try:
		console_hostname = gethostbyaddr(console_ip)[0]
	except:
		console_hostname = console_ip
	username = options.console_user
	password = options.console_password
	sfs_pool = options.sfs_pool
	if options.list:
		list_storage(sfs_pool, console_ip, username, password)
	elif options.cleandown:
		print('N/A')
		# create_cleandown_export(sfs_pool, console_ip, username, password)





