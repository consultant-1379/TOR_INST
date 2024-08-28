import glob
import traceback
from dom_helper import print_xml
from ini import ini_reader
from optparse import OptionParser
from os.path import abspath, basename, dirname, exists
from re import match
from rpm_helper import rpm_helper
from sys import argv, exit
from xml.dom.minicompat import NodeList
from xml.dom.minidom import parse


def get_text_element(xml_node, element_name, create=True):
	text_element = xml_node.getElementsByTagNameNS('*', element_name)
	if len(text_element):
		text_element = text_element[0]
		if not text_element.firstChild and create:
			text_element.appendChild(dom_tree.createTextNode(''))
		text_element = text_element.firstChild
	return text_element


def update_pkg_versions(dom_tree, tor_sw_base, pkg_src_repo, litp_repo_name):
	tor_sw_node = None
	jee_containers_node = None
	componments = dom_tree.getElementsByTagNameNS('*', 'component-def')
	for comp in componments:
		if comp.getAttribute('id') == 'tor_sw':
			if tor_sw_node:
				raise IOError('More than 1 tor_sw node defined in definition!')
			tor_sw_node = comp
		elif comp.getAttribute('id') == 'jee_containers':
			if jee_containers_node:
				raise IOError('More than 1 jee_container node defined in definition!')
			jee_containers_node = comp
	if not jee_containers_node:
		raise IOError('No jee_container node defined in definition!')
	if not tor_sw_node:
		raise IOError('No tor_sw node defined in definition!')
	packages = tor_sw_node.getElementsByTagNameNS('*', 'package-def')
	packages.extend(jee_containers_node.getElementsByTagNameNS('*', 'package-def'))
	for package in packages:
		pkg_desc = package.parentNode.getAttribute('id')
		p_name = str(package.getElementsByTagNameNS('*', 'name')[0].firstChild.nodeValue.strip())
		if not p_name.startswith('ERIC'):
			print('Skipping {0}/{1} ({2})'.format(pkg_desc, package.getAttribute('id'), p_name))
			continue
		print('Checking {0}/{1} ({2})'.format(pkg_desc, package.getAttribute('id'), p_name))
		repository = get_text_element(package, 'repository')
		if not isinstance(repository, NodeList) and str(repository.nodeValue) == litp_repo_name:
			print('\tSkipping verion update of {0} as it\'s from LITP repo {1}'.format(p_name, litp_repo_name))
			continue
		rpm_path = '{0}/{1}*.rpm'.format(tor_sw_base, p_name)
		pkg_rpm = glob.glob(rpm_path)
		if len(pkg_rpm) == 0:
			raise IOError('Could not find a match to {0}'.format(rpm_path))
		pkg_rpm = pkg_rpm[0]
		rpm_header = rpm.get_rpm_header(pkg_rpm)
		p_version = get_text_element(package, 'version', False)
		if len(p_version):
			# If there's a version tag, populate it, otherwise leasve it up to puppet to pick the version....
			if not p_version.nodeValue or len(p_version.nodeValue.strip()) == 0:
				# Default value
				p_version.nodeValue = '%{Version}'
			versionstring = rpm.query(pkg_rpm, p_version.nodeValue)
			p_version.nodeValue = ''.join(versionstring)
			repository = get_text_element(package, 'repository', False)
			repository.nodeValue = pkg_src_repo
			print('\tSet package version to {0}'.format(p_version.nodeValue))
			print('\tSet package repository to {0}'.format(repository.nodeValue))
		d_entities = package.parentNode.getElementsByTagNameNS('*', 'deployable-entity-def')
		if d_entities and len(d_entities) > 0:
			de = d_entities[0]
			install_source = get_text_element(de, 'install-source')
			name = get_text_element(de, 'name')
			version = get_text_element(de, 'version')
			app_type = get_text_element(de, 'app-type')
			contents = rpm.get_rpm_contents(pkg_rpm)
			deployable_container_types = '.*\.(ear|war|rar)$'
			jee_de = None
			for _file in contents:
				if match(deployable_container_types, _file):
					if jee_de:
						raise IOError('More than one [{0}] in {1}'.format(deployable_container_types, pkg_rpm))
					jee_de = _file
					break
			if not jee_de:
				raise IOError('Could not find an install source in {0} for {1}'.format(pkg_rpm, p_name))
			install_source.nodeValue = jee_de
			name.nodeValue = basename(jee_de)
			# The deployable entity version is just <version>
			version.nodeValue = rpm_header[rpm.h_VERSION]
			# Split the name into a list using the "." character
			tokens = name.nodeValue.split('.')
			# Reverse the list and the first element is the file extension
			app_type.nodeValue = tokens[::-1][0]
			print('\tSet de install-source to {0}'.format(install_source.nodeValue))
			print('\tSet de name/version to {0}/{1}'.format(name.nodeValue, version.nodeValue))
			print('\tSet de app-type to {0}'.format(app_type.nodeValue))

if __name__ == "__main__":
	cwd = dirname(abspath(argv[0])).replace('\\', '/')
	tor_inst_ini = '{0}/../../etc/tor.ini'.format(cwd)
	if not exists(tor_inst_ini):
		raise IOError('{0} not found'.format(tor_inst_ini))
	ini_reader.init_reader(tor_inst_ini)
	litp_repo = ini_reader.get_option(tor_inst_ini, 'LITP', 'litp_repo_name')
	rpm = rpm_helper(tor_inst_ini)
	parser = OptionParser()
	parser.add_option('-d', '--definition', help="Landscape definition xml", dest='xml')
	parser.add_option('-s', '--sw_base', help="TOR SW Directory", dest='tor_sw_base')
	parser.add_option('-o', '--output', help="Output file", dest='output_file')
	parser.add_option('-r', '--repo', help="YUM repo oackage exists in", dest='repo')
	(options, args) = parser.parse_args()
	if not options.xml:
		parser.print_help()
		exit(2)
	if not options.tor_sw_base:
		parser.print_help()
		exit(2)
	if not exists(options.xml):
		raise IOError('{0} not found'.format(options.xml))
	if not exists(options.tor_sw_base):
		raise IOError('{0} not found'.format(options.tor_sw_base))
	dom_tree = parse(options.xml)
	update_pkg_versions(dom_tree, options.tor_sw_base, options.repo, litp_repo)
	print_xml(dom_tree, options.output_file)
