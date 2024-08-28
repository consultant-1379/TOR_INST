from optparse import OptionParser
import sys
from amf.amf_api import amf_api
from litp.litp_helper import litp_helper

__author__ = 'eeipca'


class service_status:
    def __init__(self, landscape_host='localhost', au=None, ap=None, landscape_port=litp_helper.DEFAULT_LS_PORT):
        self.landscape_host = landscape_host
        self.litp = litp_helper(self.landscape_host, landscape_port)
        cmw_nodes = self.get_cmw_nodes()
        self.amf = amf_api(cmw_nodes[0], au, ap)
        self.amf.connect()

    def cleanup(self):
        # noinspection PyBroadException
        try:
            self.amf.disconnect()
        except:
            pass

    def get_services(self):
        return self.litp.search_by_reource_type(self.litp.P_CLUSTER, self.litp.R_SERVICE_GROUP)

    def get_availability_model(self, litp_sg_name):
        properties = self.litp.get_properties(self.litp.P_CLUSTER + '/' + litp_sg_name, ['availability_model'])
        return properties['availability_model']

    def get_amf_sg_for_litp_sg(self, litp_sg_name):
        base_dn = 'safApp=%s_App' % litp_sg_name
        groups = self.amf.get_by_class_type(self.amf.C_SERVICE_GROUP, base_dn=base_dn, scope=self.amf.SCOPE_SUBLEVEL)
        return groups[0]

    def check_states(self, litp_sg_name, sua, state_sua, host_sua, sub, state_sub, host_sub, expected_state,
                     state_type):
        if state_sua != expected_state or state_sub != expected_state:
            msg = 'Both SU\'s for {0} are not {1}'.format(litp_sg_name, expected_state)
            msg = '{0}\n\t{1}: {2} on {3} [Expected {4} state is {5}]'.format(msg, sua, state_sua, host_sua, state_type,
                                                                              expected_state)
            msg = '{0}\n\t{1}: {2} on {3} [Expected {4} state is {5}]'.format(msg, sub, state_sub, host_sub, state_type,
                                                                              expected_state)
            raise EnvironmentError(msg)

    def verify_2n(self, litp_sg_name, amf_units):
        expected_su_count = 2
        if len(amf_units) != expected_su_count:
            raise EnvironmentError(
                'There should be %d AMF service units defined for %s but there\' only %d defined!' % (
                    expected_su_count, litp_sg_name, len(amf_units)))
        units = amf_units.keys()
        sua_amf_hname = amf_units[units[0]]['saAmfNodeClmNode']
        sub_amf_hname = amf_units[units[1]]['saAmfNodeClmNode']
        self.check_states(litp_sg_name, units[0], amf_units[units[0]]['saAmfSUAdminState'], sua_amf_hname,
                          units[1], amf_units[units[1]]['saAmfSUAdminState'], sub_amf_hname, 'UNLOCKED(1)', 'admin')
        self.check_states(litp_sg_name, units[0], amf_units[units[0]]['saAmfSUOperState'], sua_amf_hname,
                          units[1], amf_units[units[1]]['saAmfSUOperState'], sub_amf_hname, 'ENABLED(1)', 'operational')
        self.check_states(litp_sg_name, units[0], amf_units[units[0]]['saAmfSUReadinessState'], sua_amf_hname,
                          units[1], amf_units[units[1]]['saAmfSUReadinessState'], sub_amf_hname, 'IN-SERVICE(2)',
                          'readiness')
        saAmfSUPresenceState_sua = amf_units[units[0]]['saAmfSUPresenceState']
        saAmfSUPresenceState_sub = amf_units[units[1]]['saAmfSUPresenceState']
        active_su = None
        standby_su = None
        if saAmfSUPresenceState_sua == 'UNINSTANTIATED(1)':
            active_su = units[1]
            standby_su = units[0]
            if saAmfSUPresenceState_sub != 'INSTANTIATED(3)':
                raise EnvironmentError('SU %s is in state %s therefor %s should be in state INSTANTIATED(3)' % (
                    units[0], saAmfSUPresenceState_sua, units[1]))
        elif saAmfSUPresenceState_sua == 'INSTANTIATED(3)':
            active_su = units[0]
            standby_su = units[1]
            if saAmfSUPresenceState_sub != 'UNINSTANTIATED(1)':
                raise EnvironmentError('SU %s is in state %s therefor %s should be in state UNINSTANTIATED(1)' % (
                    units[0], saAmfSUPresenceState_sua, units[1]))
        print('%s is active on host %s (%s) [standby on host %s (%s)]' % (
            litp_sg_name, amf_units[active_su]['saAmfNodeClmNode'], amf_units[active_su]['saAmfSUHostedByNode'],
            amf_units[standby_su]['saAmfNodeClmNode'], amf_units[standby_su]['saAmfSUHostedByNode']))

    def verify_nway_active(self, litp_sg_name, amf_units, litp_units):
        if len(amf_units) != len(litp_units):
            raise EnvironmentError(
                'There should be %d AMF service units defined for %s but there\' only %d defined!' % (
                    len(litp_units), litp_sg_name, len(amf_units)))
        info = []
        host_service_map = {}
        for amf_su, data in amf_units.items():
            amf_su_host = data['saAmfNodeClmNode']
            amf_su_state = data['saAmfSUAdminState']
            amf_su_node = data['saAmfSUHostedByNode']
            if data['saAmfSUAdminState'] != 'UNLOCKED(1)':
                raise EnvironmentError(
                    'SU for {0} on host {1} [{2}] is in wrong admin state {3} [Expected state is UNLOCKED(1)]'.format(
                        litp_sg_name, amf_su_host, amf_su_node, amf_su_state))
            elif data['saAmfSUOperState'] != 'ENABLED(1)':
                raise EnvironmentError(
                    'SU for {0} on host {1} [{2}]is in wrong operational state {3} [Expected state is ENABLED(1)]'.format(
                        litp_sg_name, amf_su_host, amf_su_node, amf_su_state))
            elif data['saAmfSUPresenceState'] != 'INSTANTIATED(3)':
                raise EnvironmentError(
                    'SU for {0} on host {1} [{2}] is in wrong presence state {3} [Expected state is INSTANTIATED(3)]'.format(
                        litp_sg_name, amf_su_host, amf_su_node, amf_su_state))
            elif data['saAmfSUReadinessState'] != 'IN-SERVICE(2)':
                raise EnvironmentError(
                    'SU for {0} on host {1} [{2}] is in wrong readiness state {3} [Expected state is IN-SERVICE(2)]'.format(
                        litp_sg_name, amf_su_host, amf_su_node, amf_su_state))
            info.append('SU for {0} is active on host {1} [{2}]'.format(
                litp_sg_name, amf_su_host, amf_su_node))
            if amf_su_host not in host_service_map:
                host_service_map[amf_su_host] = amf_su
            else:
                raise EnvironmentError('%s SU %s is active on same host as SU %s [%s]' % (
                    litp_sg_name, amf_su, host_service_map[data['saAmfNodeClmNode']], data['saAmfNodeClmNode']))
        print('All %d service units are active for service group %s' % (len(amf_units), litp_sg_name))
        for i in info:
            print('\t%s' % i)

    def show_amf_status(self, litp_sg_name):
        amf_fdn = self.get_amf_sg_for_litp_sg(litp_sg_name)
        availability_model = self.get_availability_model(litp_sg_name)
        amf_service_units = self.amf.list_servicegroup_status(amf_fdn)
        if '2n' == availability_model:
            self.verify_2n(litp_sg_name, amf_service_units)
        elif 'nway-active' == availability_model:
            litp_units = self.litp.search_by_reource_type(self.litp.P_CLUSTER + '/' + litp_sg_name,
                                                          self.litp.R_SERVICE_UNIT)
            self.verify_nway_active(litp_sg_name, amf_service_units, litp_units)
        else:
            raise NotImplementedError(availability_model)

    def get_cmw_nodes(self):
        peer_nodes = self.litp.search_by_reource_type(self.litp.P_CLUSTER, self.litp.R_RHEL_COMPONENT)
        nodes = []
        for node in peer_nodes:
            address = self.litp.get_properties(node + '/ip', wanted_properties=['address'])
            address = address['address']
            nodes.append(address)
        return nodes


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--landscape_host", dest="landscape_host")
    parser.add_option("--sg", dest="service_group")
    parser.add_option("--au", dest="au")
    parser.add_option("--ap", dest="ap")
    (options, args) = parser.parse_args()
    landscape_host = 'localhost'
    if options.landscape_host:
        landscape_host = options.landscape_host
    service_status = service_status(landscape_host, options.au, options.ap)
    exit_code = 0
    try:
        if options.service_group and options.service_group != 'all':
            services = [options.service_group]
        else:
            services = service_status.get_services()
            if not services:
                raise EnvironmentError('No service groups defined in landscape model on host \'%s\'!' % landscape_host)
        for service in services:
            litp_group_name = service.split('/')[-1]
            try:
                service_status.show_amf_status(litp_group_name)
            except EnvironmentError as ee:
                sys.stderr.write('ERROR:%s\n' % str(ee))
                exit_code += 1
    finally:
        service_status.cleanup()
    exit(exit_code)