from StringIO import StringIO
from xml.dom.minidom import xml


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


def print_xml(dom_tree, file):
    """
    Print a DOM tree

    @param dom_tree: The dom tree to print
    @rtype: None
    """
    writer = StringIO()
    for node in dom_tree.childNodes:
        write_node(writer, node, 0)
    if file:
        f = open(file, 'w')
        try:
            f.write(writer.getvalue())
        finally:
            f.close()
        print('Result written to {0}'.format(file))
    else:
        print(writer.getvalue())
