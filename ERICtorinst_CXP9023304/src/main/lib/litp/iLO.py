from optparse import OptionParser
import re
from sys import argv, exit

__author__ = 'eeipca'

from util.SSHSocket import SSHSocket


class ilo_api:
	DEBUG = False

	def __init__(self, ilo_hostname, ilo_username, ilo_password):
		self.ilo_hostname = ilo_hostname
		self.ilo_username = ilo_username
		self.ilo_password = ilo_password
		self.ssh_connection = None

	def connect(self):
		if not self.ssh_connection:
			self.ssh_connection = SSHSocket()
			self.ssh_connection.setHost(self.ilo_hostname)
			self.ssh_connection.setUser(self.ilo_username)
			self.ssh_connection.setPasswd(self.ilo_password)
			self.ssh_connection.connect()

	def disconnect(self):
		if self.ssh_connection:
			self.ssh_connection.disconnect()
		self.ssh_connection = None

	def ilo_action(self, command):
		if not self.ssh_connection:
			raise IOError('Not connected to iLO')
		return self.ssh_connection.execute(command)

	def split_in_index(self, index_list, line):
		last_index = index_list[0]
		_list = []
		for next_index in index_list[1::]:
			_list.append(line[last_index: next_index].strip())
			last_index = next_index
		return _list

	def get_serial_bay_mapping(self):
		all_info = self.ilo_action('show server info all')
		iterator = iter(all_info)
		serial_bay_mapping = {}
		try:
			while 1:
				line = iterator.next().strip()
				match_bay_id = re.match('^Server Blade #([0-9]+)\s+.*', line)
				if match_bay_id:
					bay_id = match_bay_id.group(1)
					while 1:
						line = iterator.next().strip()
						match_serial = re.match('^Serial Number:\s+(\S+).*', line)
						if match_serial:
							serial = match_serial.group(1)
							serial_bay_mapping[serial] = bay_id
							break
		except StopIteration:
			pass
		return serial_bay_mapping

	def get_blade_serial_number(self, bay_id):
		print('get_blade_serial_number ->')
		output = self.ilo_action('SHOW SERVER INFO %s' % bay_id)
		match = re.match('.*Serial Number:\s+(\S+).*?', ' '.join(output))
		try:
			if match:
				return match.group(1)
		finally:
			print('get_blade_serial_number <-')

	def get_bay_info(self):
		col_name_index = 7
		split_index = 8
		# if bay_id:
		# 	cmd = 'SHOW SERVER INFO %s' % bay_id
		# else:
		cmd = 'SHOW SERVER LIST'
		bay_info = self.ilo_action(cmd)
		if self.DEBUG:
			for line in bay_info:
				print(line)
		header_split = list(bay_info[split_index].strip())
		column_start_indexes = [0]
		index = 0
		while index < len(header_split):
			while index < len(header_split) and header_split[index] == '-':
				index += 1
			while index < len(header_split) and header_split[index] != '-':
				index += 1
			column_start_indexes.append(index)
		header_names = self.split_in_index(column_start_indexes, bay_info[col_name_index])
		bay_list = {}
		for info in bay_info[(split_index + 1)::]:
			if self.DEBUG:
				print('Parsing line [%s]' % info)
			if not (len(info)):
				continue
			elif re.match('\s+Totals:', info):
				break
			data = self.split_in_index(column_start_indexes, info)
			bay_info = {}
			for index in range(len(header_names)):
				bay_info[header_names[index]] = data[index]
			if bay_info['iLO Name'] == '[Absent]' or bay_info['iLO Name'] == '[Subsumed]':
				continue
			bay_list[bay_info['Bay']] = bay_info
		return bay_list

	def power_on(self, bay_id):
		results = self.ilo_action('POWERON SERVER %s' % bay_id)
		for line in results:
			print(line)

	def power_off(self, bay_id):
		results = self.ilo_action('POWEROFF SERVER %s' % bay_id)
		for line in results:
			print(line)


if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option('--ilo', dest='ilo', help='iLO ip address')
	parser.add_option('--user', dest='user', help='iLO username')
	parser.add_option('--pass', dest='passwd', help='iLO password')
	parser.add_option('--serial', dest='serial', help='Blade serial ID')
	parser.add_option('--state', action='store_true', help='Get the power state of the blade (on|off)')
	parser.add_option('--poweron', action='store_true', help='Power on a blade')
	parser.add_option('--poweroff', action='store_true', help='Power off a blade')
	(options, args) = parser.parse_args()
	if len(argv) == 1:
		parser.print_help()
		exit(2)
	serial = options.serial
	ilo = ilo_api(options.ilo, options.user, options.passwd)
	ilo.connect()
	try:
		bay_serial = ilo.get_serial_bay_mapping()
		if serial not in bay_serial:
			raise IOError('No serial-id %s found' % serial)
		bay_id = bay_serial[serial]
		blades = ilo.get_bay_info()
		if bay_id not in blades:
			raise IOError('No bay-id %s in bay list!' % bay_id)
		bay_info = blades[bay_id]
		if options.state:
			print(bay_info['Power'].lower())
		elif options.poweron:
			if bay_info['Power'] == 'Off':
				print('Powring ON %s (Bay-%s)' % (serial, bay_info['Bay']))
				ilo.power_on(bay_info['Bay'])
			else:
				print('%s (Bay-%s) already powered on' % (serial, bay_info['Bay']))
		elif options.poweroff:
			if bay_info['Power'] == 'On':
				print('Powring OFF %s (Bay-%s)' % (serial, bay_info['Bay']))
				ilo.power_off(bay_info['Bay'])
			else:
				print('%s (Bay-%s) already powered on' % (serial, bay_info['Bay']))
	finally:
		ilo.disconnect()