#!/usr/bin/env python

import paramiko

class SSHSocket:
    def __init__(self):
        self.ssh = None
        self.user = ''
        self.passwd = ''

        self.host = '127.0.0.1'
        self.sshport = 22

        self.connectTimeout = 30
        self.lookForKeys = False
        self.allowAgent = False
        self.shell = None

    def setHost(self, host):
        self.host = host

    def setUser(self, user):
        self.user = user

    def setPasswd(self, passwd):
        self.passwd = passwd

    def connect(self):
	print("iLOSSHSocket: connecting to %s using credentials %s/%s" % (self.host, self.user, '******'))
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh.connect(self.host,
                             username=self.user,
                             password=self.passwd,
                             timeout=self.connectTimeout,
                             look_for_keys=self.lookForKeys,
                             allow_agent=self.allowAgent)
            print('iLOSSHSocket: connected to %s' % self.host)
            return True
        except:
            print('iLOSSHSocket: could not connect to %s' % self.host)
            self.ssh = None
            return False

    def disconnect(self):
        if self.ssh != None:
            try:
                self.ssh.close()
            except:
                self.ssh = None
        else:
            self.ssh = None

    def execute(self, command):
        stdin, stdout, stderr = self.ssh.exec_command(command)
        return stdin, stdout, stderr

    def getShell(self):
        if self.ssh != None:
            return self.ssh.invoke_shell(term='vt100')
        else:
            return None
