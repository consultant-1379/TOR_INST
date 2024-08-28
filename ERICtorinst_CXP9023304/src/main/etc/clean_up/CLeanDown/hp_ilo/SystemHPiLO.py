#!/usr/bin/env python


from hp_ilo.iLOSSHSocket import SSHSocket
import time
import socket

class SystemHPiLO:
    # This class provides an API to run iLO commands over SSH to the HP iLO interface.
    def __init__(self):
        self.host = ''
        self.username = ''
        self.password = ''
        self.iLOConnection = None
        self.testMode = False

    def setTestMode(self, tm):
        self.testMode = tm

    def setHost(self, host):
        self.host = host

    def setUser(self, username):
        self.username = username

    def setPassword(self, password):
        self.password = password

    def _sshConnect(self):
        s = SSHSocket()
        s.setHost(self.host)
        s.setUser(self.username)
        s.setPasswd(self.password)
        if s.connect():
            self.iLOConnection = s
        else:
            self.iLOConnection = None

    def _sshDisconnect(self):
        if self.iLOConnection != None:
            self.iLOConnection.disconnect()
        self.iLOConnection = None

    def _runCmd(self, cmd, run=True):
        resultList = []
        if self.iLOConnection != None:
            if run:
	        print("SystemHPiLO: iLOCommand %s executed on %s" % (cmd, self.host))
        resultList = self.iLOConnection.execute(cmd)[1].readlines()
        return resultList

    def iLOPowerReset(self):
	resultList = []
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        cmd = 'POWER'
        resultList = self._runCmd(cmd)
        for i in resultList:
            if i.find('power: server power is currently: Off') > -1:
                cmd = 'POWER ON'
        self._sshDisconnect()
        time.sleep(1)
        self._sshConnect()
        if cmd != 'POWER ON':
            cmd = 'POWER RESET'
        resultList = self._runCmd(cmd)
	print('SystemHPiLO: POWER RESET of system %s' % self.host)
        self._sshDisconnect()

    def iLOPowerStatus(self):
	resultList = []
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: Checking power status')
        cmd = 'POWER'
        resultList = self._runCmd(cmd)
        self._sshDisconnect()
	return resultList

    def iLOPowerON(self):
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: POWER ON of system %s' % self.host)
        cmd = 'POWER ON'
        self._runCmd(cmd)
        self._sshDisconnect()

    def iLOPowerOFF(self):
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: POWER OFF of system %s' % self.host)
        cmd = 'POWER OFF'
        self._runCmd(cmd)
        self._sshDisconnect()

    def vmCDROMInsert(self, url):
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: Virtual media CDROM insert %s' % url)
        cmd = 'vm cdrom insert %s' % url
        self._runCmd(cmd)
        self._sshDisconnect()

    def vmCDROMEject(self):
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: Virtual media CDROM Eject')
        cmd = 'vm cdrom eject'
        self._runCmd(cmd)
        self._sshDisconnect()

    def vmCDROMConnect(self):
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: Virtual media CDROM connect')
        cmd = 'vm cdrom set connect'
        self._runCmd(cmd)
        self._sshDisconnect()

    def vmCDROMBootOnce(self):
        if self.iLOConnection == None:
            self._sshConnect()
            if self.iLOConnection == None:
                print("SystemHPiLO: No connection to ILO")
                return
        print('SystemHPiLO: Virtual media CDROM set boot once')
        cmd = 'vm cdrom set boot_once'
        self._runCmd(cmd)
        self._sshDisconnect()
