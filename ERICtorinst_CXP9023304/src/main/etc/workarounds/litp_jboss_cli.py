import subprocess
import litp_jboss_common as common


class LitpJbossCli(object):
    """
    JBOSS CLI
    """
    def __init__(self, config):

        self.config = config

        common.container_name = self.config.get('instance_name')

        self.jboss_cli = config.make_env()['JBOSS_CLI']

    def _exec_cmd(self, cmd):
        common.log("Executing JBOSS CLI command: %s" % cmd, level="DEBUG")
        p = subprocess.Popen(cmd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True,
                             env=self.config.make_env())
        try:
            p.wait(timeout=120)
        except Exception as e:
            return (1, '', "JBOSS CLI command timed out: %s" % e)
        rc = p.returncode
        stdout = p.stdout.readlines()
        stderr = p.stderr.readlines()
        common.log("JBOSS CLI command results " + \
                     "rc:%s, stdout:%s, stderr:%s"
                     % (rc, stdout, stderr), level="DEBUG")
        return (rc, stdout, stderr)

    def run(self, cmd):
        assert cmd is not None
        return self._exec_cmd(
                    cmd='%s -c --command="%s"' % (self.jboss_cli, cmd))

    def run_commands(self, cmds):
        assert cmds is not None
        assert len(cmds) > 0
        return self._exec_cmd(
                cmd='%s -c --commands="%s"' % (self.jboss_cli, ','.join(cmds)))

    def __repr__(self):
        return str(self.__class__)
