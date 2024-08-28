import ConfigParser
import ast
from optparse import OptionParser, OptionGroup
from os import remove
import os
from os.path import dirname, exists, realpath
from re import search
import re
from shutil import rmtree
from subprocess import Popen, PIPE
import sys


class vboxmanage_api:
    BLOCK_VM = 'VBOX'
    BLOCK_MN = 'MN'
    BLOCK_MS = 'MS'
    PARAM_OST = 'os_type'
    PARAM_MEMS = 'mem_size'
    PARAM_FSS = 'disk_size'
    PARAM_NICC = 'nic_count'
    PARAM_HWUTC = 'hardware_utc'
    PARAM_VM_SCC = 'TOR_VM_SC_COUNT'
    PARAM_DEFAULT_ISO = 'litp_iso'
    DEBUG = False

    def ini_get(self, block, param, default=None):
        try:
            return self.vm_ini.get(block, param)
        except ConfigParser.NoOptionError as noe:
            if default:
                return default
            else:
                raise noe

    def __init__(self, vm_ini):
        if vm_ini:
            self.vm_ini_file = vm_ini
        else:
            self.vm_ini_file = '{0}/{1}'.format(dirname(realpath(__file__)), '../vm.ini')
        self.vm_ini = ConfigParser.ConfigParser()
        self.vm_ini.read(self.vm_ini_file)
        self.program = self.ini_get(self.BLOCK_VM, 'vbox_manage')
        if not exists(self.program):
            raise IOError('{0} not found'.format(self.program))
        self.default_ide_controller_type = self.ini_get(self.BLOCK_VM, 'ide_controller')
        self.default_sata_controller_type = self.ini_get(self.BLOCK_VM, 'sata_controller')
        try:
            self.DEBUG = ast.literal_eval(self.ini_get(self.BLOCK_VM, 'debug'))
        except ValueError as ve:
            self.log('Incorrect value for config parm \'debug\' : {0}'.format(ve))

    def log(self, msg):
        print(msg)

    def debug(self, msg):
        if self.DEBUG:
            self.log(msg)

    def execute_process(self, args):
        command = '{0} {1}'.format(self.program, ' '.join(args))
        self.debug(command)
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        if process.returncode:
            raise Exception(stderr.strip())
        else:
            return stdout.strip()

    def get_basic_vm_details(self, uuid):
        results = self.execute_process(['showvminfo', '"{0}"'.format(uuid), '--machinereadable'])
        all_vm_info = {}
        # Split the output of the command into a dict
        for line in results.split('\n'):
            line = line.strip()
            line = line.split('=')
            value = line[1].strip('"')
            if 'none' == value:
                value = None
            all_vm_info[line[0].strip('"')] = value
        if all_vm_info['name'] == '<inaccessible>':
            raise IOError('VM {0} is inaccessible'.format(uuid))
        return all_vm_info

    def get_group(self, uuid):
        all_vm_info = self.get_basic_vm_details(uuid)
        return all_vm_info['groups']

    def list_by_uuid(self):
        vm_list = {}
        output = self.execute_process(['list', 'vms'])
        for line in output.split('\n'):
            line = line.strip()
            match = re.search('\"(.*?)\"\s+({.*?})', line)
            uuid = match.group(2)
            group = self.get_group(uuid)
            name = match.group(1)
            if group == '/':
                group = ''
            vm_list[uuid] = '{0}/{1}'.format(group, name)
        return vm_list

    def vm_exists_uuid(self, vm_uuid):
        vm_list = self.list_by_uuid()
        return vm_uuid in vm_list

    def subset(self, key_filter, _dict):
        subset = {}
        for key, value in _dict.items():
            if re.match(key_filter, key):
                subset[key] = value
        return subset

    def reformat_mac(self, mac):
        mac = mac.strip('"')
        _macv = list(mac)
        mac = ''
        for index in xrange(len(_macv)):
            mac += _macv[index]
            if index % 2 == 1 and index < len(_macv) - 1:
                mac += ':'
        return mac

    def get_vm_details(self, uuid):
        all_vm_info = self.get_basic_vm_details(uuid)
        vm_info = {}
        vm_info['uuid'] = uuid
        vm_info['name'] = all_vm_info['name']
        vm_info['memory'] = all_vm_info['memory']
        vm_info['group'] = all_vm_info['groups']
        # For each nic defined, get its info
        nics = self.subset('nic[0-9]+', all_vm_info)
        for nic, nic_type in nics.items():
            if nic_type:
                nic_info = {'name': nic}
                nic_index = nic[3:]
                mac_key = 'macaddress{0}'.format(nic_index)
                nic_info['macaddress'] = self.reformat_mac(all_vm_info[mac_key])
                if nic_type == 'hostonly':
                    adapter_key = 'hostonlyadapter{0}'.format(nic_index)
                    nic_info['adapter'] = all_vm_info[adapter_key]
                vm_info[nic] = nic_info
        return vm_info

    def add_to_group(self, vm_name, group_name):
        if group_name:
            self.execute_process(['modifyvm', '"{0}"'.format(vm_name), '--groups', '/"{0}"'.format(group_name)])
            self.log('Added VM "{0}" to group {1}'.format(vm_name, group_name))

    def create_vm(self, vm_name, group_name, os_type, vm_base_storage=None):
        _all = self.list_by_uuid()
        if '/{0}/{1}'.format(group_name, vm_name) in _all.values():
            raise Exception('VM called "{0}" already defined in group "{1}"'.format(vm_name, group_name))
        command = ['createvm', '--name', '"{0}"'.format(vm_name), '--ostype', os_type, '--register']
        if vm_base_storage:
            command.append('--basefolder')
            command.append(vm_base_storage)
        results = self.execute_process(command)
        uuid = None
        for line in results.split('\n'):
            if line.startswith('UUID:'):
                uuid = '{%s}' % line.split(':')[1].strip()
                break
        self.add_to_group(vm_name, group_name)
        self.log('Created basic VM {0}'.format(vm_name))
        return uuid

    def get_vm_dir(self, uuid):
        if self.vm_exists_uuid(uuid):
            output = self.execute_process(['showvminfo', '"{0}"'.format(uuid)]).strip()
            match = search('Config file:\s+(.*)', output)
            if match:
                vbox = match.group(1)
                return dirname(vbox)
        return None

    def delete_vm(self, uuid):
        if self.vm_exists_uuid(uuid):
            self.log('Deleting UUID {0}'.format(uuid))
            vm_dir = self.get_vm_dir(uuid)
            self.execute_process(['unregistervm', '"{0}"'.format(uuid), '--delete'])
            if exists(vm_dir):
                self.log('Removing {0}'.format(vm_dir))
                rmtree(vm_dir)
            self.log('Deleted UUID {0}'.format(uuid))
        else:
            self.log('No VM with UUID \'{0}\' exists'.format(uuid))

    def modify_vm(self, uuid, vm_name, group, vm_ram_megs, vm_disk_size, adapter_count, hardware_utc):
        _all = self.list_by_uuid()
        if '/{0}/{1}'.format(group, vm_name) not in _all.values():
            raise Exception('No VM called "{0}" defined in group "{1}"'.format(vm_name, group))
        self.execute_process(
            ['modifyvm', '"{0}"'.format(uuid), '--memory', vm_ram_megs, '--vram', '12', '--boot1', 'dvd', '--boot2',
             'disk', '--boot3', 'net', '--rtcuseutc', hardware_utc])
        host_only_iface = self.list_hostonly_adapters()
        if not host_only_iface:
            raise Exception('No Host-Only interfaces available')
        host_only_iface = '"{0}"'.format(host_only_iface.itervalues().next()['Name'])
        for _id in range(1, int(adapter_count) + 1):
            nic_id = 'nic{0}'.format(_id)
            hoa_id = '--hostonlyadapter{0}'.format(_id)
            self.execute_process(
                ['modifyvm', '"{0}"'.format(uuid), '--{0}'.format(nic_id), 'hostonly', hoa_id, host_only_iface])
            self.log('Created {0} using {1}'.format(nic_id, host_only_iface))
            info = self.get_vm_details(uuid)
            nic_macaddress = info[nic_id]['macaddress']
            self.log('\tMAC: {1}'.format(nic_id, nic_macaddress))
        vm_dir = self.get_vm_dir(uuid)
        vm_vdi = '{0}/{1}.vdi'.format(vm_dir, uuid)
        if exists(vm_vdi):
            remove(vm_vdi)
        self.execute_process(
            ['createhd', '--filename', '"{0}"'.format(vm_vdi), '--size', vm_disk_size, '--format', 'vdi', '--variant',
             'Standard'])
        self.execute_process(
            ['storagectl', '"{0}"'.format(uuid), '--name', self.default_ide_controller_type, '--add', 'ide'])
        self.execute_process(
            ['storagectl', '"{0}"'.format(uuid), '--name', self.default_sata_controller_type, '--sataportcount', '1',
             '--add',
             'sata'])
        self.execute_process(
            ['storageattach', '"{0}"'.format(uuid), '--storagectl', self.default_sata_controller_type,
             '--port', '1', '--type', 'hdd', '--medium', '"{0}"'.format(vm_vdi)])
        self.execute_process(
            ['storageattach', '"{0}"'.format(uuid), '--storagectl', self.default_sata_controller_type,
             '--port', '1', '--type', 'hdd', '--medium', '"{0}"'.format(vm_vdi)])

    def attach_iso(self, uuid, iso_path):
        if 'ini' == iso_path:
            iso_path = self.ini_get(self.BLOCK_VM, self.PARAM_DEFAULT_ISO)
        self.execute_process(
            ['storageattach', '"{0}"'.format(uuid), '--storagectl', self.default_ide_controller_type, '--port', '1',
             '--type',
             'dvddrive',
             '--device', '0', '--medium', iso_path])
        self.log('Attached {0}'.format(iso_path))

    def create_ms(self, ms_vmname, litp_iso=None, force=False, vbox_storage_root=None, group_name=None):
        if force:
            _all = self.list_by_uuid()
            _name = '/{0}/{1}'.format(group_name, ms_vmname)
            for _uuid, name in _all.items():
                if _name == name:
                    self.delete_vm(_uuid)
                    break
        os_type = self.ini_get(self.BLOCK_MS, self.PARAM_OST)
        uuid = self.create_vm(ms_vmname, group_name, os_type, vbox_storage_root)
        vm_mem_size = self.ini_get(self.BLOCK_MS, self.PARAM_MEMS)
        vm_disk_size = self.ini_get(self.BLOCK_MS, self.PARAM_FSS)
        adapter_count = self.ini_get(self.BLOCK_MS, self.PARAM_NICC, 1)
        hardware_utc = self.ini_get(self.BLOCK_MS, self.PARAM_HWUTC, 'off')
        self.modify_vm(uuid, ms_vmname, group_name, vm_mem_size, vm_disk_size, adapter_count, hardware_utc)
        self.log('Updated {0} with settings for MS type VM'.format(ms_vmname))
        if litp_iso:
            if 'ini' == litp_iso:
                litp_iso = self.ini_get(self.BLOCK_VM, self.PARAM_DEFAULT_ISO)
            self.attach_iso(uuid, litp_iso)
        else:
            self.log('No ISO attached to {0}'.format(ms_vmname))

    def create_controller(self, vmname, recreate=False, vbox_storage_root=None, group_name=None):
        if recreate:
            _all = self.list_by_uuid()
            _name = '/{0}/{1}'.format(group_name, vmname)
            for _uuid, name in _all.items():
                if _name == name:
                    self.delete_vm(_uuid)
                    break
        os_type = self.ini_get(self.BLOCK_MN, self.PARAM_OST)
        uuid = self.create_vm(vmname, group_name, os_type, vbox_storage_root)
        vm_mem_size = self.ini_get(self.BLOCK_MN, self.PARAM_MEMS)
        vm_disk_size = self.ini_get(self.BLOCK_MN, self.PARAM_FSS)
        adapter_count = self.ini_get(self.BLOCK_MN, self.PARAM_NICC, 1)
        hardware_utc = self.ini_get(self.BLOCK_MN, self.PARAM_HWUTC, 'off')
        self.modify_vm(uuid, vmname, group_name, vm_mem_size, vm_disk_size, adapter_count, hardware_utc)
        self.log('Updated {0} with settings for Managed Node type VM'.format(vmname))

    def _get_bit_count(self, mask):
        n = 0
        while mask:
            n += mask & 1
            mask >>= 1
        return n

    def netmask_to_address(self, netmask):
        bitcount = 0
        parts = netmask.split('.')
        for part in parts:
            bitcount += self._get_bit_count(int(part))
        return bitcount

    def list_hostonly_adapters(self):
        iface_list = self.execute_process(['list', 'hostonlyifs'])
        lines = iface_list.split('\n')
        interfaces = {}
        gather_interface = {}
        for entry in lines:
            entry = entry.strip()
            if entry == '':
                continue
            kvp = entry.split(':')
            key = kvp[0].strip()
            value = kvp[1].strip()
            if key == 'Name' and 'Name' in gather_interface:
                interfaces[gather_interface['Name']] = gather_interface
                gather_interface = {}
            gather_interface[key] = value
        if gather_interface:
            interfaces[gather_interface['Name']] = gather_interface
        # Work out the adapters MS settings
        for adapter, data in interfaces.items():
            gateway = data['IPAddress']
            groups = search('([0-9]+\.[0-9]+\.[0-9]+)\.([0-9]+)', gateway)
            subnet = groups.group(1)
            start = groups.group(2)
            ms_ipaddress = '{0}.{1}'.format(subnet, int(start) + 1)
            bitcount = self.netmask_to_address(data['NetworkMask'])
            data['MS Gateway'] = gateway
            data['MS IPv4 Address'] = '{0}/{1}'.format(ms_ipaddress, bitcount)
        return interfaces


def list_vm_names(vboxmanage):
    groups = {}
    for uuid, name in vboxmanage.list_by_uuid().items():
        vminfo = vboxmanage.get_vm_details(uuid)
        if vminfo['group'] not in groups:
            groups[vminfo['group']] = []
        groups[vminfo['group']].append('{0} UUID:{1}'.format(name, uuid))
    for gp, names in groups.items():
        print(gp)
        for n in names:
            print('\t{0}'.format(n))


def show_vm_info(vboxmanage, uuid):
    info = vboxmanage.get_vm_details(uuid)
    print('{0}'.format(info['name']))
    sorted_keys = info.keys()
    sorted_keys.sort()
    for key in sorted_keys:
        print('\t{0}: {1}'.format(key, info[key]))


def list_hostonly_adapter(vboxmanage):
    hoal = vboxmanage.list_hostonly_adapters()
    for key, data in hoal.items():
        print('{0}'.format(key))
        for k, v in data.items():
            print('\t{0}: {1}'.format(k, v))


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('--ini', help='INI file with VM defaults', dest='vm_ini')
    parser.add_option('--vm_storage', help='VM Storage Directory', dest='vm_storage')
    parser.add_option('--uuid', dest='uuid')

    create_tor_group = OptionGroup(parser, 'TOR VM Group', 'e.g. vm.py --create_group="LITP SP26" --desc="(SP26)"')
    create_tor_group.add_option('--create_group', dest='group_name')
    create_tor_group.add_option('--force', dest='force', action='store_true')
    create_tor_group.add_option('--iso', help='VM Boot ISO (MS Only)', dest='lms_boot_iso')
    create_tor_group.add_option('--desc', dest='desc')
    parser.add_option_group(create_tor_group)
    #
    delete_vm = OptionGroup(parser, 'Delete a VM', 'e.g. vm.py --delete --uuid={0d36f28d-3022-4eb3-93ec-2b630e2ef8a9}')
    delete_vm.add_option('--delete', action='store_true')
    parser.add_option_group(delete_vm)

    list_vms = OptionGroup(parser, 'List all VMs', 'python vm.py --list')
    list_vms.add_option('--list', dest='list_vms', action='store_true')
    parser.add_option_group(list_vms)

    list_hoa = OptionGroup(parser, 'List Host Only Adapters', 'python vm.py --hoa')
    list_hoa.add_option('--hoa', dest='hoa', action='store_true')
    parser.add_option_group(list_hoa)

    show_vm = OptionGroup(parser, 'Show VM info', 'e.g. vm.py --show --uuid={0d36f28d-3022-4eb3-93ec-2b630e2ef8a9}')
    show_vm.add_option('--show', action='store_true')
    parser.add_option_group(show_vm)

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)
    (options, args) = parser.parse_args()
    if not options.vm_ini:
        options.vm_ini = os.path.abspath(sys.argv[0])
        options.vm_ini = '{0}/vm.ini'.format(os.path.dirname(options.vm_ini))
    vboxmanage = vboxmanage_api(options.vm_ini)
    if options.list_vms:
        list_vm_names(vboxmanage)
    elif options.show:
        show_vm_info(vboxmanage, options.uuid)
    elif options.hoa:
        list_hostonly_adapter(vboxmanage)
    elif options.delete:
        vboxmanage.delete_vm(options.uuid)
    elif options.group_name:
        group_name = options.group_name
        lms_name = 'LMS'
        if options.desc:
            lms_name += ' {0}'.format(options.desc)
        vboxmanage.create_ms(lms_name, options.lms_boot_iso, options.force, options.vm_storage, group_name)
        sc_count = int(vboxmanage.ini_get(vboxmanage_api.BLOCK_VM, vboxmanage_api.PARAM_VM_SCC))
        for _id in range(1, sc_count + 1):
            peer_name = 'Peer-{0}'.format(_id)
            if options.desc:
                peer_name += ' {0}'.format(options.desc)
            vboxmanage.create_controller(peer_name, options.force, options.vm_storage, group_name)


        # parser.add_option('-c', '--create', help='Create a VM', dest='create_vm', action='store_true')
        # parser.add_option('-d', '--delete', help='Delete a VM', dest='delete_vm', action='store_true')
        # parser.add_option('-z', '--ini', help='INI file with VM defaults', dest='vm_ini')
        # parser.add_option('-a', '--attach', help='Attach an ISO', dest='attach_iso')
        # parser.add_option('-n', '--name', help='VM name', dest='vm_name')
        #
        # parser.add_option('--tor_vms', help='Create a TOR VM group', dest='tor_name')
        #
        # create_vm_options = OptionGroup(parser, 'Create VM Options')
        # parser.add_option_group(create_vm_options)
        # create_vm_options.add_option('--force', help='Recreate a VM', dest='force', action='store_true')
        # create_vm_options.add_option('--type', help='VM type [ms|sc]', dest='vm_type')
        # create_vm_options.add_option('--vm_storage', help='VM Storage Directory', dest='vm_storage')
        # create_vm_options.add_option('--iso', help='VM Boot ISO (MS Only)', dest='vm_boot_iso')
        # create_vm_options.add_option('--boot', help='Boot the VM after creating it', dest='boot_vm', action='store_true')
        #
        # parser.add_option('--info', help='View VM info', dest='vm_info', action='store_true')
        # info_opt_group = OptionGroup(parser, 'VM Info Options')
        # parser.add_option_group(info_opt_group)
        # info_opt_group.add_option('--hoa', help='List Host Only Adapters', dest='list_hoa', action='store_true')
        # info_opt_group.add_option('--vmn', help='List VMs', dest='list_vms', action='store_true')
        # info_opt_group.add_option('--vmi', help='List VM Info (* for all)', dest='list_vm_info')
        #
        # if len(sys.argv) <= 1:
        #     parser.print_help()
        #     sys.exit(2)
        # (options, args) = parser.parse_args()
        # if not options.vm_ini:
        #     options.vm_ini = os.path.abspath(sys.argv[0])
        #     options.vm_ini = '{0}/vm.ini'.format(os.path.dirname(options.vm_ini))
        # vboxmanage = vboxmanage_api(options.vm_ini)
        # if options.tor_name:
        #     group_name = options.tor_name
        #     sc_count = int(vboxmanage.ini_get(vboxmanage_api.BLOCK_VM, vboxmanage_api.PARAM_VM_SCC))
        #     options.vm_name = 'LMS ({0})'.format(group_name)
        #     options.vm_type = 'ms'
        #     create_vm(options, vboxmanage, group_name)
        #     # Set the boot option to False for the SC nodes as there's no point in booting them until the MS & landscape
        #     # has been completed.
        #     options.boot_vm = False
        #     for _id in range(1, sc_count + 1):
        #         options.vm_name = 'SC-{0} ({1})'.format(_id, group_name)
        #         options.vm_type = 'sc'
        #         create_vm(options, vboxmanage, group_name)
        # elif options.create_vm:
        #     create_vm(options, vboxmanage)
        # elif options.delete_vm:
        #     delete_vm(options, vboxmanage)
        # elif options.attach_iso:
        #     attach_iso(options, vboxmanage)
        # elif options.vm_info:
        #     vm_info(options, vboxmanage)
