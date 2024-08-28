#!/usr/bin/python

import sys, os, re

def main():
  if len(sys.argv) != 2:
    print 'Usage: {0} <macaddress>'.format(sys.argv[0])
    sys.exit(1)
  match = re.search(r'^([0-9A-Fa-f]{1,2}[:]){5}([0-9A-Fa-f]{1,2})$', sys.argv[1])
  if not match:
    print 'Wrong mac address: {0}'.format(sys.argv[1])
    sys.exit(1)
  macB = sys.argv[1].split(':')
  hexB = macB[0]
  binB = bin(int(hexB, 16))[2:].zfill(8)
  if (binB[6] == '1'):
    flipB = binB[:6] + '0' + binB[7]
  else:
    flipB = binB[:6] + '1' + binB[7]
  hexB = hex(int(flipB, 2))[2:]
  ipv6Local = 'fe80::{0}{1}:{2}ff:fe{3}:{4}{5}'.format(hexB, macB[1].zfill(2), \
    macB[2].zfill(2), macB[3].zfill(2), macB[4].zfill(2), macB[5].zfill(2)).lower()
  print ipv6Local
  sys.exit(0)

if __name__ == '__main__':
  main()
