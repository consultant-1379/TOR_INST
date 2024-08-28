#!/usr/bin/python
"""
Provides management interface for JBoss instances and related applications
(Deployable Entities) and resources (JEEProperty, JMSQueue, JMSTopic).
"""
import os
import sys
import signal
import time
import subprocess
import shutil
import re
import json
import stat

import litp_jboss_common as common
import litp_jboss_app
import litp_jboss_cli
import litp_jboss_config

from pn_utils.litp_pn_comp_env import CompEnvInstantiator


class LitpJboss(object):
    """
    LITP JBOSS Manager
    """

    def __init__(self, config):
        # @ivar pid: Linux process ID
        # @type pid: int
        self.pid = None

        self.config = None
        self.new_config = config

        instance_name = self.new_config.get('instance_name')

        self.old_config = litp_jboss_config.LitpJbossConfig.load_config(
                                                        instance_name)

        # init logging prefix variables
        common.container_name = instance_name
        common.de_name = None

        # configuration file
        self._jboss_configuration_file = 'standalone-full-ha.xml'

        # log file
        self._logfile = '/var/log/litp/litp_jboss.log'
        # pid file
        self._pidfile = '/var/run/litp-jboss/' + str(instance_name) + '.pid'

        # @param int: Startup wait time in seconds
        self._startup_wait = 25

        # @param int: Shutdown wait time in seconds
        self._shutdown_wait = 25

        self.setup_new_config()

    def setup_old_config(self):
        if self.old_config is None:
            common.log("Old config data not found! "
                        "Was this container ever started?", echo=True)
            self._exit(1)
        return self.set_config(self.old_config)

    def setup_new_config(self):
        self._check_vars(self.new_config)
        return self.set_config(self.new_config)

    def set_config(self, config):
        previous_config = self.config
        self.config = config
        self.jbosscli = litp_jboss_cli.LitpJbossCli(self.config)

        # jboss utils
        self._jboss_script = os.path.join(self.config.get('home_dir'), \
                                          'bin', 'standalone.sh')
        self._adduser = os.path.join(self.config.get('home_dir'),
                                     'bin', 'add-user.sh')
        self._mgmt_user_files = [
            os.path.join(self.config.get('home_dir'),
                 'domain/configuration',
                 'mgmt-users.properties'),
            os.path.join(self.config.get('home_dir'),
                 'standalone/configuration',
                 'mgmt-users.properties')
        ]

        console_dir = self.config.get('log_dir')
        if not console_dir:
            console_dir = self.config.get('home_dir')

        self._jboss_console_log = os.path.join(console_dir,
                                               'jboss-console.log')
        return previous_config

    def _check_vars(self, config):
        """
        @summary: Checks required variables
        install-source
        instance-name
        management-listener
        name
        public-listener
        @param config: LitpJbossConfig instance
        @type config: LitpJbossConfig
        """
        if config.get('install_source') is None:
            common.log("Please specify JBoss install source", echo=True)
            self._exit(1)

        if config.get('instance_name') is None:
            common.log("Please specify JBoss instance-name", echo=True)
            self._exit(1)

        if config.get('management_listener') is None:
            common.log("Please specify management listener address", echo=True)
            self._exit(1)

        if config.get('public_listener') is None:
            common.log("Please specify public listener", echo=True)
            self._exit(1)

        if config.get('version') is None:
            common.log("Please specify application version", echo=True)
            self._exit(1)

        if config.get('process_user') is None:
            common.log("Please specify process user", echo=True)
            self._exit(1)

    def _verify_pid(self):
        """
        @summary: Set self.pid if process is running.
        If process is not running remove pid file.
        """
        if os.path.exists(self._pidfile) and os.path.isfile(self._pidfile):
            try:
                self.pid = int(open(self._pidfile, 'r').readline() or None)
                common.log("PID is: %s." % (self.pid), level="DEBUG")
            except ValueError:
                self.pid = None

        processes_found = 0
        if self.pid is not None:
            cmd = 'ps --pid %s 2> /dev/null | grep -c %s 2> /dev/null' \
                                                        % (self.pid, self.pid)

            exit_status, stdout, _ = self._exec_cmd(cmd)

            processes_found = stdout[0]

            if int(processes_found) != 1:
                self.pid = None
                common.log("Process (pid %s) is not running." % (self.pid))
                common.log("Cleaning PID file: %s" % (self._pidfile),
                              level="DEBUG")
                if os.path.exists(self._pidfile):
                    os.remove(self._pidfile)
        else:
            common.log("PID is: %s." % str(self.pid))

    def _update_perms(self, path=None):
        if not os.path.exists(path):
            common.log("Path \"%s\" does not exists" % (path), level="ERROR")
            return 1

        cmd = 'chown -R %s:%s "%s"' % (self.config.get('process_user'),
                                           self.config.get('process_group'),
                                           path)

        rc, stdout, stderr = self._exec_cmd(cmd)

        if rc != 0:
            common.log("Error changing ownership of \"%s\" to %s:%s (%s)" \
                 % (path, self.config.get('process_user'),
                    self.config.get('process_group'), stderr),
                 level="ERROR")
            return 1

        return 0

    def _run_fragments(self, fragment_name):
        fragment_dir = self.config.get(fragment_name)
        return common.run_fragments(fragment_dir,
                                    self.config.get('process_user'),
                                    env=self.config.make_env())

    def _exec_cmd(self, cmd, env=None, silent=False):
        if env is None:
            env = self.config.make_env()

        if not silent:
            common.log('running "%s"' % cmd, level="DEBUG")
        return common.exec_cmd(cmd=cmd, env=env)

    def _get_cmd_line_options(self):
        options = ''
        cmd_line_prop = str(self.config.get('command_line_options') or '')
        if '--server-config=' not in cmd_line_prop and \
                self._jboss_configuration_file:
            options += " --server-config=%s " % self._jboss_configuration_file

        if cmd_line_prop:
            options += cmd_line_prop

        name_pairs = [
            ('data_dir', 'jboss.server.data.dir'),
            ('log_dir', 'jboss.server.log.dir'),
            ('public_listener', 'jboss.bind.address'),
            ('public_port_base', 'jboss.http.port'),
            ('management_listener', 'jboss.bind.address.management'),
            ('management_port_native', 'jboss.management.native.port'),
            ('management_port_base', 'jboss.management.http.port'),
            ('internal_listener', 'jboss.bind.address.unsecure'),
            ('port_offset', 'jboss.socket.binding.port-offset'),
            ('default_multicast', 'jboss.default.multicast.address'),
            ('log_file', 'jboss.server.log.file'),
            ('jgroups_bind_addr', 'jgroups.bind_addr'),
            ('jgroups_mping_mcast_addr', 'jgroups.mping.mcast_addr'),
            ('jgroups_mping_mcast_port', 'jgroups.mping.mcast_port'),
            ('jgroups_udp_mcast_addr', 'jgroups.udp.mcast_addr'),
            ('jgroups_udp_mcast_port', 'jgroups.udp.mcast_port'),
            ('messaging_group_address', 'jboss.messaging.group.address'),
            ('messaging_group_port', 'jboss.messaging.group.port'),
            ('instance_name', 'jboss.server.name'),
            ('instance_name', 'jboss.qualified.host.name')]

        for conf_name, property_name in name_pairs:
            val = self.config.get(conf_name)
            if val is not None:
                options += " -D%s=%s" % (property_name, val)

        return options

    def _get_environment(self):
        opts = [('', self.config.get('java_options')),
                ('-Xms', self.config.get('Xms')),
                ('-Xmx', self.config.get('Xmx')),
                ('-XX:MaxPermSize=', self.config.get('MaxPermSize')),
                ]
        opts = [opt[0] + opt[1] for opt in opts if opt[1] is not None]

        return 'JAVA_OPTS="%s"' % ' '.join(opts)

    def _run_daemon(self):
        """
        @summary: Run JBoss process as daemon
        """
        # export JAVA_OPTS="-Xms$Xms -Xmx$Xmx -XX:MaxPermSize=$MaxPermSize"
        cmd_line_options = self._get_cmd_line_options()
        # options=$(pick_options)
        env = self._get_environment()

        # Originally bash script called this:
        # daemon --user $process_user LAUNCH_JBOSS_IN_BACKGROUND=1
        # JBOSS_PIDFILE=$pid_file $jboss_script
        # $options 2>&1 > $jboss_console_log &

        # This is what jboss init.d if there is no daemon is calling:
        # su - $JBOSS_USER -c "JAVA_OPTS=* LAUNCH_JBOSS_IN_BACKGROUND=1 \
        #  JBOSS_PIDFILE=$JBOSS_PIDFILE $JBOSS_SCRIPT -c $JBOSS_CONFIG" 2>&1 \
        #  > $JBOSS_CONSOLE_LOG &
        cmd = 'su - %s -c \'%s LAUNCH_JBOSS_IN_BACKGROUND=1 ' \
              'JBOSS_PIDFILE=%s sg %s "%s %s"\' '\
              '> %s 2>&1 &' \
              % (self.config.get('process_user'),
                 env,
                 self._pidfile,
                 self.config.get('process_group'),
                 self._jboss_script,
                 cmd_line_options,
                 self._jboss_console_log,
                )

        common.log("Starting JBoss in background: %s" % (cmd), level="DEBUG")

        try:
            child_pid = subprocess.Popen(cmd, shell=True).pid

            common.log("Started JBoss with pid %s" % (child_pid),
                          level="DEBUG")
        except Exception as ex:
            common.log("Failed: %s" % (ex), level="DEBUG")
            return 1

        return 0

    def _get_old_app_config(self, name):
        if self.old_config is None:
            return None
        for app_config in self.old_config.apps:
            if app_config.get('name') == name:
                return app_config
        return None

    def _check_all_apps_ok(self):
        if len(self.config.apps) > 0:
            cmds = []
            for app_config in self.config.apps:
                cmds.append('/deployment=%s:read-attribute(name=status)' % \
                            app_config.get('name'))

            exit_status, stdout, stderr = self.jbosscli.run_commands(cmds)
            if exit_status != 0 or len(stderr) > 0:
                return 1
            # count lines that say '  "result" => "OK"\n'
            ok = 0
            for line in stdout:
                if re.match('^ *"result" => "OK"\n$', line):
                    ok += 1
            if ok == len(self.config.apps):
                common.log('All %d deployable entities are OK' % \
                             len(self.config.apps))
                return 0
            else:
                common.log('Expected %d deployable entities to be OK, ' \
                           'found only %d that are.' % \
                             (len(self.config.apps), ok), level="ERROR")
                return 1

    def _start_all_apps(self):
        """
        Will start all the apps defined in the environment.
        If any app fails to start, those apps that did start will be stopped,
        and a non-zero value returned.
        If all apps start sucessfully, zero is returned.
        """

        if len(self.config.apps) > 0:
            common.log('About to start %d deployable entities' % \
                         len(self.config.apps))

            last_started = -1
            for idx in range(len(self.config.apps)):
                app_config = self.config.apps[idx]
                app = litp_jboss_app.LitpJbossApp(app_config)
                common.de_name = app_config.get('name')
                old_config = self._get_old_app_config(app_config.get('name'))
                result = app.start(old_config)
                common.de_name = None
                if result == 0:
                    common.log("Started deployable entity \"%s\"" % \
                               self.config.apps[idx].get('name'))
                    last_started = idx
                else:
                    # Failed to start one app - stop trying to start more
                    common.log("Failed to start deployable entity "
                                 "\"%s\" (%d)" % \
                                 (self.config.apps[idx].get('name'), result))
                    break

            if last_started != (len(self.config.apps) - 1):
                # We failed to start up fully, so we're going to stop
                # whatever we did start.  Since all of the "stop" logic
                # is driven by self.old_config, but we've been starting
                # stuff defined by self.config, we need to copy one to
                # the other so that we properly stop what we've just started.
                self.old_config = self.config

                # Let _stop handle the app shutdown
                return 1

            if self._check_all_apps_ok() != 0:
                return 1

        return 0

    def _stop_all_apps_batch(self):
        """
        Stops all apps in a single cli call
        """
        # First get a map of deployed/running DEs
        running_des = self._get_running_des()
        if not running_des:
            common.log("No deployable entities to stop", echo=True)
            return True
        common.log('About to stop %d deployable entities (%s)' % \
                     (len(running_des), ", ".join([app.get('name') for app in
                         running_des])))

        self._run_app_hooks_batch("pre_shutdown", running_des)
        success = self._stop_all_apps_batch_worker(running_des)

        self._run_app_hooks_batch('post_shutdown', running_des)
        return success

    def _calculate_timeout(self, running_des):
        if not running_des:
            return 0
        # Camel is an app deployed by TOR. When under load it can take up to
        # 5 minutes to shut down. So we assume camel is in our list of DEs,
        # and add a 30 second slack time just in case anything is a bit slow
        camel_timeout = 330
        other_apps_timeout = 120 * (len(running_des) - 1)
        return camel_timeout + other_apps_timeout

    def _sleep(self, secs):
        time.sleep(secs)

    def _stop_all_apps_batch_worker(self, running_des):
        batch = self._create_batch_cli_commands(running_des)
        timeout = self._calculate_timeout(running_des)

        # Set to true to avoid unnecessary polling of DE states for first run
        cli_timed_out = True
        success = False
        max_batch_retries = len(running_des) + 2
        max_timeout_retries = 30
        cli_retries, batch_retries = 0, 0
        while True:
            if not cli_timed_out:
                running_des = self._get_running_des()
                batch = self._create_batch_cli_commands(running_des)
                timeout = self._calculate_timeout(running_des)
            if not batch:
                # No apps to stop
                return True
            common.log('About to stop %d deployable entities (%s) in a batch' \
                     % (len(running_des), ", ".join([app.get('name') for app in
                         running_des])))
            rv, stdout, stderr = self.jbosscli.run_commands(batch, timeout)
            cli_timed_out = False
            if rv == litp_jboss_cli.SUCCESS:
                common.echo_success("Successfully stopped all DEs")
                return True
            if rv == litp_jboss_cli.TIMEOUT:
                common.log("Failed to stop DEs as Jboss cli timed out")
                cli_timed_out = True
                cli_retries += 1
            else:
                # jboss cli outputs deployment errors on stdout
                common.log("Failed to stop DEs due to error encountered." \
                        " stderr: %s" % "\n".join(stdout))
                batch_retries += 1

            if ((cli_retries >= max_timeout_retries) or
                    (batch_retries >= max_batch_retries)):
                common.echo_failure("Max retries to undeploy DEs exceeded")
                return False
            self._sleep(5)
            common.log("Retrying attempt to stop DEs")

    def _get_running_des(self):
        de_states = self._get_deployable_entity_states()

        running_des = [de for de in reversed(self.config.apps)
                if de_states.get(de.get('name'), False)]
        return running_des

    def _create_batch_cli_commands(self, running_des):
        batch = []
        for de in running_des:
            batch.append("undeploy --name=%s --keep-content" % de.get('name'))
        return batch

    def _run_app_hooks_batch(self, stage, running_des):
        common.log("Running %s hooks for all DEs" % (stage), echo=True)
        for app_config in running_des:
            app = litp_jboss_app.LitpJbossApp(app_config)
            common.de_name = app_config.get('name')
            common.log("Running %s hooks for DE %s" % (stage, common.de_name),
                    echo=True)
            rc = app._run_fragments(stage)
            common.log("post_shutdown hooks for DE %s exited with status "\
                    "%s" % (common.de_name, rc))
        common.de_name = None

    def _stop_all_apps(self):
        """
        Will stop all the apps defined in the environment.
        """

        if len(self.config.apps) > 0:
            common.log('About to stop %d deployable entities' % \
                         len(self.config.apps))

            # Stop apps in reverse order

            for app_config in reversed(self.config.apps):
                app = litp_jboss_app.LitpJbossApp(app_config)
                common.de_name = app_config.get('name')
                result = app.stop()
                common.de_name = None
                timeout = self._time() + (15 * 60)
                attempt = 1
                while result == 2 and self._time() < timeout:
                    # JBoss cli might time out if under load, try multiple
                    # times within 15 minutes
                    common.log("Error stopping deployable entity '%s', " \
                            "trying again. Attempt: %d" %
                            (app_config.get('name'), attempt))
                    time.sleep(30)
                    common.de_name = app_config.get('name')
                    result = app.stop()
                    common.de_name = None
                    attempt += 1

                if result == 0:
                    common.log("Stopped deployable entity \"%s\"" % \
                               app_config.get('name'))
                else:
                    # Failed to start one app - stop trying to start more
                    common.log('Error stopping deployable entity '
                                 '\'%s\' (%d)' % \
                                 (app_config.get('name'), result))

    def _get_old_config(self):
        if self.old_config is None:
            return None
        return self.old_config

    def _get_current_value(self, property_name):
        # get value of property specified from old_config
        if self.old_config is None:
            return None
        return self.old_config.get(property_name)

    def _cleanup_failed_start(self):
        common.log("Cleaning up after earlier failed start...", echo=True)

        self._verify_pid()
        if self.pid is not None:
            self.force_stop()
        if os.path.exists(self._pidfile):
            os.remove(self._pidfile)

        home_dir = self.config.get('home_dir')
        if os.path.exists(home_dir) and os.path.isdir(home_dir):
            common.log("Removing home-dir (%s)" % home_dir, echo=True)
            try:
                shutil.rmtree(home_dir)
            except OSError as ex:
                common.log("Couldn't remove home_dir: %s. %s" \
                                    % (home_dir, ex), level="ERROR")
                return 1

        self.old_config = None
        self.config.remove_lock()
        return 0

    def _remove_old_apps(self):
        '''Removes DEs that are in old config but not in new.'''
        if self.old_config is None:
            return 0

        # Undeploy any apps that have been removed from the config.
        # We do this by considering the old apps in *reverse* order,
        # since that's the order in which we always undeploy apps.
        for old_app_config in self.old_config.apps[::-1]:
            name = old_app_config.get('name')
            for new_app_config in self.new_config.apps:
                if new_app_config.get('name') == name:
                    break
            else:
                # name is not found in new_config.apps
                common.log("Deployable entity \"%s\" has been removed from " \
                           "configuration, so undeploying it." % name)
                app = litp_jboss_app.LitpJbossApp(old_app_config)
                common.de_name = name
                result = app.undeploy()
                common.de_name = None
                if result != 0:
                    common.log("Error undeploying entity \"%s\"." % name)
                    return 1
        return 0

    def _create_piddir(self):
        pid_dir = os.path.dirname(self._pidfile)
        if not os.path.exists(pid_dir):
            try:
                common.log('creating pid_dir "%s"' % pid_dir)
                os.makedirs(pid_dir)
            except OSError as ex:
                common.log("[Errno %s] %s" % (ex.errno, ex.strerror), \
                           level="DEBUG")
                msg = "Could not create PID dir \"%s\": %s" \
                                                      % (pid_dir, ex.strerror)
                common.echo_failure(msg)
                return 1
        if not os.path.isdir(pid_dir):
            msg = "PID dir \"%s\" exists, but is not a directory" % pid_dir
            common.echo_failure(msg)
            return 1

        status = os.stat(pid_dir)
        # Directory should be owned by root, and world-writable
        if status.st_uid != 0 or status.st_gid != 0:
            common.log('pid_dir "%s" has wrong uid/gid: %d/%d: chowning' % \
                       (pid_dir, status.st_uid, status.st_gid))
            os.chown(pid_dir, 0, 0)
        if stat.S_IMODE(status.st_mode) != 0777:
            common.log('pid_dir "%s" has wrong mode: 0%o: chmoding' % \
                       (pid_dir, stat.S_IMODE(status.st_mode)))
            os.chmod(pid_dir, 0777)
        return 0

    def start(self):
        prev_config = self.setup_new_config()
        try:
            return self._start()
        finally:
            self.set_config(prev_config)

    def _start(self):
        """
        @summary: It starts the JBoss instance described by the environment
        variables, using the configuration options set by those variables.
        If the JBoss instance is not present, it will try to deploy it first.

        Also, it will check that the version that is trying to be started
        is the same as the installed one. If it is not, that version will
        be installed before starting it.

        Since a JBoss instance takes a while until it starts,
        the script waits for a configurable amount of time for JBoss
        to be started successfully and if it did not, it will return an error.
        """

        if self.config.lock_exists():
            result = self._cleanup_failed_start()
            if result != 0:
                msg = 'Failed to clean up after previous failed start.'
                common.echo_failure(msg)
                return 1

        # check that instance is not already running
        self._verify_pid()
        if self.pid is not None:
            msg = "JBoss \"%s\" (%d) is already running." \
                                  % (self.config.get('home_dir'), self.pid)
            common.echo_failure(msg)
            return 0

        self.config.create_lock()

        current_version = self._get_current_value('version')
        current_install_source = self._get_current_value('install_source')
        current_home_dir = self._get_current_value('home_dir')
        current_data_dir = self._get_current_value('data_dir')

        if current_version is None:
            # This is our first time starting - home_dir should not exist yet

            if os.path.isdir(self.config.get('home_dir')):
                msg = 'JBoss home_dir (%s) already exists!' % \
                        self.config.get('home_dir')
                common.echo_failure(msg)
                return 1

            common.log("JBoss \"%s\" is not installed, deploying first." % \
                                                 (self.config.get('home_dir')))

            # continue if deploy does not fail
            result = self.deploy()
            if result != 0:
                return 1
        # upgrade JBoss if version or install source has changed
        elif (self.config.get('version') != current_version) or \
             (self.config.get('install_source') != current_install_source):
            result = self.upgrade()
            if result != 0:
                return result

        # redeploy JBoss if home dir, data dir or SPs have changed
        elif (current_home_dir != self.config.get('home_dir') and \
                    current_home_dir != None) or \
             (current_data_dir != self.config.get('data_dir') and \
                    current_install_source != None) or \
             self.config.is_sp_different(self._get_old_config()):
            if self._redeploy() != 0:
                return 1

        # chown JBoss home dir
        if self._update_perms(self.config.get('home_dir')) != 0:
            common.echo_failure("Failed to update permissions on \"%s\"" \
                                % self.config.get('home_dir'))
            return 1

        common.log("Starting \"%s\"." % (self.config.get('home_dir')))

        # create pidfile dir
        # and verify running user permissions
        rc = self._create_piddir()
        if rc != 0:
            return rc

        # remove old log directory if it has changed
        log_dir = self.config.get('log_dir')
        current_log_dir = self._get_current_value('log_dir')
        if current_log_dir != log_dir and current_log_dir != None:
            common.remove_directory(current_log_dir)

        # create jboss log dir
        if log_dir is not None:
            if not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir)
                except OSError as ex:
                    common.echo_failure("Failed to make log dir \"%s\". %s" \
                                        % (log_dir, ex))
                    return 1

            # chown jboss log dir
            if self._update_perms(log_dir) != 0:
                common.echo_failure("Failed to update permissions on \"%s\"" \
                                                % log_dir)
                return 1

        data_dir = self.config.get('data_dir')
        # create jboss data dir
        if data_dir is not None:
            if not os.path.exists(data_dir):
                try:
                    os.makedirs(data_dir)
                except OSError as ex:
                    common.echo_failure("Failed to make data dir \"%s\". %s" \
                                % (self.config.get('data_dir'), ex.strerror))
                    return 1

            if self._update_perms(data_dir) != 0:
                common.echo_failure("Failed to update permissions on \"%s\"" \
                                    % data_dir)
                return 1

        # re-initialize jboss console log
        open(self._jboss_console_log, 'w').close()

        self._update_perms(self._jboss_console_log)

        # chown pid file
        if os.path.exists(self._pidfile):
            if self._update_perms(self._pidfile) != 0:
                msg = "Failed to update permissions of \"%s\"" \
                                                             % (self._pidfile)
                common.echo_failure(msg)
                return 1

        # add / update management user
        current_mgmt_user = self._get_current_value('management_user')
        current_mgmt_password = self._get_current_value('management_password')
        # if user changed add new user remove old user
        if current_mgmt_user != self.config.get('management_user') \
                and current_mgmt_user is not None:
            rc = self._add_management_user()
            if rc != 0:
                return 1
            self._remove_management_user(current_mgmt_user)

        # if password changed update it (add user - updates password)
        if current_mgmt_password != self.config.get('management_password') \
                and current_mgmt_password != None:
            rc = self._add_management_user()
            if rc != 0:
                return 1

        if self._run_fragments('pre_start') != 0:
            return 1

        daemon_started = self._run_daemon()
        if daemon_started != 0:
            common.echo_failure("JBoss daemon process failed to start")
            return 1

        # check jboss status
        common.log("JBoss container checking status...", echo=True)
        retries = 10  # Number of times to retry status check
        try_number = 1
        status_check = 1
        while (status_check != 0):
            if try_number > retries:
                common.echo_failure("JBoss failed its status check")
                return 1
            common.log("Checking status try_number: %s" % try_number)
            time.sleep(1)
            status_check = self.status(silent=True)
            try_number += 1

        common.log("JBoss container started. Starting apps...", echo=True)

        if self._remove_old_apps() != 0:
            return 1

        # Container started - now start the apps, if requested.
        result = self._start_all_apps()

        if result == 0:
            msg = 'JBoss started, see the logs: %s' % \
                                        (self._jboss_console_log)
            common.echo_success(msg)

            if self._run_fragments('post_start') != 0:
                return 1

            self.config.save_config()
            self.config.remove_lock()
            return 0
        else:
            msg = 'Deployable entity startup failed, ' \
                         'stopping container. See the logs: %s' % \
                         (self._jboss_console_log)
            common.echo_failure(msg)
            self._stop()
            return 1

    def stop(self, silent=False):
        prev_config = self.setup_old_config()
        try:
            return self._stop(silent)
        finally:
            self.set_config(prev_config)

    def _stop(self, silent=False):
        """
        @summary: Will stop a started JBoss instance.
        If the JBoss instance is not started, and error will be printer, but
        successful exit will be performed.
        Before stopping JBoss container instance, it will try stopping the DEs
        running in that JBoss container.
        """
        msg = "Stopping JBoss \"%s\"..." % (self.config.get('home_dir'))
        common.log(msg, echo=True)

        self._verify_pid()

        if self.pid is not None:
            if self._run_fragments('pre_shutdown') != 0:
                return 1

            self._stop_all_apps_batch()

            # try issuing SIGTERM (15)
            res = self._kill_pid(self.pid, signal.SIGTERM)
            if res:
                return 1

            # wait for a process to terminate
            for _ in xrange(self._shutdown_wait):
                time.sleep(1)
                cmd = 'ps --pid %s 2> /dev/null|grep -c %s 2> /dev/null' \
                                                        % (self.pid, self.pid)

                exit_status, stdout, stderr = self._exec_cmd(cmd)

                # command failed
                if len(stderr) > 0:
                    common.log('Command "%s" failed. [Errno %s] %s' \
                                % (cmd, exit_status, stderr), level="ERROR")
                    break

                # process terminated
                if exit_status == 1 and \
                                    len(stdout) == 1 and int(stdout[0]) == 0:
                    msg = "JBoss instance \"%s\" stopped" % \
                                        (self.config.get('home_dir'))
                    common.echo_success(msg)
                    if self._run_fragments('post_shutdown') != 0:
                        return 1
                    return 0
                else:
                    self._check_and_kill_zombie()

            # process not terminated
            if exit_status != 1:
                return self.force_stop()

            if self._run_fragments('post_shutdown') != 0:
                return 1
            return 0
        else:
            if not silent:
                msg = "JBoss instance \"%s\" was not started" \
                                                % (self.config.get('home_dir'))
                common.echo_failure(msg)
            return 0

    def restart(self):
        """
        @summary: Restarts the JBoss instance by first stopping and then
        starting it.
        If an error occurs during the stop process a message will be displayed,
        but start will be attempted.
        """
        stopped = self.stop()
        started = self.start()

        if (stopped == 0 and started == 0):
            common.log("JBoss server is restarted.")
            return 0
        else:
            common.log("JBoss server failed to restart.", level="ERROR")
            return 1

    def reload(self):
        """
        @summary: Restarts the JBoss instance, same behaviour as restart.
        """
        return self.restart()

    def force_stop(self):
        prev_config = self.setup_old_config()
        try:
            return self._force_stop()
        finally:
            self.set_config(prev_config)

    def _force_stop(self):
        """
        Will kill a started JBoss instance.
        If the JBoss instance is not started, and error will be returned.
        """
        self._verify_pid()

        if self.pid is not None:
            # if alive, send SIGKILL (9) (FORCE-STOP)
            res = self._kill_pid(self.pid, signal.SIGKILL)
            if res:
                return 1
        # LITP-3913 Wait for the process to die before returning
        while self.pid:
            time.sleep(1)
            self._check_and_kill_zombie()
            self._verify_pid()

        common.echo_success("JBoss force-stopped")
        return 0

    def _check_and_kill_zombie(self):
        self._verify_pid()
        if self._pid_is_zombie(self.pid):
            common.log("Zombie detected: pid %d" % self.pid, level="DEBUG")
            #Get parent and kill it
            ppid = self._get_ppid(self.pid)
            common.log("Parent of zombie, pid: %d" % ppid, level="DEBUG")
            # Better check ppid != 1 (init process)
            # If init is parent, it will take care of itself
            if ppid != 1:
                common.log("Sending SIGKILL to parent, pid: %d" % ppid,
                        level="DEBUG")
                self._kill_pid(ppid, signal.SIGKILL)

    def _pid_is_zombie(self, pid):
        if not pid:
            return False
        pid_cmdline = "/proc/%d/cmdline" % (pid)
        if not os.path.exists(pid_cmdline):
            # PID does not exist/is dead
            return False
        contents = open(pid_cmdline, "r").readlines()
        # contents should contain at least argv[0], if not it's a zombie
        return len(contents) == 0

    def _kill_pid(self, proc, sig):
        try:
            return os.kill(proc, sig)
        except OSError as ex:
            common.log('[Errno %s] %s' % (ex.errno, ex.strerror),
                       level="ERROR")
            common.echo_failure("Could not kill process (pid %s)" % (proc))
            return 1

    def _get_ppid(self, pid):
        # Run over status file in /proc to find PPid of pid
        status_path = "/proc/%d/status" % (pid)
        if not os.path.exists(status_path):
            return 1
        try:
            f = open(status_path, "r")
            for line in f:
                if line.startswith("PPid:"):
                    # PPid: nnnn
                    parent_id = int(line.split()[1])
                    common.log("Found parent id of %d: %d" % (pid, parent_id),
                            level="DEBUG")
                    return parent_id
            # If it doesn't exist, we assume init is the parent
            common.log("No PPID for PID %d found!" % (pid), level="ERROR")
            return 1
        except:
            return 1
        finally:
            f.close()

    def force_restart(self):
        return self.force_stop() and self.start()

    def _check_jboss_process(self, silent):
        '''
        Check Jboss process is running
        '''
        echo_opt = not(silent)
        cmd = 'ps --pid %s 2> /dev/null | grep -c %s 2> /dev/null' \
                                                        % (self.pid, self.pid)

        exit_status, stdout, stderr = self._exec_cmd(cmd)

        if exit_status != 0 or len(stderr) != 0:
            common.log('rc: %s, stdout: %s, stderr: %s' \
                          % (exit_status, stdout, stderr), level="DEBUG")
            if not silent:
                common.echo_failure("No process (%s), but PID file "\
                                                    "(%s) exists." \
                                             % (self.pid, self._pidfile))
            return 1

        exceptions_found = int(stdout[0])
        if exit_status == 0 and exceptions_found == 1:
            common.log("JBoss \"%s\" is running (pid %s)" \
                            % (self.config.get('home_dir'), self.pid),
                       echo=echo_opt)
        else:
            common.log("JBoss \"%s\" is not running" \
                    % (self.config.get('home_dir')), echo=echo_opt)

        return 0

    def _have_management_account(self):
        return (self.config.get('management_user') is not None) and \
               (self.config.get('management_password') is not None)

    def _make_jboss_http_cmd(self, attrs, max_time=None):
        myattrs = dict(attrs)
        myattrs['json.pretty'] = 1

        if max_time is not None:
            cmd = 'curl --max-time %d' % int(max_time)
        else:
            cmd = 'curl'

        url = self.config.get_jboss_management_url()

        # -g is needed to "glob" the [ ] if we have an ipv6.
        cmd += ' -g -s -S --digest -L \'%s\'' % url
        cmd += ' --header "Content-Type: application/json"'
        cmd += ' -u %s:%s' % (self.config.get('management_user'),
                             self.config.get('management_password'))
        cmd += ' -d \'%s\'' % json.dumps(myattrs)
        return cmd

    def _run_jboss_http_cmd(self, attrs, max_time=None):
        cmd = self._make_jboss_http_cmd(attrs, max_time)
        # STORY-6410 Do not remove the silent aspect without talking to Eoin
        rc, stdout, stderr = self._exec_cmd(cmd, silent=True)
        stderr_str = '\n'.join([ln.strip() for ln in stderr])

        if rc != 0:
            common.log('rc: %s, stdout: %s, stderr: %s' % (rc, stdout, stderr),
                    level="DEBUG")
            return rc, stderr_str

        if stderr:
            common.log('rc: %s, stdout: %s, stderr: %s' % (rc, stdout, stderr),
                    level="DEBUG")
            return 1, stderr_str

        try:
            output = json.loads('\n'.join(stdout))
            return 0, output
        except ValueError, e:
            common.log('Unable to decode "%s" as JSON: %s' \
                                % ('\n'.join(stdout), e), level="DEBUG")
            return 1, None

    def _check_jboss_is_running(self, silent):
        if self._have_management_account():
            return self._check_jboss_via_http()
        else:
            return self._check_jboss_via_cli(silent)

    def _time(self):
        return time.time()

    def _check_jboss_via_http(self):
        common.log('Starting status check')

        request_time = 2    # seconds per curl request - must be integer
        total_time = 9      # seconds to allow overall - less than AMF allows
        delay_time = 0.5    # sleep between curl requests

        start_time = self._time()
        end_time = start_time + total_time

        while True:
            rc, exit_status = self._check_jboss_via_http_worker(request_time)
            if rc == 0 and exit_status == 0:
                break

            if (end_time - self._time()) > delay_time:
                time.sleep(delay_time)

            remaining = end_time - self._time()
            if remaining < 0:
                break

            request_time = int(min(request_time, remaining))
            if request_time <= 0:
                break
        common.log('Status check returning %d, %s' % (rc, exit_status))
        return rc, exit_status

    def _check_jboss_via_http_worker(self, max_time):
        rc, output = self._run_jboss_http_cmd(
            {
                'operation': 'read-attribute',
                'name': 'server-state',
            },
            max_time=max_time
        )

        if rc != 0:
            return rc, output   # got no HTTP response

        if 'outcome' in output and output['outcome'] == 'success':
            if 'result' in output and output['result'] == 'running':
                return 0, 0     # got good response

        return 0, 1             # got bad response

    def _query_deployable_entity_states(self, query_time=None):
        rc, output = 1, ""
        count = 0
        max_retries = 10
        delay_time = 0.5
        while count < max_retries:
            rc, output = self._run_jboss_http_cmd(
                {
                    'operation': 'read-children-resources',
                    'child-type': 'deployment',
                    'include-runtime': 'true',
                },
                max_time=query_time
            )
            common.log("Querying DE states. Attempt: %d" % count, "DEBUG")
            if rc == 0 and 'outcome' in output \
                    and output['outcome'] == 'success':
                break
            common.log("Query failed rc: %s, output: %s" % (rc, output),
                    "DEBUG")
            count = count + 1
            self._sleep(delay_time)
        if rc == 0:
            common.log("Got successful response, response: %s" % output,
                    "DEBUG")
        return rc, output

    def _get_deployable_entity_states(self, query_time=None):
        # Returns a dictionary indexed by deployed entity, with a boolean
        # value where True means the app is running.
        results = {}
        rc, output = self._query_deployable_entity_states(query_time)
        if rc != 0:
            return results
        for deployed_de in output['result']:
            results[deployed_de] = 'OK' in \
                    output['result'][deployed_de]['status']
        return results

    def _check_jboss_via_cli(self, silent):
        '''Check JBoss running using CLI management protocol
        '''
        echo_opt = not(silent)
        exit_status = None
        common.log('Checking JBoss management cli, please, wait...',
                       echo=echo_opt)
        jboss_cmd = "read-attribute server-state"
        search_status = 'running'
        exit_status, stdout, stderr = self.jbosscli.run(jboss_cmd)
        if (exit_status != 0):
            common.log('rc: %s, stdout: %s, stderr: %s' \
                        % (exit_status, stdout, stderr), level="DEBUG")

            msg = "Running  JBoss cli command \"%s\" failed. "\
                                         "See console logs." % (jboss_cmd)
            if not silent:
                common.echo_failure(msg)
            return 1, exit_status

        if len(stdout) != 0:
            if stdout[-1].strip() == search_status:
                common.log('Success: Found "%s" in "%s"' % \
                           (search_status, stdout[-1]))
                exit_status = 0
            else:
                common.log('Fail: Didn\'t find "%s" in "%s"' % \
                           (search_status, stdout[-1]))
                exit_status = 1
        else:
            exit_status = 1

        return 0, exit_status

    def status(self, silent=False):
        """
        @summary: Will print the status of a given JBoss instance.
        It checks if the JBoss process is running and it connects JBoss cli
        and checks if JBoss server is reported to be running.
        """
        echo_opt = not(silent)
        self._verify_pid()
        if self.pid:
            # check jboss - if status is called with silent=False (not used by
            # self._start) then we return success regardless of whether
            # _check_jboss_is_running succeeds, so long as we have the pid. We
            # just run it and output the error for visibility. (See LITP-4118)
            rc, exit_status = self._check_jboss_is_running(silent)
            msg = "JBoss \"%s\" is running" % (self.config.get('home_dir'))
            if rc != 0:
                # If we fail to query JBoss, tell the user why
                if silent:
                    return 1
                else:
                    rc_msg = "JBoss \"%s\" status query failed with error: %s"\
                        % (self.config.get('home_dir'), exit_status)
                    print >> sys.stderr, rc_msg

            if silent and exit_status != 0:
                return 1

            if not silent:
                common.echo_success(msg)
            return 0  # exit_status

        common.log("JBoss \"%s\" is not running" % \
                        (self.config.get('home_dir')), echo=echo_opt)
        return 1  # exit_status

    def _maketempdir(self):
        import tempfile
        temppath = tempfile.mkdtemp('litpjboss')
        try:
            if not os.path.exists(temppath):
                os.makedirs(temppath)
            return 0, temppath
        except OSError as ex:
            common.log("[Errno %s] %s" % (ex.errno, ex.strerror),
                       level="DEBUG")
            msg = "Could not create \"%s\", please run as root." % (temppath)
            common.echo_failure(msg)
            return 1, None

    def _makehomedir(self):
        if not os.path.exists(self.config.get('home_dir')):
            try:
                os.makedirs(self.config.get('home_dir'))
                return 0
            except OSError as ex:
                common.log('[Errno %s] %s' % (ex.errno, ex.strerror),
                           level="DEBUG")
                msg = "Could not create JBoss home \"%s\", " \
                                    "please run as root." \
                                    % (self.config.get('home_dir'))
                common.echo_failure(msg)
                return 1
        else:
            common.log("JBoss home dir already exists. Skipping.")
            return 0

    def _untar_and_move(self, temppath):
        cmd = 'tar -xzf %s -C %s && mv %s/* %s' % \
                            (self.config.get('install_source'),
                             temppath, temppath, self.config.get('home_dir'))
        rc, stdout, stderr = self._exec_cmd(cmd)

        if rc != 0 or len(stderr) != 0:
            common.log('rc: %s, stdout: %s, stderr: %s' \
                                    % (rc, stdout, stderr), level="DEBUG")
            msg = "Failed to deploy JBoss to \"%s\".  See console logs %s." \
                    % (self.config.get('home_dir'), self._jboss_console_log)
            common.echo_failure(msg)
            return 1
        return 0

    def _untar_support_packages(self):
        self.module_dir = os.path.join(self.config.get('home_dir'), 'modules')

        common.log("Untarring %d support_packages" % \
                    len(self.config.support_packages))

        for idx in range(len(self.config.support_packages)):
            support_package = self.config.support_packages[idx]
            cmd = 'tar -xzf %s -C %s' % \
                            (support_package.get('install_source'),
                             self.module_dir)
            rc, stdout, stderr = self._exec_cmd(cmd)

            if rc != 0 or len(stderr) != 0:
                common.log('rc: %s, stdout: %s, stderr: %s' \
                                    % (rc, stdout, stderr), level="ERROR")
                msg = "Failed to extract Support Package \"%s\" to \"%s\"" \
                    % (support_package.get('install_source'), self.module_dir)
                common.echo_failure(msg)
                return 1
        return 0

    def _clean_temp(self, temppath):
        try:
            shutil.rmtree(temppath)
        except OSError as ex:
            common.log("Didn't cleaned temp: %s. %s" \
                                    % (temppath, ex), level="DEBUG")

    def _add_management_user(self):
        if self.config.get('management_user') and \
            self.config.get('management_password'):
            common.log("Adding JBOSS management user \'%s\'" % \
                       (self.config.get('management_user')))
            cmd = self._adduser + " --silent=true " \
                      + self.config.get('management_user') + " " \
                      + self.config.get('management_password')
            rc, stdout, stderr = self._exec_cmd(cmd)

            if rc != 0 or len(stderr) != 0:
                common.log('rc: %s, stdout: %s, stderr: %s' \
                                    % (rc, stdout, stderr), level="DEBUG")
                msg = "Failed to add management user " \
                             "\"%s\" to \"%s\" using \"%s\"." \
                             % (self.config.get('management_user'),
                                self.config.get('home_dir'),
                                self._adduser)
                common.echo_failure(msg)
                return 1
        return 0

    def _remove_management_user(self, mgmt_user):
        for user_file in self._mgmt_user_files:
            self._remove_user_from_file(mgmt_user, user_file)

    def _remove_user_from_file(self, user, user_file):
        # remove specified mgmt user from mgmt users file
        f = open(user_file, "r")
        lines = f.readlines()
        f.close()

        common.log("Removing JBOSS management user \'%s\' from file \'%s\'" % \
                    (user, user_file))
        f = open(user_file, "w")
        for line in lines:
            if not line.startswith(user + "="):
                f.write(line)
        f.close()

    def deploy(self):
        prev_config = self.setup_new_config()
        try:
            return self._deploy()
        finally:
            self.set_config(prev_config)

    def _deploy(self):
        """
        @summary: Will deploy the JBoss instance described by the environment
        variables, without starting it.
        """
        # fail if there is no install source
        if not (os.path.exists(self.config.get('install_source')) and \
                os.path.isfile(self.config.get('install_source'))):
            msg = "No valid JBoss install source found at \"%s\"" \
                                      % (self.config.get('install_source'))
            common.echo_failure(msg)
            return 1

        # Check if the jboss is already installed
        if os.path.exists(self.config.get('home_dir')) and \
            os.path.isdir(self.config.get('home_dir')):
            msg = "JBoss \"%s\" was already installed" % \
                        (self.config.get('home_dir'))
            common.echo_success(msg)
            return 0

        common.log("Starting JBoss deployment from \"%s\" to '%s." % \
                            (self.config.get('install_source'),
                             self.config.get('home_dir')), echo=True)

        # run pre-deploy scripts
        if self._run_fragments('pre_deploy') != 0:
            return 1

        # extract install source into /tmp/jboss/
        rc, temppath = self._maketempdir()
        if rc != 0:
            return rc

        # make home dir
        rc = self._makehomedir()
        if rc != 0:
            return rc

        # untar and move to target directory
        rc = self._untar_and_move(temppath)
        if rc != 0:
            return rc

        # cleanup tmppath
        self._clean_temp(temppath)

        # add management user
        rc = self._add_management_user()
        if rc != 0:
            return 1

        # add support packages
        rc = self._untar_support_packages()
        if rc != 0:
            return 1

        # chown everything inside to process
        self._update_perms(self.config.get('home_dir'))

        msg = "Successfully installed JBoss to \"%s\"" % \
                                        (self.config.get('home_dir'))
        common.echo_success(msg)
        self.config.save_config()

        if self._run_fragments('post_deploy') != 0:
            return 1

        return 0

    def undeploy(self, remove_state_dir=True):
        prev_config = self.setup_old_config()
        try:
            return self._undeploy(remove_state_dir)
        finally:
            self.set_config(prev_config)

    def _undeploy(self, remove_state_dir):
        """
        Will remove the JBOSS instance described by the environment variables.
        It will first try to stop the instance and then proceed with removing
        it. It will check if the JBOSS executable script is present and only
        then it will delete the instance. If the script would not find the
        JBOSS executable, it will display a message that says that this does
        not appear to be a valid JBOSS installation and will fail.

        If there is no home dir it will assume this instance is already
        undeploy.

        This check is in place just to make sure that some other files on the
        filesystem will not get deleted by mistake.
        """
        self.setup_old_config()
        if not (os.path.exists(self.config.get('home_dir')) \
                and os.path.isdir(self.config.get('home_dir'))):
            common.echo_failure('Nothing to undeploy. ' \
                                'No JBoss found in home directory at "%s"' \
                                % (self.config.get('home_dir')))
            self.config.remove_config()
            return 0

        # check for jboss script
        if not (os.path.exists(self._jboss_script) \
                and os.path.isfile(self._jboss_script)):
            msg = "JBoss \"%s\" is not installed or " \
                  "installation is not valid" % (self.config.get('home_dir'))
            common.echo_failure(msg)

            common.log("Script file \"%s\" is not present " \
                    " or is not a file." % (self._jboss_script), level="DEBUG")
            return 1

        # stop container
        self.stop(silent=True)

        if self._run_fragments('pre_undeploy') != 0:
            return 1

        msg = "Deleting JBoss from \"%s\"..." % (self.config.get('home_dir'))
        common.log(msg, echo=True)

        # rm -rf jboss home dir
        if common.remove_directory(self.config.get('home_dir')) == 1:
            return 1

        # do not remove 'data_dir' - it makes jboss cluster unstable
        # rm -rf jboss data dir
        #if self.config.get('data_dir') is not None:
        #    if common.remove_directory(self.config.get('data_dir')) == 1:
        #        return 1

        msg = "Deleted JBoss \"%s\"" % (self.config.get('home_dir'))
        common.echo_success(msg)

        if remove_state_dir:
            self.config.remove_state_dir()
        else:
            self.config.remove_config()

        if self._run_fragments('post_undeploy') != 0:
            return 1

        return 0

    def _redeploy(self):
        """
        @summary: It does a redeploy of JBoss which consist of
        an undeploy and a deploy
        """
        undeployed = self.undeploy(remove_state_dir=False)
        if undeployed != 0:
            return undeployed

        deployed_new = self.deploy()
        if deployed_new != 0:
            return deployed_new
        return 0

    def upgrade(self):
        prev_config = self.setup_new_config()
        try:
            return self._upgrade()
        finally:
            self.set_config(prev_config)

    def _upgrade(self):
        """
        @summary: It compares the installed version of jboss
        with the one set by the environment variables.
        If these versions are different, it will call pre_upgrade scripts,
        undeploy function, deploy function and then the post_upgrade scripts.

        If the installed version is the same as the one it tries to upgrade to,
        the script will fail.

        If the script cannot find the current version information,
        it will fail.
        """
        current_version = self._get_current_value('version')

        if current_version == '':
            msg = "No current JBoss version, cannot upgrade."
            common.echo_failure(msg)
            return 1

        current_install_source = self._get_current_value('install_source')

        if (self.config.get('version') != current_version) or \
            (self.config.get('install_source') != current_install_source):

            msg = 'Upgrading JBoss from version "%s" (%s) ' \
                  'to version "%s" (%s)' \
            % (current_version, current_install_source,
                self.config.get('version'), self.config.get('install_source'))

            common.log(msg, echo=True)

            prev_config = self.setup_old_config()
            try:
                if self._run_fragments('pre_upgrade') != 0:
                    return 1
            finally:
                self.set_config(prev_config)

            # redeploy JBoss
            if self._redeploy() != 0:
                return 1

            if self._run_fragments('post_upgrade') != 0:
                return 1

            msg = "JBoss upgrade completed successfully."
            common.echo_success(msg)
            return 0
        else:
            msg = "JBoss version \"%s\" is already installed." % \
                                              (self.config.get('version'))
            common.echo_failure(msg)
            return 1

    def _exit(self, rc):
        """
        log exit status and then exit
        """
        log_level = 'INFO'
        if rc != 0:
            log_level = 'ERROR'
        common.log("Exiting with (%s)" % (rc), level=log_level)
        sys.exit(rc)

    def main(self):
        """
        Parses arguments and call appropriate methods
        """
        try:
            common.log('main() - sys.argv: %s' % str(sys.argv), level="DEBUG")
            if len(sys.argv) == 1:
                raise ValueError

            action = str(sys.argv[1]).strip().lower()
            if action == 'start':
                self._exit(self.start())
            elif action == 'stop':
                self._exit(self.stop())
            elif action == 'force-stop':
                self._exit(self.force_stop())
            elif action == 'restart':
                self._exit(self.restart())
            elif action == 'force-restart':
                self._exit(self.force_restart())
            elif action == 'reload':
                self._exit(self.reload())
            elif action == 'status':
                self._exit(self.status())
            elif action == 'deploy':
                self._exit(self.deploy())
            elif action == 'undeploy':
                self._exit(self.undeploy())
            elif action == 'upgrade':
                self._exit(self.upgrade())
            else:
                raise ValueError

        except (ValueError):
            print >> sys.stderr, "Usage: litp-jboss [" + \
                                                        "start|" + \
                                                        "stop|" + \
                                                        "force-stop|" + \
                                                        "restart|" + \
                                                        "force-restart|" + \
                                                        "reload|" + \
                                                        "status|" + \
                                                        "deploy|" + \
                                                        "undeploy|" + \
                                                        "upgrade" + \
                                                    "]"
            self._exit(2)

if __name__ == "__main__":
    arglist = sys.argv[1:]
    if len(arglist):
        cmd = arglist[0]
        os.environ['WRAPPER_COMMAND'] = cmd.strip().strip('"')
    cEnvI = CompEnvInstantiator()
    cEnvI.appendEnvironment(cEnvI.parseEnvFileName())
    config = litp_jboss_config.LitpJbossConfig(os.environ)
    LitpJboss(config).main()
