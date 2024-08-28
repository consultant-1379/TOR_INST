#!/usr/bin/python

from StringIO import StringIO
import fnmatch
from optparse import OptionParser
from xml.dom.minidom import parse, getDOMImplementation, xml
from xml.sax import make_parser, handler
from os import path, walk
import sys


class simple_parser(handler.ContentHandler):
    def __init__(self):
        """
        Default Constructor
        """
        handler.ContentHandler.__init__(self)
        self.dommer = getDOMImplementation()
        self.doc = None
        self.parent_node = None
        self.cw_element = None
        self.parent_node = None

    def getParentNode(self):
        """
        Get the parent node the xml snippet should be inserted into

        @return: the parent node
        @rtype: Element
        """
        return self.parent_node

    def getExtractedNodes(self):
        """
        Get the list of nodes to insert into the TORINST definition xml

        @return: the nodes the insert
        @rtype: Element[]
        """
        return self.extracted_nodes

    def startDocument(self):
        """
        Reset the parser for a new parse run
        """
        self.doc = self.dommer.createDocument(None, 'ROOT', None)
        self.parent_node = self.doc.documentElement
        self.cw_element = None

    def endDocument(self):
        """
        Finised parsing, setup return values
        """
        self.parent_node = self.doc.documentElement.firstChild
        self.extracted_nodes = self.doc.documentElement.firstChild.childNodes

    def startElement(self, name, attrs):
        """
        Parse an element
        """
        if self.cw_element:
            self.parent_node = self.cw_element
        self.cw_element = self.doc.createElement(name)
        self.parent_node.appendChild(self.cw_element)
        for a_name, a_value in attrs.items():
            self.cw_element.setAttribute(a_name, a_value)

    def endElement(self, name):
        """
        Finish parsing an element
        """
        if self.cw_element:
            self.cw_element = self.parent_node
            if self.cw_element:
                self.parent_node = self.cw_element.parentNode

    def characters(self, data):
        """
        Parse text elements, if no text then nothing is added
        """
        data = data.strip()
        if len(data) > 0:
            text_node = self.doc.createTextNode(data)
            self.cw_element.appendChild(text_node)


def merge(xml_dom, parent_container, insert_nodes):
    """
    Merge an XML snippet to another XML doc

    @param           xml_dom: Main xml DOM document to insert into
    @type            xml_dom: Document
    @param  parent_container: The parent node in the main document to insert into
    @type   parent_container: Element
    @param      insert_nodes: The list of nodes to insert
    @type       insert_nodes: Element[]
    @return                 : None
    """
    parent_node_type = str(parent_container.nodeName)
    tokens = parent_node_type.split(':')
    if len(tokens) == 2:
        _parent_typename = tokens[1]
        parent_id = parent_container.getAttribute('id')
    else:
        # Default to an element type called component-def
        _parent_typename = 'component-def'
        parent_id = str(parent_container.nodeName)
    elements = xml_dom.getElementsByTagNameNS('*', _parent_typename)
    if not elements:
        raise IOError('No elements found for parent type {0}.(1)'.format(_parent_typename, parent_id))
    for element in elements:
        if element.getAttribute('id') == parent_id:
            print('\tInserting {0} node(s) into parent \'{1}.{2}\''
                  .format(len(insert_nodes), str(element.nodeName), parent_id))
            #http://jira-oss.lmera.ericsson.se/browse/TORD-632
            node = insert_nodes[0]
            while node:
                new = node.nextSibling
                element.appendChild(node)
                node = new


def intent_writer(writer, indent):
    """
    Indent a writer i.e. tab it out

    @param writer: The writer to indent
    @type writer: writer
    @param indent: The tab count
    @type indent: int
    @rtype: None
    """
    for i in range(0, indent):
        writer.write('\t')


def write_node(writer, node, indent):
    """
    Write a node to a writer

    @param writer: The writer stream
    @type writer: writer
    @param node: The Xml node to write
    @type node: Node
    @param indent: The tab count
    @type indent: int
    @rtype: None
    """
    if node.nodeType == xml.dom.Node.TEXT_NODE:
        data = str(node.nodeValue).strip()
        if len(data) > 0:
            writer.write(data)
    elif node.nodeType == xml.dom.Node.COMMENT_NODE:
        intent_writer(writer, indent)
        writer.write('<!-- {0} -->\n'.format(node.nodeValue))
    elif node.nodeType == xml.dom.Node.ELEMENT_NODE:
        intent_writer(writer, indent)
        writer.write('<{0}'.format(node.nodeName))
        attrs = node._get_attributes()
        a_names = attrs.keys()
        a_names.sort()
        for a_name in a_names:
            writer.write(' {0}=\"{1}\"'.format(a_name, attrs[a_name].value))
        if node.childNodes:
            writer.write('>')
            if len(node.childNodes) == 1 and node.firstChild.nodeType == xml.dom.Node.TEXT_NODE:
                # Special handling when the only child in a text node, LITP xml parsing
                # doesn't really like free text split across multiple line e.g.:
                # <abc>
                #   Some value...
                # </abc>
                # It need to be :
                # <abc>Some value...</abc>
                writer.write(str(node.firstChild.nodeValue.strip()))
            else:
                writer.write('\n')
                for child in node.childNodes:
                    write_node(writer, child, indent + 1)
                intent_writer(writer, indent)
            writer.write('</{0}>\n'.format(node.nodeName))
        else:
            writer.write('/>\n')
    else:
        raise IOError('Unknown node type {0}'.format(node.nodeType))


def print_xml(dom_tree, _file):
    """
    Print a DOM tree

    @param dom_tree: The dom tree to print
    @rtype: None
    """
    writer = StringIO()
    for node in dom_tree.childNodes:
        write_node(writer, node, 0)
    if _file:
        f = open(_file, 'w')
        try:
            f.write(writer.getvalue())
        finally:
            f.close()
        print('Merged result written to {0}'.format(_file))
    else:
        print(writer.getvalue())


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-d', '--definition', help="Landscape definition xml", dest='dest_xml')
    parser.add_option('-s', '--snippets', help="Snippets base directory", dest='snippets')
    parser.add_option('-a', '--auto_version', help="Insert the version info base on the RPM version",
                    dest='auto_version', action="store_true")
    parser.add_option('-o', '--output', help="Output file", dest='output_file')
    (options, args) = parser.parse_args()
    if not options.dest_xml:
        parser.print_help()
        sys.exit(2)
    if not options.snippets:
        parser.print_help()
        sys.exit(2)
    dest_xml = parse(options.dest_xml)
    sax_parser = make_parser()
    simple_parser = simple_parser()
    sax_parser.setContentHandler(simple_parser)
    for root, subFolders, files in walk(options.snippets):
        for _file in files:
            if fnmatch.fnmatch(_file, '*.xml'):
                full_path = path.join(root, _file)
                print('Merging contents of {0}'.format(full_path))
                sax_parser.parse(full_path)
                parent = simple_parser.getParentNode()
                nodes_to_insert = simple_parser.getExtractedNodes()
                merge(dest_xml, parent, nodes_to_insert)
    print_xml(dest_xml, options.output_file)
