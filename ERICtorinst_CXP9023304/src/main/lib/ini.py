from ConfigParser import SafeConfigParser
from optparse import OptionParser
import os
import sys


class ini_reader:
    EXIT_USAGE = 2
    EXIT_FNF = 3
    EXIT_SECTION_NF = 4
    EXIT_OPTION_NF = 5

    @staticmethod
    def init_reader(ini_file):
        if not os.path.exists(ini_file):
            ini_reader._exit(ini_reader.EXIT_FNF, 'ERROR: {0} not found'.format(ini_file))
        inireader = SafeConfigParser()
        inireader.optionxform = str
        inireader.read(ini_file)
        return inireader

    @staticmethod
    def get_option(ini_file, section, option):
        if ini_file:
            inireader = ini_reader.init_reader(ini_file)
        if inireader.has_section(section):
            if inireader.has_option(section, option):
                return inireader.get(section, option)
            else:
                ini_reader._exit(ini_reader.EXIT_OPTION_NF,
                                 'No option called {0} found in section {1} in {2}'.format(option, section, ini_file))
        else:
            ini_reader._exit(ini_reader.EXIT_SECTION_NF, 'No section called {0} found in {1}'.format(section, ini_file))

    @staticmethod
    def get_section(ini_file, section, keys_only):
        inireader = ini_reader.init_reader(ini_file)
        if inireader.has_section(section):
            items = inireader.items(section)
            for item in items:
                if keys_only:
                    return item[0]
                else:
                    return '{0}={1}'.format(item[0], item[1])
        else:
            ini_reader._exit(ini_reader.EXIT_SECTION_NF, 'No section called {0} found in {1}'.format(section, ini_file))

    @staticmethod
    def get_block_names(ini_file):
        inireader = ini_reader.init_reader(ini_file)
        return inireader.sections()

    @staticmethod
    def _exit(exit_code, message=None):
        if message:
            print(message)
        sys.exit(exit_code)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-f", dest="ini_file")
    parser.add_option("-s", dest="section")
    parser.add_option("-o", dest="option")
    parser.add_option("--keys", dest="keys_only", action="store_true")
    parser.add_option("--block_keys", dest="block_keys", action="store_true")
    if len(sys.argv) == 1:
        parser.print_help()
        ini_reader._exit(ini_reader.EXIT_USAGE)
    (options, args) = parser.parse_args()
    if options.block_keys:
        for b in ini_reader.get_block_names(options.ini_file):
            print(b)
    else:
        if not options.option:
            print(ini_reader.get_section(options.ini_file, options.section, options.keys_only))
        else:
            print(ini_reader.get_option(options.ini_file, options.section, options.option))
