import base64
from optparse import OptionParser
import bz2


def encode(string):
	_string = bz2.compress(string)
	_string = base64.b64encode(_string)
	return _string


def decode(string):
	_string = base64.b64decode(string)
	return bz2.decompress(_string)


if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option("-d", dest="decode_string")
	parser.add_option("-e", dest="encode_string")
	(options, args) = parser.parse_args()
	if options.decode_string:
		print(decode(options.decode_string))
	if options.encode_string:
		print(encode(options.encode_string))