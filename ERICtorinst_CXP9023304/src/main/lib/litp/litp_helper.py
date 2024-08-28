from ast import literal_eval
from glob import glob
from httplib import HTTPConnection
from httplib import OK
from optparse import OptionGroup
from optparse import OptionParser
from os.path import abspath
from os.path import basename
from os.path import dirname
from os.path import exists
from os.path import splitext
from re import match
from socket import gethostbyaddr
from subprocess import PIPE
from subprocess import Popen
from sys import argv
from sys import exit
from time import sleep
from xml.sax import make_parser

from paramiko import SSHException
from simplejson import dumps
from simplejson import loads

from ini import ini_reader
from util.SSHSocket import SSHSocket
from xml_utils.rpm_helper import rpm_helper
from xml_utils.xml_merge import simple_parser


class litp_helper:
    P_CLUSTER = '/inventory/deployment1/cluster1'
    P_DEPLOYMENT = '/inventory/deployment1'

    R_JMS_QUEUE = 'jms-queue'
    R_JMS_TOPIC = 'jms-topic'
    R_DEPLOYABLE_ENTITY = 'deployable-entity'
    R_RHEL_COMPONENT = 'rhel-component'
    R_SERVICE_GROUP = 'service-group'
    R_SERVICE_UNIT = 'service-unit'
    R_PACKAGE = 'package'
    R_PACKAGE_DEF = 'package-def'
    R_LITP_TASK = 'LitpTask'
    R_NODE = 'node'

    C_LITPPACKAGEDEF = 'LitpPackageDef'

    YUM_RETRY_COUNT = 3
    YUM_RETRY_WAIT = 5
    DEFAULT_LS_PORT = 9999
    H_CONTENT_LENGTH = 'content-length'
    OP_GET = 'GET'
    OP_PUT = 'PUT'
    OP_DELETE = 'DELETE'
    DEBUG = False
    STATUS_KEYS = sorted(
        ['Initial', 'Available', 'Allocated', 'Configured', 'Applied', 'Applying', 'Verified', 'Failed', 'Deconfigured',
         'Removing', 'Removed'])

    def __init__(self, landscape_host, landscape_port=DEFAULT_LS_PORT, _debug=False, tor_ini=None):
        self.landscape_host = landscape_host
        self.landscape_port = landscape_port
        self.DEBUG = _debug
        if tor_ini is None:
            cwd = dirname(abspath(argv[0])).replace('\\', '/')
            self.tor_ini = '{0}/../../etc/tor.ini'.format(cwd)
        else:
            self.tor_ini = tor_ini
        if not exists(self.tor_ini):
            raise IOError('{0} not found'.format(self.tor_ini))
        self.rpmhelper = rpm_helper(self.tor_ini)

    def _debug(self, msg):
        if self.DEBUG:
            print(msg)

    def get_max_state_length(self):
        max_key_length = 0
        for key in self.STATUS_KEYS:
            if len(key) > max_key_length:
                max_key_length = len(key)
        return max_key_length

    def get_request(self, litp_path, litp_cmd):
        conn = HTTPConnection(host=self.landscape_host, port=self.landscape_port)
        try:
            _path = '%s/%s' % (litp_path, litp_cmd)
            self._debug(_path)
            headers = {self.H_CONTENT_LENGTH: 0}
            conn.request(self.OP_GET, _path, headers=headers)
            response = conn.getresponse()
            if response.status != OK:
                raise Exception(response.reason)
            response_data = response.read()
            return loads(response_data)
        finally:
            conn.close()

    def put_request(self, litp_path, body):
        conn = HTTPConnection(host=self.landscape_host, port=self.landscape_port)
        try:
            headers = {self.H_CONTENT_LENGTH: len(body)}
            conn.request(self.OP_PUT, litp_path, headers=headers, body=body)
            response = conn.getresponse()
            if response.status != OK:
                raise Exception(response.reason)
            response_data = response.read()
            return loads(response_data)
        finally:
            conn.close()

    def delete_request(self, litp_path, body):
        conn = HTTPConnection(host=self.landscape_host, port=self.landscape_port)
        try:
            headers = {self.H_CONTENT_LENGTH: 0}
            conn.request(self.OP_DELETE, litp_path, headers=headers)
            response = conn.getresponse()
            if response.status != OK:
                raise Exception(response.reason)
            response_data = response.read()
            return loads(response_data)
        finally:
            conn.close()

    def update_properties(self, litp_path, properties):
        body = dumps(properties)
        results = self.put_request(litp_path, body)
        self._debug(results)
        return results

    def update_property(self, litp_path, prop_name, prop_value):
        self.update_properties(litp_path, {prop_name: prop_value})

    def litp(self, litp_path, command):
        self._debug('HTTP:%s/%s' % (litp_path, command))
        response = self.get_request(litp_path, command)
        if 'error' in response:
            raise IOError(response['error'])
        elif 'Error' in response:
            raise IOError(response['Error'])
        return response

    def show(self, path, recursive=False, verbose_type=None, properties=None):
        command = 'show?'
        if recursive:
            command += 'recursive=r&'
        if verbose_type:
            command += 'verbose=%s&' % verbose_type
        if properties:
            command += 'attributes=['
            for prop in properties:
                command += '\'%s\'' % prop
            command += ']'
        return self.litp(path, command)

    def get_properties(self, path, wanted_properties=None):
        properties = self.show(path)
        if not wanted_properties:
            return properties
        return dict([(i, properties['properties'][i]) for i in wanted_properties if i in properties['properties']])

    def get_children(self, path, recurse=False, include_properties=False):
        verbose_type = None
        if not include_properties:
            verbose_type = 'l'
        children = self.show(path, recurse, verbose_type=verbose_type)
        data = {}
        for child in children:
            data[str(child[0])] = child[1]
        return data

    def path_exits(self, path):
        try:
            self.show(path, path)
            return True
        except IOError:
            return False

    def delete_path(self, litp_path):
        command = '%s/?force=' % litp_path
        self.delete_request(litp_path, command)

    def search_by_reource_type(self, path, resource_type, name=None):
        command = 'find?resource={0}'.format(resource_type)
        if name:
            command = '{0}&names={1}'.format(command, name)
        return self.litp(path, command)

    def get_empty_status(self):
        _map = {}
        for key in self.STATUS_KEYS:
            _map[key] = 0
        return _map

    def search_by_class_type(self, start, node_type):
        data = self.show(start, True, verbose_type='d')
        types = {}
        for node in data:
            _type = str(node[1]['class'])
            if _type == node_type:
                types[str(node[0])] = node
        return types

    def get_nodes_by_display_options(self, base_path, display_option, option_filter, litp_node_type=R_LITP_TASK):
        all_tasks = self.search_by_class_type(base_path, litp_node_type)
        matched_tasks = {}
        for task_path, data in all_tasks.items():
            task_properties = data[1]['properties']
            if 'display_options' in task_properties:
                options = task_properties['display_options']
                options = literal_eval(options)
                if display_option in options:
                    if match(option_filter, options[display_option]):
                        matched_tasks[task_path] = task_properties
        return matched_tasks

    def get_nodes_by_description(self, base_path, desc, litp_node_type=R_LITP_TASK):
        return self.get_nodes_by_display_options(base_path, 'description', desc, litp_node_type)

    def get_nodes_by_method_name(self, base_path, method_filter, litp_node_type=R_LITP_TASK):
        return self.get_nodes_by_display_options(base_path, 'method_name', method_filter, litp_node_type)

    def update_package_def(self, path, rpm, repo, pkg_version_formatter_map):
        header = self.rpmhelper.get_rpm_header(rpm)
        properties = self.show(path)
        from_version = 'N/A'
        if 'version' in properties['properties']:
            from_version = str(properties['properties']['version'])
        c_name = str(properties['properties']['name'])
        if c_name in pkg_version_formatter_map:
            to_version = self.rpmhelper.query(rpm, pkg_version_formatter_map[c_name])
            to_version = ''.join(to_version)
        else:
            to_version = header['VERSION']
        modified = False
        if 'repository' in properties['properties']:
            current_src_repo = str(properties['properties']['repository'])
            if current_src_repo != repo:
                print('Updating %s (%s)\n\trepository' % (path, c_name))
                print('\t\tFrom: {0}\n\t\t  To: {1}'.format(current_src_repo, repo))
                self.update_property(path, 'repository', repo)
                modified = True
            else:
                print('%s repository already set to %s' % (path, repo))
        if to_version != from_version:
            print('Updating %s (%s)\n\tversion' % (path, c_name))
            print('\t\tFrom: {0}\n\t\t  To: {1}'.format(from_version, to_version))
            self.update_property(path, 'ensure', 'installed')
            self.update_property(path, 'version', to_version)
            modified = True
        else:
            print('%s version already set to %s' % (path, to_version))
        return modified

    def update_de_def(self, de_path, pkg_rpm):
        version = self.rpmhelper.get_rpm_version(pkg_rpm)
        contents = self.rpmhelper.get_rpm_contents(pkg_rpm)
        deployable_container_types = '.*\.(ear|war|rar)$'
        install_source = None
        for _file in contents:
            if match(deployable_container_types, _file):
                if install_source:
                    raise IOError('More than one [{0}] in {1}'.format(deployable_container_types, pkg_rpm))
                install_source = _file
                break
        if not install_source:
            raise IOError('Could not find an install source in {0} for {1}'.format(pkg_rpm, de_path))
        name = basename(install_source)
        app_type = name.split('.')[::-1][0]
        c_properties = self.show(de_path)
        update_props = {'install-source': install_source, 'name': name, 'app-type': app_type, 'version': version}
        changes = {}
        for key in update_props:
            _from = c_properties['properties'][key]
            _to = update_props[key]
            if _from != _to:
                changes[key] = _to
        if changes:
            print('Updating %s' % de_path)
            for key in changes:
                print('\t{0}\n\t\tFrom: {1}\n\t\t  To: {2}'.format(key, c_properties['properties'][key], changes[key]))
            self.update_properties(de_path, changes)
            return True
        return False

    def show_deployables(self, tor_sw_path):
        des = self.search_by_class_type(tor_sw_path, 'JEEDeployableEntityDef')
        for de, info in des.items():
            print(de)
            for k, v in info[1]['properties'].items():
                print('\t{0} -- {1}'.format(k, v))
        pkgs = self.search_by_class_type(tor_sw_path, 'LitpPackageDef')
        for pkg, info in pkgs.items():
            print(pkg)
            for k, v in info[1]['properties'].items():
                print('\t{0} -- {1}'.format(k, v))

    def execute_process(self, command):
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        if process.returncode:
            raise Exception(stderr.strip())
        else:
            return stdout.strip().split('\n')

    def get_installed_rpm_details(self, ssh_client, rpm_name):
        _retry_count = 0
        results = None
        while True:
            try:
                results = ssh_client.execute('yum -q info installed {0}'.format(rpm_name))
                break
            except IOError as ioe:
                _msg = str(ioe)
                if 'Another app is currently holding the yum lock' in _msg:
                    _retry_count += 1
                    if _retry_count > self.YUM_RETRY_COUNT:
                        print('YUM is locked, retried {0} times to get info to no avail'.format(self.YUM_RETRY_COUNT))
                        raise ioe
                    print(_msg)
                    print('YUM is locked, retrying again in {0} seconds'.format(self.YUM_RETRY_WAIT))
                    sleep(self.YUM_RETRY_WAIT)
                    continue
                else:
                    raise ioe
                    # skip the first line ('Available Packages')
        rpm_info = {}
        for line in results[1:]:
            line = line.strip()
            if len(line) == 0:
                continue
            tokens = line.split(':', 1)
            if len(tokens) != 2:
                raise IOError(
                    'Expected [{0}] to be split into 2 path, was split into {1} parts'.format(line, len(tokens)))
            rpm_info[tokens[0].strip().lower()] = tokens[1].strip()
        return rpm_info

    def _get_packages_in_repo(self, yum_repo):
        details = self.execute_process(['yum', '--disablerepo=*', '--enablerepo=%s' % yum_repo, 'list', 'available'])
        repo_packages = {}
        for line in details:
            if match('.*%s$' % yum_repo, line):
                parts = line.split()
                package_name = parts[0].strip().replace('.noarch', '')
                ver_rel = parts[1].strip()
                version = ver_rel.split('-')[0]
                release = ver_rel.split('-')[1]
                repo = parts[0].strip()
                repo_packages[package_name] = {'version': version, 'release': release, 'repo': repo}
        return repo_packages

    def update_deployables(self, pkg_dir, source_repo, tor_sw_path='/definition/tor_sw',
                           jee_c_path='/definition/jee_containers'):
        if tor_sw_path is None:
            tor_sw_path = '/definition/tor_sw'
        if jee_c_path is None:
            jee_c_path = '/definition/jee_containers'
        if not exists(pkg_dir):
            raise IOError('{0} not found'.format(pkg_dir))
        print('Searching %s for packages' % pkg_dir)
        new_packages = glob('%s/*.rpm' % pkg_dir)
        if len(new_packages) == 0:
            raise IOError('No rpm files found in {0}'.format(pkg_dir))
        # Get packages under tor_sw (i.e. TOR applications)
        sw_packages = self.search_by_class_type(tor_sw_path, self.C_LITPPACKAGEDEF)
        sw_packages.update(
            self.search_by_class_type(jee_c_path, self.C_LITPPACKAGEDEF)
        )
        # Get packages under jee_containers (i.e. JBoss package)
        peer_nodes = self.search_by_reource_type(self.P_DEPLOYMENT, self.R_RHEL_COMPONENT)
        login_user = ini_reader.get_option(self.tor_ini, 'TOR', 'command_user')
        # Requires key login to sc1 and sc2, if running from design machines via cygwin:
        # cd ~
        # cat .ssh/id_rsa.pub | ssh root@SC-1 'cat >> .ssh/authorized_keys'
        # cat .ssh/id_rsa.pub | ssh root@SC-2 'cat >> .ssh/authorized_keys'
        # cat .ssh/id_rsa.pub | ssh root@ms1 'cat >> .ssh/authorized_keys'
        ssh_clients = {}
        # Note: the ssh is set up for all nodes, so for the ms it will ssh back to itself.
        # but for Win env (design) we need to ssh to the ms
        # socket.gethostbyname_ex(socket.gethostname())
        for node_path in peer_nodes:
            node_ip_props = self.show(node_path + '/ip')
            address = node_ip_props['properties']['address']
            ssh_clients[address] = SSHSocket()
            ssh_clients[address].setHost(address)
            ssh_clients[address].setUser(login_user)
            try:
                ssh_clients[address].connect()
            except SSHException as ae:
                raise IOError('Failed to connect to {0}'.format(address), ae)
                # pkg_map is the packages as defined in /definition at time of execution
        pkg_map = {}
        print('Gathering installation info ..')
        for path, info in sw_packages.items():
            pkgname = str(info[1]['properties']['name'])
            if pkgname not in pkg_map:
                pkg_map[pkgname] = {'paths': [], 'nodes': []}
                # if 'paths' not in pkg_map[pkgname]:
            #   pkg_map[pkgname]['paths'] = []
            paths_to_update = pkg_map[pkgname]['paths']
            paths_to_update.append(str(path))
            pkg_map[pkgname]['nodes'] = {}
            for node_data in peer_nodes:
                node_ip_props = self.show(node_data + '/ip')
                address = node_ip_props['properties']['address']
                _address = gethostbyaddr(address)[0]
                print('Checking {0} for install state details of {1}'.format(_address, pkgname))
                try:
                    installed_details = self.get_installed_rpm_details(ssh_clients[address], pkgname)
                    pkg_map[pkgname]['nodes'][node_data] = installed_details
                except IOError as ioe:
                    _msg = str(ioe)
                    if 'No matching Packages to list' in _msg:
                        print('{0} not currently installed on {1}'.format(pkgname, _address))
                        pkg_map[pkgname]['nodes'][node_data] = None
                    else:
                        raise ioe
        for _ssh in ssh_clients.values():
            _ssh.disconnect()
        print('Finished gathering install info.')
        package_updates = 0
        entity_updates = 0
        # Map a package name to a version format string based on the xml_snippets/tow_sw xml files
        cwd = dirname(abspath(argv[0])).replace('\\', '/')
        pkg_xmls = glob('{0}/../../etc/xml_snippets/tor_sw/*.xml'.format(cwd))
        pkg_xmls.extend(glob('{0}/../../etc/xml_snippets/jee_containers/*.xml'.format(cwd)))
        sax_parser = make_parser()
        sp = simple_parser()
        sax_parser.setContentHandler(sp)
        pkg_version_map = {}
        for xml in pkg_xmls:
            sax_parser.parse(xml)
            pkgdefs = sp.getExtractedNodes()
            packages = pkgdefs[0].getElementsByTagNameNS('*', self.R_PACKAGE_DEF)
            for package in packages:
                nodelist = package.getElementsByTagNameNS('*', 'version')
                if not nodelist:
                    continue
                name = str(package.getElementsByTagNameNS('*', 'name')[0].firstChild.nodeValue)
                version_format = str(nodelist[0].firstChild.nodeValue)
                pkg_version_map[name] = version_format
        print('Checking what versions are installed across all {0} nodes'.format(len(peer_nodes)))
        for package in new_packages:
            new_rpm_header = self.rpmhelper.get_rpm_header(package)
            bname = basename(package)
            pbname = splitext(bname)[0]
            pbname = pbname[:pbname.rfind('-')]
            if pbname in pkg_map:
                for base in pkg_map[pbname]['paths']:
                    nf_count = 0
                    update_required = False
                    _nodes = pkg_map[pbname]['nodes']
                    for node_path, installed_version in _nodes.items():
                        if not installed_version:
                            nf_count += 1
                            continue
                        i_version = installed_version['version']
                        i_release = installed_version['release']
                        i_version_t = tuple(map(int, (i_version.split("."))))
                        i_release_t = tuple(map(int, (i_release.split("."))))
                        n_rpm_version_t = tuple(map(int, (new_rpm_header['VERSION'].split("."))))
                        n_rpm_release_t = tuple(map(int, (new_rpm_header['RELEASE'].split("."))))
                        if n_rpm_version_t > i_version_t or n_rpm_release_t > i_release_t:
                            update_required = True
                            print(
                                '{0} currently has version {1}-{2} of {3} installed, will be upgraded to {4}-{5}'.format(
                                    node_path,
                                    i_version, i_release, pbname, new_rpm_header['VERSION'], new_rpm_header['RELEASE']))
                    if nf_count == len(pkg_map[pbname]['nodes'].values()):
                        # The package isnt installed on any of the blade but may be defined in the landscape
                        # model, let the update continue, if its not defined in the model, nothing will happen
                        print(
                            '{0} not currently installed on any nodes, landscape update may be required.'.format(
                                pbname))
                        update_required = True
                    if update_required:
                        print(
                            'Either {0} in not yet installed or a previous version is installed (and is to be upgraded)'.format(
                                pbname))
                        if self.update_package_def(base, package, source_repo, pkg_version_map):
                            package_updates += 1
                        parent = dirname(base)
                        de_path = '%s/de' % parent
                        if self.path_exits(de_path):
                            if self.update_de_def(de_path, package):
                                entity_updates += 1
                    else:
                        print('No version difference detected for {0}'.format(pbname))
            else:
                print('No usages of package %s found' % pbname)
        print('Total of {0} package changes made.'.format(package_updates))
        print('Total of {0} entity changes name.'.format(entity_updates))


    def delete_cmw_locks_unlocks(self, plan_path):
        search_string = 'cmw-(|un)?lock'
        print('Searching in {0} for tasks of type \'{1}\''.format(plan_path, search_string))
        cmw_lock_unlock = self.get_nodes_by_description(plan_path, search_string)
        if cmw_lock_unlock:
            for task_path, task_data in cmw_lock_unlock.items():
                task_type = literal_eval(task_data['display_options'])['description']
                print('Deleting {0} task {1}'.format(task_type, task_path))
                self.delete_path(task_path)
                print('Deleted {0} task {1}'.format(task_type, task_path))
        else:
            print('No tasks of type \'{0}\' found in {1}'.format(search_string, plan_path))

    def delete_snapshot_tasks(self, base_path, nas_service_list, lvm_list):
        search_string = '((NAS|LVM) snapshot|(NAS|LVM) restore)'
        print('Searching in {0} for tasks of type \'{1}\''.format(base_path, search_string))
        if nas_service_list:
            nas_service_list = nas_service_list.replace('\'', '').replace('"', '').split(',')
        if lvm_list:
            lvm_list = lvm_list.split(',')
        snap_tasks = self.get_nodes_by_method_name(base_path, search_string)
        if snap_tasks:
            deleted_any_sfs = False
            deleted_any_lvm = False
            for task_path, data in snap_tasks.items():
                snap_paths = literal_eval(data['params'])
                task_type = literal_eval(data['display_options'])['method_name']
                if nas_service_list and match('NAS (snapshot|restore)', task_type):
                    for ns in nas_service_list:
                        if ns == snap_paths[0]:
                            deleted_any_sfs = True
                            print('Deleting {0} task ({1}) {2}'.format(task_path, task_type, snap_paths))
                            self.delete_path(task_path)
                            print('Deleted {0} task ({1}) {2}'.format(task_path, task_type, snap_paths))
                if lvm_list and match('LVM (snapshot|restore)', task_type):
                    for _lvm_ in lvm_list:
                        lvm_attrs = snap_paths[1]
                        delete = False
                        if task_type == 'LVM snapshot':
                            delete = lvm_attrs['path'].endswith('/{0}'.format(_lvm_))
                        elif task_type == 'LVM restore':
                            delete = match('.*/{0}_.*'.format(_lvm_), lvm_attrs)
                        if delete:
                            deleted_any_lvm = True
                            print('Deleting {0} task ({1}) {2}'.format(task_path, task_type, snap_paths))
                            self.delete_path(task_path)
                            print('Deleted {0} task ({1}) {2}'.format(task_path, task_type, snap_paths))
            if not deleted_any_sfs:
                print('No tasks of type \'{0}\' found in {1} for service list {2}'.format(search_string, base_path,
                                                                                          nas_service_list))
            if not deleted_any_lvm:
                print('No tasks of type \'{0}\' found in {1} for LVM list {2}'.format(search_string, base_path,
                                                                                      lvm_list))
        else:
            print('No tasks of type \'{0}\' found in {1}'.format(search_string, base_path))

    def delete_snapshot_tasks_ms(self, base_path):
        """ Find and delete 'LVM snapshot' and 'grub save' tasks on ms - should be used only during
        upgrade to TOR 1.0.19/LITP CP4. Call to execute:
        litp_helper.py --delete_snapshot_tasks_ms --plan_path 'upgrade_plan_path'
 
        'LVM snapshto' task is identified by:
            "properties": {
                "display_options": "{'applied_in': 'ms1', 'description': 'LVM snapshots'}",
                "estimated_duration": "60",
                ...
        
        'grub save' task is identified by:
            "properties": {
                "display_options": "{'method_name': 'grub save', 'applied_in': 'ms1'}"

        """
        #find and delete 'LVM snapshot' task
        search_string = 'LVM snapshot'
        print('Searching in {0} for tasks of type \'{1}\''.format(base_path, search_string))
        snap_tasks = self.get_nodes_by_display_options(base_path, 'description', search_string)

        if snap_tasks:
            deleted_any_lvm = False
            for task_path, data in snap_tasks.items():
                task_type = literal_eval(data['display_options'])['applied_in']
                if task_path and match('ms1', task_type):
                   print('Deleting {0} task ({1})'.format(task_path, task_type))
                   self.delete_path(task_path)
                   print('Deleted {0} task ({1})'.format(task_path, task_type))
                   deleted_any_lvm = True
            if not deleted_any_lvm:
                print('No tasks of type \'{0}\' found in {1} for node {2}'.format(search_string, base_path,
                                                                                      'ms1'))
        else:
            print('No tasks of type \'{0}\' found in {1}'.format(search_string, base_path))
        
        #find and delete 'grub save' task
        search_string = 'grub save'
        print('Searching in {0} for tasks of type \'{1}\''.format(base_path, search_string))
        snap_tasks = self.get_nodes_by_display_options(base_path, 'method_name', search_string)

        if snap_tasks:
            deleted_any_lvm = False
            for task_path, data in snap_tasks.items():
                task_type = literal_eval(data['display_options'])['applied_in']
                if task_path and match('ms1', task_type):
                   print('Deleting {0} task ({1})'.format(task_path, task_type))
                   self.delete_path(task_path)
                   print('Deleted {0} task ({1})'.format(task_path, task_type))
                   deleted_any_lvm = True
            if not deleted_any_lvm:
                print('No tasks of type \'{0}\' found in {1} for node {2}'.format(search_string, base_path,
                                                                                      'ms1'))
        else:
            print('No tasks of type \'{0}\' found in {1}'.format(search_string, base_path))

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--landscape_host", dest="landscape_host")
    parser.add_option("--ini", dest="tor_ini")
    parser.add_option("--path", dest="def_tor_sw")
    parser.add_option('--plan_path', dest="plan_path")

    show_deployables = OptionGroup(parser, 'Show Deployable Entities')
    show_deployables.add_option('--show_deployables', action="store_true")
    parser.add_option_group(show_deployables)

    update_deployables = OptionGroup(parser, 'Update Deployable entities( and RPM package) versions')
    update_deployables.add_option('--update_deployables', action="store_true")
    update_deployables.add_option("--swdir", dest="rpm_dir")
    update_deployables.add_option("--jeec_path", dest="jeec_path")
    update_deployables.add_option('--repo', dest="repo")
    parser.add_option_group(update_deployables)

    delete_snapshot_tasks = OptionGroup(parser, 'Delete snapshot create/rollback tasks')
    delete_snapshot_tasks.add_option('--delete_snapshot_tasks', action="store_true")
    delete_snapshot_tasks.add_option('--nas_service_list', dest="nas_service_list")
    delete_snapshot_tasks.add_option('--lvm_list', dest="lvm_list")

    delete_snapshot_tasks_ms = OptionGroup(parser, 'Delete LMS snapshot create tasks')
    delete_snapshot_tasks_ms.add_option('--delete_snapshot_tasks_ms', action="store_true")

    delete_snap_tasks = OptionGroup(parser, 'Delete all cmw_lock and cmw_unlock tasks')
    delete_snap_tasks.add_option('--delete_cmw_locks_unlocks', action="store_true")
    parser.add_option_group(delete_snap_tasks)

    (options, args) = parser.parse_args()
    if len(argv) == 1:
        parser.print_help()
        exit()
    landscape_host = 'localhost'
    if options.landscape_host:
        landscape_host = options.landscape_host
    litp = litp_helper(landscape_host, tor_ini=options.tor_ini)
    if options.show_deployables:
        litp.show_deployables(options.def_tor_sw)
    elif options.update_deployables:
        litp.update_deployables(options.rpm_dir, options.repo, tor_sw_path=options.def_tor_sw, jee_c_path=options.jeec_path)
    elif options.delete_cmw_locks_unlocks:
        litp.delete_cmw_locks_unlocks(options.plan_path)
    elif options.delete_snapshot_tasks:
        litp.delete_snapshot_tasks(options.plan_path, options.nas_service_list, options.lvm_list)
    elif options.delete_snapshot_tasks_ms:
        litp.delete_snapshot_tasks_ms(options.plan_path)
