#!/usr/bin/env python

import datetime
import sys
import traceback

class ScriptSpecificError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

def timeStamp(string):
	# Prints a timestamp to stdout 
	# string - a string to print with the timestamp
	timestamper = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
	print string, " TIME: ", timestamper

def handleException(exception, value='', withTraceback=True):
	# Handles an exception raised
	printException(exception, value, withTraceback)
	raise exception

def printException(exception, value='', withTraceback=False):
	timeStamp("EXCEPTION:")
	(xtype, xvalue, xtraceback) = sys.exc_info()
	print "exception type:", xtype
	if value <> '':
		xvalue = value
	print "value:", xvalue
	if ((withTraceback) and (xtraceback != None)):
		print "printing traceback"
		print traceback.format_exc()
