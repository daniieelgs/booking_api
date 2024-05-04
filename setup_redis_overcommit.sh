#!/bin/bash

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root." 1>&2
   exit 1
fi

echo "Setting up vm.overcommit_memory a 1..."
sysctl vm.overcommit_memory=1

echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf

echo "Done"