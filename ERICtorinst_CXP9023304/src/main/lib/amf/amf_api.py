#!/usr/bin/env python

from optparse import OptionParser
import socket
from sys import argv

from util.SSHSocket import SSHSocket


__author__ = 'eeipca'


class amf_api:
	_AMF_STATE = '/usr/bin/amf-state'
	_IMMFIND = '/usr/bin/immfind'
	_IMMLIST = '/usr/bin/immlist'

	C_SERVICE_GROUP = 'SaAmfSG'
	C_SERVICE_UNIT = 'SaAmfSU'

	SCOPE_SUBLEVEL = 'sublevel'
	SCOPE_SUBTREE = 'subtree'

	def __init__(self, amf_host, user, passwd=None):
		self.amf_host = amf_host
		self.huser = user
		self.hpasswd = passwd
		self.ssh_connection = None

	def connect(self):
		if self.ssh_connection:
			raise IOError('Already connected to {0}'.format(self.amf_host))
		self.ssh_connection = SSHSocket()
		self.ssh_connection.setHost(self.amf_host)
		self.ssh_connection.setUser(self.huser)
		if self.hpasswd:
			self.ssh_connection.setPasswd(self.hpasswd)
		try:
			self.ssh_connection.connect()
		except socket.error as error:
			raise IOError(error.errno, 'Could not connect to host %s (%s)' % (self.amf_host, error.strerror))

	def _check_connected(self):
		if not self.ssh_connection:
			raise IOError('Not connected to {0}'.format(self.amf_host))

	def disconnect(self):
		if self.ssh_connection:
			try:
				self.ssh_connection.disconnect()
			finally:
				self.ssh_connection = None

	def get_by_class_type(self, amf_class_type, base_dn='', scope=None):
		self._check_connected()
		command = '{0} {1} -c {2} '.format(self._IMMFIND, base_dn, amf_class_type)
		if scope:
			command = '{0} -s {1}'.format(command, scope)
		return self.ssh_connection.execute(command)

	def get_su_state_info(self, su_dn):
		self._check_connected()
		command = '{0} su all {1}'.format(self._AMF_STATE, su_dn)
		_states = self.ssh_connection.execute(command)
		states = {}
		for line in _states:
			tokens = line.split('=', 1)
			states[tokens[0]] = tokens[1]
		return states

	def get_attributes(self, dn, att_names=None):
		self._check_connected()
		command = '{0} {1}'.format(self._IMMLIST, dn)
		if att_names:
			if type(att_names) is str:
				command = '{0} -a {1}'.format(command, att_names)
			else:
				for att in att_names:
					command = '{0} -a {1}'.format(command, att)
		attributes = self.ssh_connection.execute(command)
		attmap = {}
		if att_names:
			for nv in attributes:
				tokens = nv.split('=', 1)
				value = None
				if tokens[1] != '<Empty>':
					value = tokens[1]
				attmap[tokens[0]] = value
		else:
			for line in attributes[2:]:
				tokens = line.split()
				value = None
				if tokens[2] != '<Empty>':
					value = tokens[2]
				attmap[tokens[0]] = value
		return attmap

	def list_service_groups(self):
		service_groups = self.get_by_class_type(self.C_SERVICE_GROUP)
		service_groups.sort()
		for sg in service_groups:
			print(sg)

	def list_servicegroup_status(self, group_dn):
		serviceunits = self.get_by_class_type(self.C_SERVICE_UNIT, base_dn=group_dn, scope=self.SCOPE_SUBLEVEL)
		serviceunits.sort()
		units = {}
		for unit in serviceunits:
			units[unit] = self.get_su_state_info(unit)
			units.pop("safSu", None)
			unit_atts = self.get_attributes(unit, 'saAmfSUHostedByNode')
			saAmfSUHostedByNode = unit_atts['saAmfSUHostedByNode'].split(',')[0].split('=')[1]
			units[unit]['saAmfSUHostedByNode'] = saAmfSUHostedByNode
			saAmfNodeClmNode = self.get_attributes(unit_atts['saAmfSUHostedByNode'], ['saAmfNodeClmNode'])
			saAmfNodeClmNode = saAmfNodeClmNode['saAmfNodeClmNode'].split(',')[0].split('=')[1]
			units[unit]['saAmfNodeClmNode'] = saAmfNodeClmNode
		return units

if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option('--amf_host', dest='amf_host')
	parser.add_option('--username', dest='username')
	parser.add_option('--password', dest='password')
	parser.add_option('--list_groups', action="store_true")
	parser.add_option('--sg', dest='service_group')
	(options, args) = parser.parse_args()
	if len(argv) == 1:
		parser.print_help()
		exit()
	amf = amf_api(options.amf_host, options.username, options.password)
	amf.connect()
	try:
		if options.list_groups:
			amf.list_service_groups()
		elif options.service_group:
			amf.list_servicegroup_status(options.service_group)
	finally:
		amf.disconnect()