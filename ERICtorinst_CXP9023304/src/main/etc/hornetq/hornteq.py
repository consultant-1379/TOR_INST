#! /usr/bin/python

__version__ = "1.0.0"

__copyright__ ="""
 *******************************************************************************
 * COPYRIGHT Ericsson 2013
 *
 * The copyright to the computer program(s) herein is the property of
 * Ericsson Inc. The programs may be used and/or copied only with written
 * permission from Ericsson Inc. or in accordance with the terms and
 * conditions stipulated in the agreement/contract under which the
 * program(s) have been supplied.
 *******************************************************************************
 """

__usage__ = """

Used to update hornetq configuration via JBOSS CLI.
Assumes a TOR 13B deployment is installed. Will updates all JBoss instances except SSO.
Must be run on the peer node.
	
"""
import optparse
import os
import subprocess
import sys
import time
import utilities


REST_CALL_TIMEOUT=10
POLLING_DELAY_SECONDS=5
MAX_POLLS=20

VERBOSE=1

SERVICE='HornetQ update service'

COMMANDS='/subsystem=messaging/hornetq-server=default/cluster-connection=my-cluster:write-attribute(name=max-retry-interval,value=10000L),/subsystem=messaging/hornetq-server=default/cluster-connection=my-cluster:write-attribute(name=retry-interval-multiplier,value=5)'

def printOpts(options):
	for k,v in options.__dict__.iteritems():
		utilities.log('%s : %s' % (k,v),SERVICE,'DEBUG',False)


def validate(options):
	invalid=0
	for k,v in options.__dict__.iteritems():
		if v == None or v == '':
			utilities.log('%s is null' % (k),SERVICE,'ERROR',True)
			invalid+=1

	if invalid>0:
		utilities.log('There were validation errors. Not proceeding.',SERVICE,'ERROR',True)
		sys.exit(1)

def readArguments():
	"""
	See http://docs.python.org/library/optparse.html#optparse.Option.type for documentation on optparse
	It's a deprecated library, but the recommended replacement is only in python 2.7, we use 2.6.
	Notes:
	Type can be: "string", "int", "long", "choice", "float" and "complex" -> designates the type of the cli arg
	"""
	parser = optparse.OptionParser( __usage__ )
	parser.add_option("--verbose", action="callback",callback=utilities.optional_arg('on'), dest="verbose",default="off",
        help="Print all output to the command line.Optional argument, off by default", metavar="VERBOSE")
		
	return parser.parse_args()	


(opts,args) = readArguments()

def findJEEContainers():
	ret, out, err = utilities.exec_cmd_1(utilities.LITP_FIND_JEE_CONTAINERS_COMMAND)
	utilities.log("Execute command : %s" % (utilities.LITP_FIND_JEE_CONTAINERS_COMMAND))
	jee_list = None
	if ret == 0:
		jee_list = out.split("\n")
		jee_list.remove('')
		utilities.log("JEEContainer's : %s " % (jee_list))
	else:
		utilities.log("No JEEContainers found!!!!",SERVICE,'ERROR',True)
		sys.exit(1)
	return jee_list

def get_jboss_ips(jee_list):
	ip_addresses = []
	
	for jee_uri in jee_list:
		uri = str(jee_uri)
		if 'SSO' in uri:
			utilities.log("Not configurating anything for SSo")
		else:
			command = "%s%s%s%s" %(utilities.LITP_CLI,uri,utilities.LITP_SHOW_PROPERTIES,'public-listener')
			utilities.log("Execute command : %s " %(command))
			p1 = subprocess.Popen(command.split(),
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
			(props, std_err) = p1.communicate()
			ret = p1.returncode
			utilities.log("STD_OUT : %s" % (props))
			utilities.log("STR_ERR : %s "% (std_err))
			utilities.log("RC : %s" %(ret))
			
		if ret == 0:
			prop = props.split('\n')[2]
			cli = prop.split(": ")[1]
			ip_addresses.append(cli.strip('"'))
	return ip_addresses

def update_hornetq(ip_addresses):
	if os.path.exists('/home/jboss/MedCore_su_0_jee_instance/bin/jboss-cli.sh'):
		JBOSS_CLI='/home/jboss/MedCore_su_0_jee_instance/bin/jboss-cli.sh'
	else:
		JBOSS_CLI='/home/jboss/MedCore_su_1_jee_instance/bin/jboss-cli.sh'
		
	for ip in ip_addresses:
		command = "%s --controller=%s -c --user=root --password=shroot --commands=%s" % (JBOSS_CLI,ip,COMMANDS)
		utilities.log("Execute command : %s " %(command),SERVICE,'INFO',True)
		p1 = subprocess.Popen(command.split(),
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
		(props, std_err) = p1.communicate()
		ret = p1.returncode
		utilities.log("STD_OUT : %s" % (props))
		utilities.log("STR_ERR : %s "% (std_err))
		utilities.log("RC : %s" %(ret))
		if ret == 0:
			utilities.log("HornetQ update : success",SERVICE,'INFO',True)
		else:
			utilities.log("HornetQ update : FAILED, HornetQ not updated for JBoss with IP address %s " % (ip),SERVICE,'ERROR',True)

"""
Set flag if verbose output has been set to on
"""
if opts.__dict__["verbose"] == "on":
	VERBOSE=0

validate(opts)
printOpts(opts)
jee_list = findJEEContainers()
ip_addresses = get_jboss_ips(jee_list)
update_hornetq(ip_addresses)

sys.exit(0)