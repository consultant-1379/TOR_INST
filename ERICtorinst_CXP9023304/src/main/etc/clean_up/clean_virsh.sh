#!/bin/bash
for vmname in `virsh list --all | grep -i VM |gawk '{print $2}'`; do
virsh destroy $vmname
virsh undefine $vmname
done
exit 0
