#!/usr/bin/perl -w
use strict;

if ($#ARGV<2) {
    die ("usage: ./.createSiteSpecificInventory.pl <Site Engineering file> <Inventory template file> <output filename>");
}

open(my $fh_SiteFile, '<', $ARGV[0]) or die "Can't read file $ARGV[0]\n";
open(my $fh_ScriptToMod, '<', $ARGV[1]) or die "Can't read file $ARGV[1]\n";
open(my $fh_OutputFile, '>', $ARGV[2]) or die "Can't read file $ARGV[2]\n";

my %hash;
while (<$fh_SiteFile>)
{
    chomp;
    #skip comments and empty lines
    m/^\s*#/ and next;
    m/^\s*$/ and next;

    # Fix TORD-905 to allow '=' character to be used in value (previous 'split' 
    # implementation would remove = and subsequent characters).
    #my ($key, $val) = split /=/;
    my ($key, $val) = ($_ =~ /(.*?)=(.*)/);

    # remove DOS carriage return chars
    $val =~ tr/\015//d;
    # remove leading spaces
    $val =~ s/^\s+//;
    # remove trailing spaces
    $val =~ s/\s+$//;
    $hash{$key} = $val;

}

{
    my $slurpFile;
    local $/;  # change the line separator to undef
    $slurpFile= <$fh_ScriptToMod>;

    foreach my $key (keys %hash) {
        my $searchString = $key;
        my $replaceString = $hash{$key};
        $slurpFile =~ s/%%$searchString%%/$replaceString/g;
    }

    print $fh_OutputFile $slurpFile;
}

close $fh_SiteFile;
close $fh_ScriptToMod;
close $fh_OutputFile;
