#!/bin/bash
ssh sc-1 '/etc/init.d/puppet stop && /etc/init.d/iptables stop && /etc/init.d/ip6tables stop'
ssh sc-2 '/etc/init.d/puppet stop && /etc/init.d/iptables stop && /etc/init.d/ip6tables stop'

ssh sc-1 'echo 0 > /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts'
ssh sc-2 'echo 0 > /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts'
