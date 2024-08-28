import paramiko

__author__ = 'eeipca'


class SSHSocket:
	def __init__(self, debug=False):
		self.ssh = None
		self.user = ''
		self.passwd = None

		self.host = '127.0.0.1'
		self.sshport = 22

		self.connectTimeout = 30
		self.lookForKeys = True
		self.allowAgent = True
		self.shell = None
		self.DEBUG = debug

	def debug(self, message):
		if self.DEBUG:
			print(message)

	def setHost(self, host):
		self.host = host

	def setUser(self, user):
		self.user = user

	def setPasswd(self, passwd):
		self.passwd = passwd

	def connect(self):
		self.debug("iLOSSHSocket: connecting to %s using credentials %s/%s" % (self.host, self.user, '******'))
		self.ssh = paramiko.SSHClient()
		self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ok = False
		try:
			self.ssh.connect(self.host, username=self.user, password=self.passwd, timeout=self.connectTimeout,
			                 look_for_keys=self.lookForKeys, allow_agent=self.allowAgent)
			self.debug('iLOSSHSocket: connected to %s' % self.host)
			ok = True
		finally:
			if not ok:
				self.ssh = None
		return ok

	def disconnect(self):
		if self.ssh is not None:
			try:
				self.ssh.close()
			except:
				self.ssh = None
		else:
			self.ssh = None

	def _execute(self, command):
		if not self.ssh:
			raise IOError('ssh: Not connected')
		channel = self.ssh.get_transport().open_session()
		channel.exec_command(command)
		stdout = channel.makefile('rb', -1)
		stderr = channel.makefile_stderr('rb', -1)
		exit_code = channel.recv_exit_status()
		if exit_code != 0:
			raise IOError({'rc': exit_code, 'stdout': stdout.readlines(), 'stderr': stderr.readlines()})
		lines = []
		while True:
			line = stdout.readline().strip()
			if len(line) == 0:
				break
			lines.append(line)
		return lines, stderr.readlines()

	def execute(self, command):
		stdout, stderr = self._execute(command)
		if len(stderr) > 0:
			raise IOError(' '.join(stderr))
		return stdout

	def getShell(self):
		if self.ssh is not None:
			return self.ssh.invoke_shell(term='vt100')
		else:
			return None
