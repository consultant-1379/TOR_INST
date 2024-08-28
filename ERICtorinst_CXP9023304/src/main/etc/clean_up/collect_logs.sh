#/bin/bash

##
## ./collect_logs.sh - collects litp relevant system logs into collect_logs.DDMMYYHHMM.tgz archive
##

sDate=`date +%d%m%Y%H%M`;   ## system date and time
 
# restart the landscaped service
service landscaped restart &> /dev/null

# tar up relevant log files
tar czf collect_logs_$sDate.tgz /var/log/messages /var/log/litp /var/log/cobbler /var/lib/landscape /var/lib/cobbler/kickstarts /etc/sysconfig/network-scripts/ifcfg-* /root /opt/ericsson/nms/litp/etc/puppet/manifests/inventory /opt/ericsson/nms/litp/bin/samples/local_vm /opt/ericsson/nms/litp/bin/samples/single_blade /opt/ericsson/nms/litp/bin/samples/multi_blade /opt/ericsson/nms/litp/.version &> /dev/null

exit 0

