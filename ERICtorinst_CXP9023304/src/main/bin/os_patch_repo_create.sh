#!/bin/bash

LITP=/usr/bin/litp


$LITP /inventory/deployment1/ms1/repository/patch62_v1 create repository name="patch62_v1" url="file:///var/www/html/patches/rhel_1_2_3"
$LITP /inventory/deployment1/cluster1/sc1/repository/patch62_v1 create repository name="patch62_v1" url="http://MS1/patches/rhel_1_2_3"
$LITP /inventory/deployment1/cluster1/sc2/repository/patch62_v1 create repository name="patch62_v1" url="http://MS1/patches/rhel_1_2_3"

#$LITP /inventory/ allocate
#$LITP /inventory/ configure
#$LITP /inventory validate
#$LITP /cfgmgr apply scope=/inventory
