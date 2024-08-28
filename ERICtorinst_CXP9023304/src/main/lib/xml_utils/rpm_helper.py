from optparse import OptionParser
import os
import subprocess
import sys
from ini import ini_reader


class rpm_helper:
    h_NAME = 'NAME'
    h_VERSION = 'VERSION'
    h_RELEASE = 'RELEASE'
    h_PACKAGER = 'PACKAGER'
    h_FILENAMES = 'FILENAMES'
    _RPM = 'rpm'

    def __init__(self, tor_ini=None):
        if tor_ini:
            self._RPM = ini_reader.get_option(tor_ini, sys.platform, 'RPM')

    def execute_process(self, args, wd=None):
        try:
            process = subprocess.Popen(args, cwd=wd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        except WindowsError as we:
            print('{0}'.format(args))
            raise we
        stdout, stderr = process.communicate()
        if process.returncode:
            raise IOError('Error executing command {0}\n{1}'.format(args, stderr))
        return stdout.split('\n')

    def h_format(self, header_name):
        return header_name + ':%{' + header_name + '}'

    def get_rpm_header(self, rpm_path):
        query_format = self.h_format(self.h_NAME)
        query_format = '{0}\n{1}'.format(query_format, self.h_format(self.h_VERSION))
        query_format = '{0}\n{1}'.format(query_format, self.h_format(self.h_RELEASE))
        query_format = '{0}\n{1}'.format(query_format, self.h_format(self.h_PACKAGER))
        if sys.platform.startswith('win'):
            return self._win_get_rpm_header(rpm_path, query_format)
        else:
            return self._nix_get_rpm_header(rpm_path, query_format)

    def _win_get_rpm_header(self, rpm_path, query, keyed=True):
        rpm_path = rpm_path.replace('\\', '/')
        if not os.path.exists(rpm_path):
            raise IOError('File \'{0}\' not found'.format(rpm_path))
        command = '{0} -q -p --queryformat "{1}" {2}'.format(self._RPM, str(query), rpm_path)
        wd = os.path.dirname(self._RPM)
        if wd == '':
            wd = None
        result = self.execute_process(command, wd)
        if keyed:
            header = {}
            for line in result:
                line = line.strip()
                if len(line) == 0:
                    continue
                line = line.split(':')
                header[line[0]] = line[1]
            return header
        else:
            return result

    def _nix_get_rpm_header(self, rpm_path, query, keyed=True):
        if not os.path.exists(rpm_path):
            raise IOError('File \'{0}\' not found'.format(rpm_path))
        args = [self._RPM, '-q', '-p', '--queryformat', '{0}'.format(query), rpm_path]
        wd = os.path.dirname(self._RPM)
        if wd == '':
            wd = None
        result = self.execute_process(args, wd)
        if keyed:
            header = {}
            for line in result:
                line = line.strip()
                if len(line) == 0:
                    continue
                line = line.split(':')
                header[line[0]] = line[1]
            return header
        else:
            return result

    def get_rpm_contents(self, rpm_path):
        if not os.path.exists(rpm_path):
            raise IOError('{0} not found'.format(rpm_path))
        args = [self._RPM, '-q', '-p', '-l', rpm_path.replace('\\', '/')]
        wd = os.path.dirname(self._RPM)
        if wd == '':
            wd = None
        return self.execute_process(args, wd)

    def get_rpm_version(self, rpm_path):
        header = self.get_rpm_header(rpm_path)
        return header[self.h_VERSION]

    def get_rpm_release(self, rpm_path):
        header = self.get_rpm_header(rpm_path)
        return header[self.h_RELEASE]

    def query(self, rpm_path, query_string):
        if sys.platform.startswith('win'):
            return self._win_get_rpm_header(rpm_path, query_string, False)
        else:
            return self._nix_get_rpm_header(rpm_path, query_string, False)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-v", dest="version")
    parser.add_option("-r", dest="release")
    parser.add_option("-a", dest="header")
    (options, args) = parser.parse_args()
    rpmh = rpm_helper(None)
    if options.version:
        print(rpmh.get_rpm_version(options.version))
    elif options.release:
        print(rpmh.get_rpm_release(options.release))
    elif options.header:
        header = rpmh.get_rpm_header(options.header)
        for key, value in header.items():
            print('%s %s' % (key, value))


