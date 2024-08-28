#!/bin/sh
# ********************************************************************
# Ericsson LMI                SCRIPT
# ********************************************************************
#
# (c) Ericsson LMI 2013 - All rights reserved.
#
# The copyright to the computer program(s) herein is the property
# of Ericsson LMI. The programs may be used
# and/or copied only with the written permission from Ericsson LMI or in accordance with the terms and conditions stipulated
# in the agreement/contract under which the program(s) have been
# supplied.
#
# ********************************************************************
# Name    : lock_unlock.sh
# Package : Utility Scripts
# Date    : 04/09/2013
# Revision: 1
# Purpose : Script locks or unlock all running JBOSS instances
#			User can also choose to just lock, or unlock instances separately.
# Usage   : <script_name> <arguments>
# Author(s) : Kieran O Brien
# 
#
# ********************************************************************


source_dependencies()
{
  dir=`dirname $0`
  SCRIPT_PATH=`cd ${dir}/ 2>/dev/null && pwd || ${ECHO} ${dir}`
 . ${SCRIPT_PATH}/common_variables
 . ${SCRIPT_PATH}/common_functions
}

source_dependencies


function usage(){
	printf "Automatically Lock or Unlock (in order) all service instances. \n"
	echo "Usage: `basename $0` <Option>
	<Options>
	-h: Show this message
	-l: Lock all service instances
	-u: Unlock all service instances"
}


# Check that the script was passed arguments and if any equal "help"
if [ $# -eq 0 ] || [ "${1}" == "-h" ] || [ "${1}" == "-help" ]; then
  usage
  exit 0
fi

# Check for bad arguments
if [ $? -ne 0 ] ; then
  usage
  exit 1
fi

while getopts "hlu?" OPTION; do
	case $OPTION in
		h)	usage
			exit 0
			;;	
		l)  lock_all_service_instances
			exit 0
			;;
		u)	unlock_all_service_instances	
			exit 0
			;;
	esac
done