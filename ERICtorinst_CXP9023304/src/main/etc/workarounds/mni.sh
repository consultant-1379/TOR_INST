#!/bin/bash
# chkconfig: 345 17 80
# description: configure interface for management network

# start up script to configure eth3 interface after LMS reboot
# with the management network IP address


#Configurable parameters(example provided, please change it to your values):
#
#eth            - interface name, which is connected to the management network
#ip_address     - ip address must be in CIDR format like 192.168.24.10/24
#broadcast      - broadcast address 192.168.24.255
#
#################################################################
eth="eth30"
ip_address="192.168.24.10/24"
broadcast="192.168.24.255"
#################################################################




IP=/sbin/ip
ECHO=/bin/echo
GREP=/bin/grep

. /etc/init.d/functions

start()
{
$ECHO -n "mni: starting $eth : "
result_=$($IP addr show dev $eth 2>&1)
if [ $? -ne 0 ]
then
		$ECHO "No $eth ethernet interface exist."
        echo_failure
		$ECHO ""
        exit 1
fi
result_=$($IP addr show dev $eth 2>&1|$GREP ${ip_address})
if [ $? -eq 0 ]
then
        $ECHO -n "already configured $eth"
        echo_success
        $ECHO ""
        exit 0
fi


result_=$($IP addr add dev ${eth} ${ip_address} broadcast ${broadcast})
if [ $? -ne 0 ]
then
        $ECHO "mni: Failed to configure ip address on $eth"
        $ECHO "${result_}"
        echo_failure
        $ECHO ""
        exit 1
fi

result_=$($IP link set $eth up)
if [ $? -ne 0 ]
then
        $ECHO -n  "Failed to bring interface $eth up."
        echo_failure
        $ECHO "${result_}"
        exit 1
fi
$ECHO -n "$eth successfully started."
echo_success
$ECHO ""
}

stop()
{
$ECHO -n "mni: stopping $eth : "

result_=$($IP addr show dev $eth 2>&1)
if [ $? -ne 0 ]
then
        $ECHO -n "No $eth ethernet interface exist."
        echo_failure
        $ECHO ""
        exit 1
fi

_result_=$(status|$GREP ${ip_address})
if [ $? -eq 0 ]
then
        result_=$($IP addr del dev $eth ${ip_address})
        if [ $? -ne 0 ]
        then
                $ECHO "Failed to stop interface $eth ."
                $ECHO "${result_}"
                exit 1
        fi
       $ECHO -n "successfully stopped"
else
       $ECHO -n "$eth probably already stopped."
fi
echo_success
$ECHO ""
}

restart()
{
stop
start
}

status()
{
$IP addr show dev $eth
}

case "$1" in
start)
        start
        ;;
stop)
        stop
        ;;
restart)
        restart
        ;;
status)
        status
        ;;

*)
        echo $"Usage: $0 {start|stop|restart|status}"
        exit 1
esac

exit $?