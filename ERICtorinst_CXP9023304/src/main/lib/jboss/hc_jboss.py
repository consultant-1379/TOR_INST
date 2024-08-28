#!/usr/bin/env python
from optparse import OptionParser
from re import match
from jboss.jboss_cli import jboss_cli, JBossQueryError
from litp.litp_helper import litp_helper


def check_deployables(jboss_cli, litp_cli, jboss_address, service_path):
    deployed = jboss_cli.list_deployed(jboss_address)
    deployables = litp_cli.search_by_reource_type(service_path, litp_cli.R_DEPLOYABLE_ENTITY)
    report = {
    'errors': [],
    'success': []
    }
    for deployable in deployables:
        de_properties = litp_cli.get_properties(deployable, ['name'])
        litp_de_name = de_properties['name']
        if litp_de_name in deployed:
            if deployed[litp_de_name] == 'true':
                report['success'].append('%s is deployed (%s)' % (litp_de_name, deployed[litp_de_name]))
            else:
                report['errors'].append('%s is deployed  but not enabled' % litp_de_name)
        else:
            msg = '{0} is NOT deployed [Currently deployed -> {1}]'.format(litp_de_name, ', '.join(deployed))
            report['errors'].append(msg)
    return report


def check_jms_queues(jboss_cli, litp_cli, jboss_address, jboss_instance_name, service_path):
    jboss_instance_queues = jboss_cli.get_jms_queues(jboss_address)
    modeled_queues = litp_cli.search_by_reource_type(service_path, litp_cli.R_JMS_QUEUE)
    if len(modeled_queues):
        report = {
        'errors': [],
        'success': []
        }
        for modeled_queue in modeled_queues:
            modeled_queue_details = litp_cli.get_properties(modeled_queue, ['jndi', 'name'])
            if modeled_queue_details['jndi'] in jboss_instance_queues:
                for modeled_name in modeled_queue_details['name'].split(','):
                    if modeled_name in jboss_instance_queues[modeled_queue_details['jndi']]:
                        report['success'].append('\'name\' %s is created' % modeled_name)
                    else:
                        report['errors'].append('\t\t\t\'name\' %s is NOT created' % modeled_name)
            else:
                report['errors'].append('Modeled queue \'%s\' is not defined in JBoss instance %s(%s) ' % (
                modeled_queue, jboss_instance_name, jboss_address))
        return report
    else:
        return None


def check_jms_topics(jboss_cli, litp_cli, jboss_address, jboss_instance_name, service_path):
    jboss_instance_topics = jboss_cli.get_jms_topics(jboss_address)
    modeled_topic = litp_cli.search_by_reource_type(service_path, litp_cli.R_JMS_TOPIC)
    if len(modeled_topic):
        report = {
        'errors': [],
        'success': []
        }
        for modeled_topic in modeled_topic:
            modeled_topic_details = litp_cli.get_properties(modeled_topic, ['jndi', 'name'])
            if modeled_topic_details['jndi'] in jboss_instance_topics:
                for modeled_name in modeled_topic_details['name'].split(','):
                    if modeled_name in jboss_instance_topics[modeled_topic_details['jndi']]:
                        report['success'].append('\'name\' %s is created' % modeled_name)
                    else:
                        report['success'].append('\'name\' %s is NOT created' % modeled_name)
            else:
                report['success'].append('Modeled topic \'%s\' is not defined in JBoss instance %s(%s) ' % (
                modeled_topic, jboss_instance_name, jboss_address))
        return report
    else:
        return None


def check_application_count(jboss_cli, expected_app_count, jboss_address, jboss_name):
    report = {
    'errors': [],
    'warnings': [],
    'success': []
    }
    try:
        pib_count = jboss_cli.pib_count(jboss_address)
    except JBossQueryError as jqe:
        if jqe.error_code == 404:
            report['warnings'].append('PIB not deployed in %s' % jboss_name)
            return report
        else:
            raise jqe
    if pib_count:
        if pib_count == expected_app_count:
            report['success'].append(
                'OK application visibilty count for {0} Expected:{1} Actual:{2}'.format(jboss_name, expected_app_count,
                                                                                        pib_count))
        else:
            report['errors'].append(
                'Incorrect application visibilty count for {0} Expected:{1} Actual:{2}'.format(jboss_name,
                                                                                               expected_app_count,
                                                                                               pib_count))
    else:
        report['errors'].append('No PIB count returned for {0}'.format(jboss_name))
    return report


def print_report(report, errors_only):
    errors = False
    for line in report['errors']:
        print('\t\tERROR: %s' % line)
        errors = True
    if 'warnings' in report:
        for line in report['warnings']:
            print('\t\tWarning: %s' % line)
    if not errors_only:
        for line in report['success']:
            print('\t\tSUCCESS: %s' % line)
    return errors


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--landscape_host", dest="landscape_host")
    parser.add_option("--sg", dest="service_group", default="all")
    parser.add_option("--errors_only", dest="errors_only", action="store_true", default=False)
    parser.add_option("--verbose", action="store_true", default=False)
    (options, args) = parser.parse_args()

    landscape_host = 'localhost'
    if options.landscape_host:
        landscape_host = options.landscape_host
    group = ''
    if options.service_group and options.service_group != 'all':
        group = options.service_group
    litp = litp_helper(landscape_host)
    jboss = jboss_cli(options.verbose)
    base_path = litp.P_CLUSTER
    services = litp.search_by_reource_type('%s/%s' % (base_path, group), litp.R_SERVICE_UNIT)
    if not services:
        print('No service units found under %s' % base_path)
        exit(1)
    errors = False
    expected_app_count = 0
    for service_path in services:
        if match('.*?(SSO|httpd|logstash).*', service_path):
            continue
        packages = litp.search_by_reource_type(service_path, litp.R_PACKAGE, 'pkg')
        for p in packages:
            if not match('.*camel.*', p):
                expected_app_count += 1

    for service_path in services:
        print('Checking %s' % service_path)
        try:
            jee_ip = service_path + '/jee/instance/ip'
            if not litp.path_exits(jee_ip):
                print('\t%s is not a JBoss instance, skipping.' % service_path)
                continue
            jboss_address = litp.get_properties(jee_ip, ['address'])
            jboss_address = jboss_address['address']
            if not jboss_address:
                print('\tERROR: No value for property \'address\' defined for %s' % jee_ip)
                errors = True
                continue
            try:
                jboss_name = jboss.get_instance_name(jboss_address)
            except IOError as ioe:
                print('\tCouldn\'t get JBoss instance name for %s (%s)' % (service_path, jboss_address))
                errors = True
                continue
            print('\tChecking deployables for %s(%s)' % (jboss_name, jboss_address))
            report = check_deployables(jboss, litp, jboss_address, service_path)
            if report:
                _errors = print_report(report, options.errors_only)
                if _errors:
                    errors = _errors
            else:
                print('\t\tNo deployables modeled for %s' % service_path)
            print('\tChecking JMS queues for %s(%s)' % (jboss_name, jboss_address))
            report = check_jms_queues(jboss, litp, jboss_address, jboss_name, service_path)
            if report:
                _errors = print_report(report, options.errors_only)
                if _errors:
                    errors = _errors
            else:
                print('\t\tNo JMS queues modeled in %s [%s(%s)]' % (service_path, jboss_name, jboss_address))
            print('\tChecking JMS topics for %s(%s)' % (jboss_name, jboss_address))
            report = check_jms_topics(jboss, litp, jboss_address, jboss_name, service_path)
            if report:
                _errors = print_report(report, options.errors_only)
                if _errors:
                    errors = _errors
            else:
                print('\t\tNo JMS topics modeled in %s [%s(%s)]' % (service_path, jboss_name, jboss_address))
            # if not match('.*?(SSO|httpd|logstash).*', service_path):
            # 	print('\tChecking application visibility count for %s(%s)' % (jboss_name, jboss_address))
            # 	report = check_application_count(jboss, expected_app_count, jboss_address, jboss_name)
            # 	_errors = print_report(report, options.errors_only)
            # 	if _errors:
            # 		errors = _errors
        except JBossQueryError as ioe:
            print('Errors checking %s\n\t%s' % (service_path, str(ioe)))
            errors = True
    if errors:
        exit(1)
    else:
        exit(0)