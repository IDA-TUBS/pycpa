"""
| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

This module contains methods to initalize the pycpa environment.
It will setup an argument parser and set up default parameters.
"""

from __future__ import print_function

MAX_ITERATIONS = 1000
MAX_WCRT = float('inf')
OFFSET_OUTPUT_MODEL = False
IMPROVED_OUTPUT_MODEL = True
EPSILON = 1e-12
MAX_ERRORS = 10
INFINITY = float('inf')

import argparse
import logging
import sys

from pycpa import __license_text__

parser = argparse.ArgumentParser(description='Scheduling Analysis')
parser.add_argument('--max_iterations', type=int,
                    default=MAX_ITERATIONS,
                    help='Maximum number of iterations in a local analysis (default=%d)' % (MAX_ITERATIONS))
parser.add_argument('--max_wcrt', type=int,
                    default=MAX_WCRT,
                    help='Maximum response-time in a local analysis (default=%f)' % (MAX_WCRT))
parser.add_argument('--e2e_improved', action='store_true',
                    help='enable improved end to end analysis (experimental)')
parser.add_argument('--nocaching', action='store_true',
                    help='disable event-model caching')
parser.add_argument('--show', action='store_true',
                    help='Show plots (interactive).')
parser.add_argument('--propagation', type=str, default='busy_window',
                    help='Event model propagation method (jitter, jitter_dmin, jitter_offset, busy_window). default: busy_window')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='be more talkative')



welcome = "pyCPA a Compositional Performance Analysis Toolkit implemented in Python.\n\n" \
+ __license_text__

_opts = None


def get_opt(option):
    """ Returns the option specified by the parameter.
    If called for the first time, the parsing is done.
    """
    global _opts
    if _opts is None: _init_pycpa()
    return getattr(_opts, option)

def pprintTable(out, table, column_sperator="", header_separator=":"):
    """Prints out a table of data, padded for alignment
    @param out: Output stream (file-like object)
    @param table: The table to print. A list of lists.
    Each row must have the same number of columns. """

    def format(num):
        """Format a number according to given places.  Adds commas, etc. Will truncate floats into ints!"""
        #try:
        #    inum = int(num)
        #    return locale.format("%.*f", (0, inum), True)
        #except (ValueError, TypeError):
        return str(num)
    def get_max_width(table1, index1):
        """Get the maximum width of the given column index"""
        return max([len(format(row1[index1])) for row1 in table1])

    col_paddings = []
    for i in range(len(table[0])):
        col_paddings.append(get_max_width(table, i))

    for row in table:
        # left col
        print(row[0].ljust(col_paddings[0] + 1), end=header_separator, file=out)
        # rest of the cols
        for i in range(1, len(row)):
            col = format(row[i]).rjust(col_paddings[i] + 1)
            print(col, end=" " + column_sperator, file=out)
        print(file=out)

    return

def _init_pycpa():
    global _opts
    opts_dict = dict()
    _opts = parser.parse_args()

    # set up the general logging object

    if _opts.verbose == True:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)


    print (welcome)
    print ("invoked via: " + " ".join(sys.argv) + "\n")

    #table of selected paramters

    table = list()
    for attr in dir(_opts):
        if not attr.startswith("_"):
            row = ["%s" % attr, str(getattr(_opts, attr))]
            opts_dict[attr] = str(getattr(_opts, attr))
            table.append(row)
    pprintTable(sys.stdout, table)

    print("\n\n")

