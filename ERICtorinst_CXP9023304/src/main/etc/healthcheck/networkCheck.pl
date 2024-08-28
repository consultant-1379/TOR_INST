#!/usr/bin/perl
use strict;
use warnings;

my @hostlist;
if ($#ARGV<0) { 
    die ("usage: ./networkCheck.pl <space separated hostname list of peer nodes, e.g. atrcxb122 atrcxb123>\n");
        }
push @hostlist, @ARGV;


sub runCommandViaSSH
{
    my $hostname = $_[0];
    my $command = $_[1];
    my @output = qx/ssh $hostname $command/;
    return @output;
}

sub verifyIfcfgFiles
{
    my $hostname = $_[0];
    my $device = $_[1];
    my $command = "find /etc/sysconfig/network-scripts/ -name ifcfg-$device";
    my @result = runCommandViaSSH ($hostname,$command);
    if (@result > 0) {
        print "ifcfg file exists for device $device on $hostname: OK\n";
        return 0;
    } else {
        print "ifcfg file does not exist for device $device on $hostname: NOK\n";
        return -1;
    }
}

sub checkIPAddress
{
    my $hostname = $_[0];
    my $device = $_[1];
    my $command = "ip address show dev $device";
    my @result = runCommandViaSSH ($hostname,$command);
    if (@result > 0) {
        if($result[0] =~ m/state UP/) {
            print "device $device is UP\n";
        } else {
            print "device $device is DOWN\n";
            return;
        }
        if($result[2] =~ m/inet\s(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})\/\d{1,2}/) {
            print "IP address is $1\n\n";
            pingTest ($hostname,$1);
        } else {
            print "No IPv4 address configured on device $device\n\n";
        }
    } 
}

sub pingTest
{
    my $hostname = $_[0];
    my $IP = $_[1];
    my $command = "ping -c 2 $IP";

    print "Attempting to ping $IP..\n";
    my @result = runCommandViaSSH ($hostname,$command);
    print "@result\n";
}

sub buildHash
{
    my %networks;
    
    open(my $fh_NetGraphSC, '<', '/opt/ericsson/torinst/etc/NetGraphSC_local.xml') or die "Can't read NetGraph file ";
    {
        my $slurpFile;
        local $/;  # change the line separator to undef
        $slurpFile = <$fh_NetGraphSC>;

        while ($slurpFile =~ /ng-net id="net_(.*?)">\n\s+<children>vlan_(.*?)<\/children/g) {
        $networks {$2} = $1;
        }

        if ($slurpFile =~ /ng-net id="net_(.*?)">\n\s+<children>bond_0<\/children/g) {
        $networks {bond_0} = $1;
        }

    }

    return \%networks
}

{
    my $networks = buildHash('/opt/ericsson/torinst/etc/NetGraphSC_local.xml');
    my $device;

    foreach my $VLAN_ID (keys %$networks) {
        print "###############################################\n";
        print "Checking $networks->{$VLAN_ID} network\n";
        print "###############################################\n\n";
        if ($VLAN_ID eq "bond_0") {
            $device = "bond0";
        } else {
            $device = "bond0.$VLAN_ID";
        }

        foreach (@hostlist) {
            if (verifyIfcfgFiles ($_, $device) == 0) {
                checkIPAddress ($_, $device);
            }
        }
        print "\n";
    } 
}

