#!/bin/sh
AWK=/bin/awk
CAT=/bin/cat
CP=/bin/cp
DATE=/bin/date
ECHO=/bin/echo
GREP=/bin/grep
LITP=/usr/bin/litp
LOGGER=/usr/bin/logger
MKDIR=/bin/mkdir
#find ip's
     for _a_ in `litp /inventory/deployment1/cluster1/ show -rl | ${GREP} instance/ip`; do
v=`litp  ${_a_} show | ${GREP} address`
echo ${_a_} ${v}
done