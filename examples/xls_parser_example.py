"""
| Copyright (C) 2014 Daniel Thiele
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Daniel Thiele (thiele@ida.ing.tu-bs.de)

Description
-----------

XLS parser example
"""

from pycpa import util
from pycpa import xls_parser

import sys


def xls_parser_test(filename):
    x = xls_parser.XLS_parser(filename)
    x.parse()
    print("Using file: %s" % filename)
    print("Sheets: %s" % x.sheets.keys())
    print("All data: %s" % x.sheets)
    print("Sheet \"foo\", line 1 (index starts at zero): %s" % x.get_line_of_sheet('foo', 1))
    print("Sheet \"foo\", column \"A\", line 2 (index starts at zero): %s" % x.get_line_entry_of_sheet('foo', 2, 'A'))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Call with xls_parser_example.xls as single argument.")
    else:
        xls_parser_test(sys.argv[1])




# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
