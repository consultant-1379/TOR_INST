from os.path import dirname
from re import match
from SSHSocket import SSHSocket
from sys import argv


class SFS:
	SFS_BLOCK = 'SFS'

	def init(self, sfs_address, sfs_username, sfs_password):
		self.sfs_address = sfs_address
		self.sfs_username = sfs_username
		self.sfs_password = sfs_password

	def sfs_connect(self):
		s = SSHSocket()
		s.setHost(self.sfs_address)
		s.setUser(self.sfs_username)
		s.setPasswd(self.sfs_password)
		if s.connect():
			self.ssh_connection = s
		else:
			raise IOError('Failed to connect to SFS')

	def sfs_disconnect(self):
		if self.ssh_connection:
			self.ssh_connection.disconnect()

	def sfs_action(self, command):
		self.sfs_connect()
		try:
			return self.ssh_connection.execute(command)
		finally:
			self.sfs_disconnect()

	def split_in_index(self, index_list, line):
		_list = []
		for group_range in index_list:
			end = group_range[1]
			if end == -1:
				end = len(line)
			_list.append(line[group_range[0]: end].strip())
		return _list

	def parse_date(self, header, header_match, data_list, row_match=None):
		groups = match(header_match, header)
		if not groups:
			raise SyntaxError('Cant parse results header \'{0}\''.format(header))
		header_names = []
		column_start_indexes = []
		group_count = len(groups.groups())
		for index in range(1, group_count + 1):
			header_names.append(groups.group(index))
			start_index = groups.start(index)
			if index >= group_count:
				end_index = -1
			else:
				# end and the start of then next header
				end_index = groups.start(index + 1)
			column_start_indexes.append([start_index, end_index])
		parsed_data = []
		for info in data_list:
			info = info.strip()
			if not (len(info)):
				continue
			if row_match:
				groups = match(row_match, info)
				row_data = []
				if not groups:
					raise SyntaxError('Cant parse results data row  \'{0}\''.format(info))
				for cell_value in groups.groups():
					row_data.append(cell_value)
			else:
				row_data = self.split_in_index(column_start_indexes, info)
			row_map = {}
			for index in range(len(header_names)):
				row_map[header_names[index]] = row_data[index]
			parsed_data.append(row_map)
		return parsed_data

	def nfs_share_show(self, pool_name=None):
		output = self.sfs_action('nfs share show')
		shares = {}
		for line in output:
			if line == 'Faulted Shares:':
				break
			groups = match('^(/vx/(.*))\s+(.*)\s+\(*', line.strip())
			if groups:
				sfs_path = groups.group(1).strip()
				sfs_name = groups.group(2).strip()
				share_ip = groups.group(3).strip()
				pool = sfs_name.split('-')[0]
				share_info = {'name': sfs_name, 'path': sfs_path, 'shared_to': share_ip}
				if not pool_name or pool == pool_name:
					if share_ip not in shares:
						shares[share_ip] = []
					shares[share_ip].append(share_info)
		return shares

	def storage_fs_list(self, pool_name=None):
		output = self.sfs_action('storage fs list')
		header_match = '(FS)\s+(STATUS)\s+(SIZE)\s+(LAYOUT)\s+(MIRRORS)\s+(COLUMNS)\s+(USE%)\s+(NFS SHARED)\s+(CIFS SHARED)\s+(SECONDARY TIER)\s+(POOL LIST)'
		row_match = '(\S+)\s+(\w+)\s+(\S+)\s+(\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(\w+)'
		data = self.parse_date(output[0].strip(), header_match, output[2::], row_match)
		fs_list = {}
		for row in data:
			if not pool_name or row['POOL LIST'] == pool_name:
				fs_list[row['FS']] = row
		return fs_list

	def storage_rollback_list(self, pool_name=None):
		output = self.sfs_action('storage rollback list')
		data = self.parse_date(output[0].strip(), '(NAME)\s+(TYPE)\s+(FILESYSTEM)\s+(SNAPDATE)', output[1::])
		snap_list = {}
		for row in data:
			pool = row['FILESYSTEM'].split('-', 1)[0]
			if not pool_name or pool == pool_name:
				snap_list[row['NAME']] = row
		return snap_list

	def storage_pool_list(self):
		output = self.sfs_action('storage pool list')
		data = self.parse_date(output[0].strip(), '^(\w+)\s+(.*)', output[2::])
		pool_list = {}
		for row in data:
			pool_list[row['Pool']] = row
		return pool_list

if __name__ == '__main__':
	sfs = SFS()
	tor_ini = '{0}/tor.ini'.format(dirname(argv[0]))
	ini_reader = sfs.init(tor_ini, 'env2')
	tor_sfs_pool_name = ini_reader.get(sfs.SFS_BLOCK, 'sfs_pool')
	tor_shares = sfs.nfs_share_show(tor_sfs_pool_name)
	print('======================-Shares(%s)-======================' % tor_sfs_pool_name)
	for share in tor_shares:
		print('{0}\n\tpath:{1}\n\tshared_to:{2}'.format(share['name'], share['path'], share['shared_to']))
	print('======================--------======================')
	sfs_filesystems = sfs.storage_fs_list(tor_sfs_pool_name)
	print('======================-Filesystems(%s)-======================' % tor_sfs_pool_name)
	for fs_name, fs_info in sfs_filesystems.items():
		print(fs_name)
	print('======================-------------======================')
