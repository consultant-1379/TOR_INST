#!/bin/bash

###########################################################################
# COPYRIGHT Ericsson 2013
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
###########################################################################

# $Id: 20130611$
# $Date: 2013-12-09 11:20:10$
# $Author: David O'Shaughnessy$
#
# This script should be executed as JBoss pre-start script in order to configure HornetQ ,
# to be able handle node lock use-case.

#############################################################
#
# Logger Functions
#
#############################################################
info()
{
logger -s -t TOR_JBOSS_PRE_START -p user.notice "INFORMATION ($prg): $@"
}
 
error()
{
logger -s -t TOR_JBOSS_PRE_START -p user.err "ERROR ($prg): $@"
}

#Make sure not to run in SSO container
if [[ (${LITP_JEE_CONTAINER_instance_name} == *SSO*)  ]]; then 
    exit 0
else
	info "Updating HornetQ cluster : my-cluster, for JBoss instance ${LITP_JEE_CONTAINER_instance_name}"
	$JBOSS_CLI -c --commands="/subsystem=messaging/hornetq-server=default/cluster-connection=my-cluster:write-attribute(name=max-retry-interval,value=10000L),/subsystem=messaging/hornetq-server=default/cluster-connection=my-cluster:write-attribute(name=retry-interval-multiplier,value=5)"
	if [[ $? != "0" ]] ; then 
		error "Failed to update HornetQ cluster : my-cluster, for JBoss instance ${LITP_JEE_CONTAINER_instance_name}"
        exit 0
        fi
fi

exit 0