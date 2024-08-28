#!/usr/bin/python
import glob
from optparse import OptionParser
import os
from os.path import abspath, basename, dirname, exists
from ConfigParser import ConfigParser as ini
import subprocess
from xml.dom.minidom import parse
import sys

from rpm_helper import rpm_helper


class pkg_verifier:
	def get_container_names(self, xml_dom):
		container_list = []
		elements = xml_dom.getElementsByTagNameNS('*', 'jee-container-def')
		if not len(elements):
			raise IOError('No elements of type \'jee-container-def\' found.')
		for node in elements:
			if node.getAttribute('id') != 'instance':
				continue
			name = node.getElementsByTagNameNS('*', 'name')
			if not len(name):
				raise IOError('No elements of type \'name\' found.')
			container_list.append(str(name[0].firstChild.nodeValue.strip()))
		return container_list

	def get_deployable_entities(self, xml_dom):
		entities = xml_dom.getElementsByTagNameNS('*', 'deployable-entity-def')
		deployable_entities = {}
		for entity in entities:
			install_source = str(entity.getElementsByTagNameNS('*', 'install-source')[0].firstChild.nodeValue.strip())
			e_name = str(entity.getElementsByTagNameNS('*', 'name')[0].firstChild.nodeValue.strip())
			e_version = str(entity.getElementsByTagNameNS('*', 'version')[0].firstChild.nodeValue.strip())
			try:
				service = str(entity.getElementsByTagNameNS('*', 'service')[0].firstChild.nodeValue.strip())
			except IndexError:
				service = None
			try:
				app_type = str(entity.getElementsByTagNameNS('*', 'app-type')[0].firstChild.nodeValue.strip())
			except IndexError:
				app_type = None
			de_name = entity.parentNode.getAttribute('id')
			packages = entity.parentNode.getElementsByTagNameNS('*', 'package-def')
			deployable_packages = []
			for package in packages:
				p_name = str(package.getElementsByTagNameNS('*', 'name')[0].firstChild.nodeValue.strip())
				if len(package.getElementsByTagNameNS('*', 'version')):
					p_version = str(package.getElementsByTagNameNS('*', 'version')[0].firstChild.nodeValue.strip())
				else:
					p_version = 'N/A'
				deployable_packages.append({'name': p_name, 'version': p_version})
			deployable_entities[de_name] = {
				'install-source': install_source,
				'app-type': app_type,
				'service': service,
				'name': e_name,
				'version': e_version,
				'packages': deployable_packages
			}
		return deployable_entities

	def execute_process(self, args):
		process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
		stdout, stderr = process.communicate()
		if process.returncode:
			raise IOError('Error executing command {0}\n{1}'.format(args, stderr))
		return stdout.split('\n')

	def verify_cmw_campaigns(self, xml_dom, tor_sw_base, show_only_errors=False):
		campaigns = xml_dom.getElementsByTagNameNS('*', 'cmw-campaign-def')
		error_count = 0
		for campaign in campaigns:
			pec = error_count
			campaign_name = campaign.getAttribute('id')
			bundle_name = str(campaign.getElementsByTagNameNS('*', 'bundle_name')[0].firstChild.nodeValue.strip())
			try:
				bundle_type = str(campaign.getElementsByTagNameNS('*', 'bundle_type')[0].firstChild.nodeValue.strip())
			except IndexError:
				bundle_type = 'sdp'
			container_name = '{0}.{1}'.format(bundle_name, bundle_type)
			if not exists('{0}/{1}'.format(tor_sw_base, container_name)):
				print(
					'ERROR: Campaign \'{0}\' container not found in {1}, looking for {2}'
					.format(campaign_name, tor_sw_base, container_name))
				error_count += 1
			if bundle_type == 'sdp':
				install_name = str(campaign.getElementsByTagNameNS('*', 'install_name')[0].firstChild.nodeValue.strip())
				install_container = '{0}.sdp'.format(install_name)
				if not exists('{0}/{1}'.format(tor_sw_base, install_container)):
					print(
						'ERROR: Campaign \'{0}\' package container not found in {1}, looking for {2}'.format(
							campaign_name,
							tor_sw_base, install_container))
					error_count += 1
			if not show_only_errors and pec == error_count:
				print('OK: Campaign containers for \'{0}\' looks OK'.format(campaign_name))
		print('Total of {0} errors for campaign installables.'.format(error_count))
		return error_count

	def verify_deployable_entities(self, xml_dom, tor_sw_base, show_only_errors=False):
		deployable_entities = self.get_deployable_entities(xml_dom)
		error_count = 0
		warning_count = 0
		cwd = dirname(abspath(sys.argv[0])).replace('\\', '/')
		tor_inst_ini = '{0}/../../etc/tor.ini'.format(cwd)
		if not os.path.exists(tor_inst_ini):
			raise IOError('{0} not found'.format(tor_inst_ini))
			# ini_reader.init_reader(tor_inst_ini)
		rpmhelper = rpm_helper(tor_inst_ini)
		jboss_containers = self.get_container_names(xml_dom)
		rpm_path = '{0}/*.rpm'.format(tor_sw_base)
		files = glob.glob(rpm_path)
		tow_sw_list = {}
		for file in files:
			header = rpmhelper.get_rpm_header(file)
			tow_sw_list[header[rpmhelper.h_NAME]] = header
		for entity, data in deployable_entities.items():
			pec = error_count
			if basename(data['install-source']) != data['name']:
				print(
					'ERROR: In deployable entity for \'{0}\': install-source and name values don\'t match {1} <-> {2}'
					.format(entity, data['install-source'], data['name']))
				error_count += 1
			if not data['service']:
				print('WARNING: Deployable entity \'{0}\' doesn\'t reference any JBOSS instance?'.format(entity))
				warning_count += 1
			elif data['service'] not in jboss_containers:
				print('ERROR: Deployable entity \'{0}\' references an undefined JBoss instance called \'{1}\''.format(
					entity, data['service']))
				error_count += 1
			if not data['app-type']:
				print('WARNING: Deployable entity \'{0}\' has no \'app-type\' declaration?'.format(entity))
				warning_count += 1
			if data['packages']:
				_package = data['packages'][0]
				if not tow_sw_list[_package['name']]:
					print('ERROR: No rpm can be found using the name {0}'.format(_package['name']))
					error_count += 1
					continue
				rpm_file = '{0}/{1}-{2}.rpm'.format(tor_sw_base, tow_sw_list[_package['name']]['NAME'],
				                                    tow_sw_list[_package['name']]['VERSION'])
				if not exists(rpm_file):
					print('ERROR: No rpm for deployable entity \'{0}\' found in {1} (looking for {2})'.
					      format(entity, tor_sw_base, basename(rpm_file)))
					error_count += 1
				else:
					rpm_file = rpm_file.replace('\\', '/')
					file_list = rpmhelper.get_rpm_contents(rpm_file)
					source_found = False
					for file in file_list:
						if file == data['install-source']:
							source_found = True
							break
					if not source_found:
						print('ERROR: Deployable entity \'{0}\' defines its install-source as {1} but the '
						      'package-def ({2}) doesn\'t contain that file'
						      .format(entity, data['install-source'], basename(rpm_file)))
						error_count += 1
			else:
				print('WARNING: Deployable entity \'{0}\' doesn\'t define any installable packages?'.format(entity))
				warning_count += 1
			if not show_only_errors and pec == error_count:
				print('OK: Deployable entity for \'{0}\' looks OK'.format(entity))
		print('Total of {0} errors and {1} warnings for rpm installables.'.format(error_count, warning_count))
		return error_count

	def verify_installables(self, def_xml, tor_sw_base, show_only_errors=False):
		xml_dom = parse(def_xml)
		exit_code = self.verify_deployable_entities(xml_dom, tor_sw_base, show_only_errors)
		exit_code += self.verify_cmw_campaigns(xml_dom, tor_sw_base, show_only_errors)
		return exit_code


if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option('-d', '--definition', help="Landscape definition xml", dest='xml')
	parser.add_option('-s', '--sw_base', help="TOR SW Directory", dest='tor_sw_base')
	parser.add_option('-e', '--errors_only', help="Only show errors", dest='errors_only', action="store_true")
	(options, args) = parser.parse_args()
	verifier = pkg_verifier()
	if not options.xml:
		parser.print_help()
		sys.exit(2)
	if not options.tor_sw_base:
		parser.print_help()
		sys.exit(2)
	if not os.path.exists(options.tor_sw_base):
		raise IOError('{0} not found'.format(options.tor_sw_base))
	exit_code = verifier.verify_installables(options.xml, options.tor_sw_base, options.errors_only)
	sys.exit(exit_code)
