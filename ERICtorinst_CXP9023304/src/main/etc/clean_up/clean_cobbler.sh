#!/bin/bash
for sysname in $(cobbler system list); do
	cobbler system remove --name "$sysname"
done

for distroname in $(cobbler distro list); do
	cobbler distro remove --name "$distroname"
done

exit 0

