#!/bin/sh

service landscaped stop

rm -rf /opt/ericsson/nms/litp/etc/puppet/manifests/*
rm -rf /var/lib/landscape/*

service landscaped start

exit 0
