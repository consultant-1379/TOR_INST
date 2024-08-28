from optparse import OptionParser
from os import linesep
from sys import argv, exit, stdout
from xml.sax import make_parser
from xml.sax.handler import ContentHandler

from litp.litp_helper import litp_helper


class landscape_xml_parser(ContentHandler):
    def __init__(self):
        self.fdn = []
        self.current_attribute_name = None
        self.current_attribute_value = None
        self.path_attributes = None
        self.path_class_type = None

    def print_line(self, message):
        stdout.write('{0}{1}'.format(message, linesep))

    def parse(self, xml_file):
        parser = make_parser()
        parser.setContentHandler(self)
        self.path_attributes = {}
        self.path_class_type = {}
        parser.parse(open(xml_file))

    def get_parent(self, path):
        return '/'.join(path.split('/')[:-1])

    def delta_live(self, litp_host, format_type='raw'):
        if not self.path_attributes:
            raise IOError('No XML parsed.')
        litp = litp_helper(litp_host)
        all_current_paths = litp.get_children('/', True, True)
        paths = self.path_attributes.keys()
        for path in paths:
            # print(path)
            path_exits = path in all_current_paths
            if not path_exits:
                parent = path
                while True:
                    parent = self.get_parent(parent)
                    if parent not in all_current_paths:
                        parent_class = self.path_class_type[parent]
                        create_cmd = self.format_create(parent, parent_class, format_type)
                        self.print_line(create_cmd)
                    else:
                        break
                class_type = self.path_class_type[path]
                create_cmd = self.format_create(path, class_type, format_type)
                self.print_line(create_cmd)
                for name, value in self.path_attributes[path].items():
                    update_cmd = self.format_update(path, name, value, format_type)
                    self.print_line(update_cmd)
            else:
                ls_props = all_current_paths[path]['properties']
                xml_props = self.path_attributes[path]
                att_diff = set(xml_props.keys()) - set(ls_props.keys())
                if att_diff:
                    for ad in att_diff:
                        update_cmd = self.format_update(path, ad, xml_props[ad], format_type)
                        self.print_line(update_cmd)

    def get_current_fdn(self):
        return '/%s' % '/'.join(self.fdn)

    def characters(self, content):
        self.current_attribute_value = str(content).strip()

    def startElement(self, name, attrs):
        if name.startswith('litp'):
            node_name = str(attrs.getValueByQName('id'))
            self.fdn.append(node_name)
        else:
            self.current_attribute_name = str(name)

    def endElement(self, name):
        fdn = self.get_current_fdn()
        if fdn not in self.path_attributes:
            self.path_attributes[fdn] = {}
        if name.startswith('litp'):
            self.path_class_type[fdn] = name.split(':')[1]
            self.fdn.pop()
        else:
            self.path_attributes[fdn][self.current_attribute_name] = self.current_attribute_value
            self.current_attribute_name = None
            self.current_attribute_value = None

    def format_create(self, litp_path, class_type, format_type='raw'):
        if format_type == 'raw':
            return 'litp {0} create {1}'.format(litp_path, class_type)
        elif format_type == 'bash':
            cmd = '/usr/bin/litp {0} show > /dev/null 2>&1\n'
            cmd += 'if [ $? -ne 0 ] ; then\n'
            cmd += '\techo "litp {0} create {1}"\n'
            cmd += '\t/usr/bin/litp {0} create {1}\n'
            cmd += 'fi\n'
            return cmd.format(litp_path, class_type)
        else:
            raise IOError('Unknown format type "{0}"'.format(format_type))

    def format_update(self, litp_path, att_name, att_value, format_type='raw'):
        if format_type == 'raw':
            return 'litp %s update %s=\'%s\'' % (litp_path, att_name, att_value)
        elif format_type == 'bash':
            cmd = '/usr/bin/litp {0} show > /dev/null 2>&1\n'
            cmd += 'if [ $? -ne 0 ] ; then\n'
            cmd += '\techo "Path {0} not found"\n'
            cmd += '\texit 1\n'
            cmd += 'fi\n'
            cmd += 'echo "litp {0} update {1}=\'{2}\'"\n'
            cmd += '/usr/bin/litp {0} update {1}=\'{2}\'\n'
            cmd += 'if [ $? -ne 0 ] ; then\n'
            cmd += '\texit 1\n'
            cmd += 'fi\n'
            return cmd.format(litp_path, att_name, att_value)
        else:
            raise IOError('Unknown format type "{0}"'.format(format_type))


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('--file', dest='filename')
    parser.add_option('--landscape_host', dest='landscape_host')
    parser.add_option('--format', dest='format', default='raw')
    (options, args) = parser.parse_args()
    if len(argv) == 1:
        parser.print_help()
        exit()
    landscape_host = 'localhost'
    if options.landscape_host:
        landscape_host = options.landscape_host
    cmd_parser = landscape_xml_parser()
    cmd_parser.parse(options.filename)
    cmd_parser.delta_live(landscape_host, options.format)