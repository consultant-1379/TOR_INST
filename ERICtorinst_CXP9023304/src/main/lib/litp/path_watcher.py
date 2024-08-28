from time import gmtime, strftime
from httplib import HTTPConnection, OK
from time import sleep
from simplejson import loads as json_parser

__author__ = 'eeipca'

LITP_CLASS_NODE = 'LitpNodeDef'
LITP_CLASS_SITE = 'LitpSiteDef'
LITP_CLASS_CLUSTER = 'LitpClusterDef'

DEF_PATH_ROOT = '/'
DEF_PATH_DEFINITION = '%sdefinition' % DEF_PATH_ROOT
DEF_PATH_INVENTORY = '%sinventory' % DEF_PATH_ROOT


class path_watcher:
    DEFAULT_LS_PORT = 9999
    H_CONTENT_LENGTH = 'content-length'
    OP_GET = 'GET'
    DEBUG = False
    STATUS_KEYS = sorted(
        ['Initial', 'Available', 'Allocated', 'Configured', 'Applied', 'Applying', 'Verified', 'Failed',
         'Deconfigured', 'Removing', 'Removed'])

    def __init__(self, landscape_host, landscape_port=DEFAULT_LS_PORT, _debug=False):
        self.landscape_host = landscape_host
        self.landscape_port = landscape_port
        self.DEBUG = _debug

    def _debug(self, msg):
        if self.DEBUG:
            print(msg)

    def get_max_state_length(self):
        max_key_length = 0
        for key in self.STATUS_KEYS:
            if len(key) > max_key_length:
                max_key_length = len(key)
        return max_key_length

    def get_request(self, litp_path, litp_cmd):
        conn = HTTPConnection(host=self.landscape_host, port=self.landscape_port)
        try:
            path = '%s/%s' % (litp_path, litp_cmd)
            headers = {self.H_CONTENT_LENGTH: 0}
            conn.request(self.OP_GET, path, headers=headers)
            response = conn.getresponse()
            if response.status != OK:
                raise Exception(response.reason)
            response_data = response.read()
            return json_parser(response_data)
        finally:
            conn.close()

    def litp(self, litp_path, command):
        self._debug('HTTP:%s/%s' % (litp_path, command))
        response = self.get_request(litp_path, command)
        if 'error' in response:
            raise IOError(response['error'])
        return response

    def show(self, path, recursive, verbose_type=None, properties=None):
        command = 'show?'
        if recursive:
            command += 'recursive=r&'
        if verbose_type:
            command += '&verbose=%s&' % verbose_type
        if properties:
            command += '&attributes=['
            for prop in properties:
                command += '\'%s\'' % prop
            command += ']'
        return self.litp(path, command)

    def get_empty_status(self):
        _map = {}
        for key in self.STATUS_KEYS:
            _map[key] = 0
        return _map


class Formatter:
    VALUE_INC = '\033[33m'
    VALUE_DEC = '\033[36m'
    VALUE_NOC = '\033[92m'
    VALUE_KEY = '\033[7m'
    ENDC = '\033[0m'

    def format_color(self, name, value, color):
        return '{0}{1}[{2}]{3} '.format(name, color, value, Formatter.ENDC)

    def format_line(self, current_count, last_count):
        message = ''
        for idx, val in enumerate(current_count):
            cc = current_count[val]
            color = Formatter.VALUE_NOC
            if cc > last_count[val]:
                color = Formatter.VALUE_DEC
            elif cc < last_count[val]:
                color = Formatter.VALUE_INC
            message += self.format_color(val, cc, color)
        return message.strip()

    def print_if_changed(self, base_path, current_status, last_status):
        diff = False
        for key, count in current_status.items():
            if last_status[key] != count:
                diff = True
                break
        if diff:
            this_message = self.format_line(current_status, last_status)
            now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
            base_path = '[{0}]{1}{2}{3}'.format(now, self.VALUE_KEY, base_path, Formatter.ENDC)
            print('{0} -> {1}'.format(base_path, this_message))


def watch_path_1(ms_host, paths):
    litp = path_watcher(ms_host)
    path_data = {}
    for path in paths:
        path_data[path] = litp.get_empty_status()
    printer = Formatter()
    while True:
        for base_path, last_status in path_data.items():
            current_status = litp.get_empty_status()
            try:
                data = litp.show(base_path, True, ['status'])
            except IOError as ioe:
                print('Oops {0}'.format(ioe))
                continue
            for component in data:
                status = str(component[1]['status'])
                scount = 0
                if status in current_status:
                    scount = current_status[status]
                scount += 1
                current_status[status] = scount
            printer.print_if_changed(base_path, current_status, last_status)
            path_data[base_path] = current_status
        sleep(1)


if __name__ == "__main__":
    landscape_host = 'localhost'
    try:
        watch_path_1(landscape_host, ['/inventory/deployment1/ms1', 
        '/inventory/deployment1/cluster1/sc1', '/inventory/deployment1/cluster1/sc2'])
    except KeyboardInterrupt:
        pass