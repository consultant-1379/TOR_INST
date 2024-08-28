#!/bin/bash
service puppet stop
service puppetmaster stop
puppetca --clean ms1
rm -rf /var/lib/puppet/ssl/*
rm -f /root/.ssh/known_hosts
service puppetmaster start
service puppet start
exit 0
