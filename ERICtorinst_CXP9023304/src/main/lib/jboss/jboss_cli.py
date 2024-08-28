import logging
import pycurl
import cStringIO
from time import time, sleep
import urllib
from simplejson import dumps, loads

_logger = logging.getLogger('jboss_cli')
_logger.addHandler(logging.StreamHandler())
_logger.setLevel(logging.INFO)


class PathNotFoundError(Exception):
    def __init__(self, path=None):
        self.path = path

    def __str__(self):
        return repr(self.path)


class JBossQueryError(Exception):
    def __init__(self, error_code, error_message):
        self.error_code = error_code
        self.error_message = error_message

    def __str__(self):
        return repr('%s:%s' % (self.error_code, self.error_message))


class jboss_cli:
    CURL_EXIT_CODES = {'1': 'Unsupported protocol. This build of curl has no support for this protocol.',
                       '2': 'Failed to initialize.',
                       '3': 'URL malformed. The syntax was not correct.',
                       '4': 'A feature or option that was needed to perform the desired request was not enabled or was explicitly disabled at build-time. To make curl able to do this, you probably need another build of libcurl!',
                       '5': 'Couldn\'t resolve proxy. The given proxy host could not be resolved.',
                       '6': 'Couldn\'t resolve host. The given remote host was not resolved.',
                       '7': 'Failed to connect to host.',
                       '8': 'FTP weird server reply. The server sent data curl couldn\'t parse.',
                       '9': 'FTP access denied. The server denied login or denied access to the particular resource or directory you wanted to reach. Most often you tried to change to a directory that doesn\'t exist on the server.',
                       '11': 'FTP weird PASS reply. Curl couldn\'t parse the reply sent to the PASS request.',
                       '13': 'FTP weird PASV reply, Curl couldn\'t parse the reply sent to the PASV request.',
                       '14': 'FTP weird 227 format. Curl couldn\'t parse the 227-line the server sent.',
                       '15': 'FTP can\'t get host. Couldn\'t resolve the host IP we got in the 227-line.',
                       '17': 'FTP couldn\'t set binary. Couldn\'t change transfer method to binary.',
                       '18': 'Partial file. Only a part of the file was transferred.',
                       '19': 'FTP couldn\'t download/access the given file, the RETR (or similar) command failed.',
                       '21': 'FTP quote error. A quote command returned error from the server.',
                       '22': 'HTTP page not retrieved. The requested url was not found or returned another error with the HTTP error code being 400 or above. This return code only appears if -f, --fail is used.',
                       '23': 'Write error. Curl couldn\'t write data to a local filesystem or similar.',
                       '25': 'FTP couldn\'t STOR file. The server denied the STOR operation, used for FTP uploading.',
                       '26': 'Read error. Various reading problems.',
                       '27': 'Out of memory. A memory allocation request failed.',
                       '28': 'Operation timeout. The specified time-out period was reached according to the conditions.',
                       '30': 'FTP PORT failed. The PORT command failed. Not all FTP servers support the PORT command, try doing a transfer using PASV instead!',
                       '31': 'FTP couldn\'t use REST. The REST command failed. This command is used for resumed FTP transfers.',
                       '33': 'HTTP range error. The range "command" didn\'t work.',
                       '34': 'HTTP post error. Internal post-request generation error.',
                       '35': 'SSL connect error. The SSL handshaking failed.',
                       '36': 'FTP bad download resume. Couldn\'t continue an earlier aborted download.',
                       '37': 'FILE couldn\'t read file. Failed to open the file. Permissions?',
                       '38': 'LDAP cannot bind. LDAP bind operation failed.',
                       '39': 'LDAP search failed.',
                       '41': 'Function not found. A required LDAP function was not found.',
                       '42': 'Aborted by callback. An application told curl to abort the operation.',
                       '43': 'Internal error. A function was called with a bad parameter.',
                       '45': 'Interface error. A specified outgoing interface could not be used.',
                       '47': 'Too many redirects. When following redirects, curl hit the maximum amount.',
                       '48': 'Unknown option specified to libcurl. This indicates that you passed a weird option to curl that was passed on to libcurl and rejected. Read up in the manual!',
                       '49': 'Malformed telnet option.',
                       '51': 'The peer\'s SSL certificate or SSH MD5 fingerprint was not OK.',
                       '52': 'The server didn\'t reply anything, which here is considered an error.',
                       '53': 'SSL crypto engine not found.',
                       '54': 'Cannot set SSL crypto engine as default.',
                       '55': 'Failed sending network data.',
                       '56': 'Failure in receiving network data.',
                       '58': 'Problem with the local certificate.',
                       '59': 'Couldn\'t use specified SSL cipher.',
                       '60': 'Peer certificate cannot be authenticated with known CA certificates.',
                       '61': 'Unrecognized transfer encoding.',
                       '62': 'Invalid LDAP URL.',
                       '63': 'Maximum file size exceeded.',
                       '64': 'Requested FTP SSL level failed.',
                       '65': 'Sending the data requires a rewind that failed.',
                       '66': 'Failed to initialise SSL Engine.',
                       '67': 'The user name, password, or similar was not accepted and curl failed to log in.',
                       '68': 'File not found on TFTP server.',
                       '69': 'Permission problem on TFTP server.',
                       '70': 'Out of disk space on TFTP server.',
                       '71': 'Illegal TFTP operation.',
                       '72': 'Unknown TFTP transfer ID.',
                       '73': 'File already exists (TFTP).',
                       '74': 'No such user (TFTP).',
                       '75': 'Character conversion failed.',
                       '76': 'Character conversion functions required.',
                       '77': 'Problem with reading the SSL CA cert (path? access rights?).',
                       '78': 'The resource referenced in the URL does not exist.',
                       '79': 'An unspecified error occurred during the SSH session.',
                       '80': 'Failed to shut down the SSL connection.',
                       '82': 'Could not load CRL file, missing or wrong format (added in 7.19.0).',
                       '83': 'Issuer check failed (added in 7.19.0).',
                       '84': 'The FTP PRET command failed',
                       '85': 'RTSP: mismatch of CSeq numbers',
                       '86': 'RTSP: mismatch of Session Identifiers',
                       '87': 'unable to parse FTP file list',
                       '88': 'FTP chunk callback reported error'}
    CMD_GET_NAME = 'CMD_GET_NAME'
    CMD_STATUS = 'CMD_STATUS'
    CMD_IS_DEPLOYED = 'CMD_IS_DEPLOYED'
    CMD_LIST_JMS_QUEUES = 'CMD_LIST_JMS_QUEUES'
    CMD_LIST_JMS_TOPICS = 'CMD_LIST_JMS_TOPICS'

    _COMMANDS = {
    CMD_GET_NAME: {'operation': 'read-attribute', 'name': 'name', 'json.pretty': 1},
    CMD_STATUS: {'operation': 'read-attribute', 'name': 'server-state', 'json.pretty': 1},
    CMD_IS_DEPLOYED: {'operation': 'read-resource', 'address': ['deployment', ''], 'json.pretty': 1},
    CMD_LIST_JMS_QUEUES: {'operation': 'read-resource',
                          'address': ['subsystem', 'messaging', 'hornetq-server', 'default', 'jms-queue', '*'],
                          'json.pretty': 1},
    CMD_LIST_JMS_TOPICS: {'operation': 'read-resource',
                          'address': ['subsystem', 'messaging', 'hornetq-server', 'default', 'jms-topic', '*'],
                          'json.pretty': 1}
    }
    management_user = 'root'
    management_password = 'shroot'
    CURL_TIMEOUT = 5

    def __init__(self, logging_level=logging.INFO):
        _logger.setLevel(logging_level)

    def curl_post(self, host, port, data, uri='management', verbose=False):
        url = 'http://{0}:{1}/{2}'.format(host, port, uri)
        self._log('Curling to {0}'.format(url), logging.DEBUG)
        _curl = pycurl.Curl()
        if verbose:
            _curl.setopt(_curl.VERBOSE, 1)
            _curl.setopt(_curl.NOPROGRESS, 0)
        _curl.setopt(_curl.HTTPHEADER, ["Content-Type: application/json"])
        _curl.setopt(_curl.HTTPAUTH, _curl.HTTPAUTH_DIGEST)
        _curl.setopt(_curl.PROXY, '')
        _curl.setopt(_curl.TIMEOUT, 1)
        _curl.setopt(_curl.URL, url)
        _curl.setopt(_curl.USERPWD, self.management_user + ':' + self.management_password)
        _curl.setopt(_curl.POST, 1)
        if data:
            _curl.setopt(_curl.POSTFIELDS, dumps(data))
        _buf = cStringIO.StringIO()
        _curl.setopt(_curl.WRITEFUNCTION, _buf.write)
        try:
            self._log('curl.perform()->', logging.DEBUG)
            _curl.perform()
            self._log('curl.perform()<-', logging.DEBUG)
            results = _buf.getvalue()
            self._log('curled -> %s' % results, logging.DEBUG)
            try:
                return loads(results)
            except Exception as e:
                return results
        except pycurl.error as e:
            self._exception('pycurl.error')
            raise JBossQueryError(e[0], e[1])
        finally:
            _buf.close()
            _curl.close()

    def curl_get(self, host, port, uri, uri_params, verbose=False):
        url = 'http://{0}:{1}/{2}'.format(host, port, uri)
        uri = url + '?' + urllib.urlencode(uri_params)
        self._log('Curling to {0}'.format(url), logging.DEBUG)
        _curl = pycurl.Curl()
        if verbose:
            _curl.setopt(_curl.VERBOSE, 1)
            _curl.setopt(_curl.NOPROGRESS, 0)
        _curl.setopt(_curl.HTTPHEADER, ["Content-Type: application/json"])
        _curl.setopt(_curl.HTTPAUTH, _curl.HTTPAUTH_DIGEST)
        _curl.setopt(_curl.PROXY, '')
        _curl.setopt(_curl.TIMEOUT, self.CURL_TIMEOUT)
        _curl.setopt(_curl.URL, uri)
        _curl.setopt(_curl.USERPWD, self.management_user + ':' + self.management_password)
        _buf = cStringIO.StringIO()
        _curl.setopt(_curl.WRITEFUNCTION, _buf.write)
        try:
            self._log('curl.perform()->', logging.DEBUG)
            _curl.perform()
            self._log('curl.perform()<-', logging.DEBUG)
            http_code = _curl.getinfo(_curl.HTTP_CODE)
            if http_code == 404:
                raise JBossQueryError(404, 'URI %s not found' % uri)
            results = _buf.getvalue()
            self._log('curled -> %s' % results, logging.DEBUG)
            try:
                return loads(results)
            except Exception as e:
                return results
        except pycurl.error as e:
            self._exception('pycurl.error')
            raise JBossQueryError(e[0], e[1] + ' ' + uri)
        finally:
            _buf.close()
            _curl.close()

    def _log(self, message, level):
        _logger.log(level, 'Log:%s' % message)

    def _exception(self, message):
        _logger.exception('Error:%s' % message)

    def http_post(self, host, port, data, uri='management', verbose=False):
        data = self.curl_post(host, port, data, uri, verbose)
        if data['outcome'] != 'success':
            if 'No handler for read-resource at address' in data['failure-description']:
                raise PathNotFoundError(str(data['failure-description']))
            else:
                raise IOError(data)
        else:
            return data

    def http_get(self, host, port, uri, uri_params, verbose=False):
        return self.curl_get(host, port, uri, uri_params, verbose)

    def get_instance_name(self, jboss_address, mgmt_port=9990):
        data = self.http_post(jboss_address, mgmt_port, self._COMMANDS[self.CMD_GET_NAME])
        return data['result']

    def get_status(self, jboss_address, mgmt_port=9990):
        data = self.http_post(jboss_address, mgmt_port, self._COMMANDS[self.CMD_STATUS])
        return data['result']

    def list_deployed(self, jboss_address, mgmt_port=9990):
        _cmd = self._COMMANDS[self.CMD_IS_DEPLOYED]
        _cmd['address'][1] = '*'
        data = self.http_post(jboss_address, mgmt_port, _cmd)
        deployed = {}
        for de in data['result']:
            name = de['result']['name']
            enabled = str(de['result']['enabled']).lower()
            deployed[name] = enabled
        return deployed

    def is_deployed(self, jboss_address, de_name, mgmt_port=9990):
        _cmd = self._COMMANDS[self.CMD_IS_DEPLOYED]
        _cmd['address'][1] = de_name
        try:
            self.http_post(jboss_address, mgmt_port, _cmd)
            return True
        except JBossQueryError as e:
            if 'not found' in str(e):
                return False
            else:
                self._exception('Failed to look up deploy-status of %s' % de_name)

    def get_jms_queues(self, jboss_address, mgmt_port=9990):
        try:
            data = self.http_post(jboss_address, mgmt_port, self._COMMANDS[self.CMD_LIST_JMS_QUEUES])
            queues = {}
            for queue in data['result']:
                queue_name = str(queue['address'][-1:][0]['jms-queue'])
                queues[queue_name] = []
                for entry in queue['result']['entries']:
                    queues[queue_name].append(str(entry))
            return queues
        except PathNotFoundError:
            return None

    def get_jms_topics(self, jboss_address, mgmt_port=9990):
        try:
            data = self.http_post(jboss_address, mgmt_port, self._COMMANDS[self.CMD_LIST_JMS_TOPICS])
            topics = {}
            for topic in data['result']:
                topic_name = str(topic['address'][-1:][0]['jms-topic'])
                topics[topic_name] = []
                for entry in topic['result']['entries']:
                    topics[topic_name].append(str(entry))
            return topics
        except PathNotFoundError:
            return None

    def pib_count(self, jboss_address, mgmt_port=8080):
        uri_params = {'app_server_identifier': 'NONE', 'service_identifier': 'NONE', 'all': 'true', 'count': 'true'}
        sid = self.http_get(jboss_address, mgmt_port, 'pib/healthcheck/getStatus', uri_params)
        count = -1
        for x in range(0, 5):
            count = self.http_get(jboss_address, mgmt_port, 'pib/healthcheck/getResponseAsJson', {'id': sid})
            if count == 'NONE':
                sleep(2)
                continue
            else:
                break
        return count
