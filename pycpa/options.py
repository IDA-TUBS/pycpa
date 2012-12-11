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
parser.add_argument('--check_violations', action='store_true',
                    help='check for constraint violations during analysis')
parser.add_argument('--show', action='store_true',
                    help='Show plots (interactive).')
parser.add_argument('--propagation', type=str, default='busy_window',
                    help='Event model propagation method (jitter, jitter_dmin, jitter_offset, busy_window). default: busy_window')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='be more talkative')



welcome = "pyCPA a Compositional Performance Analysis Toolkit implemented in Python.\n\n" \
+ __license_text__

_opts = None
_opts_dict = None


def get_opt(option):
    """ Returns the option specified by the parameter.
    If called for the first time, the parsing is done.
    """
    global _opts
    if _opts is None: init_pycpa(implicit=True)
    return getattr(_opts, option)

def set_opt(option, value):
    """ Sets the option specified by the parameter to value.
    If called for the first time, the parsing is done.
    """
    global _opts
    if _opts is None: init_pycpa(implicit=True)
    setattr(_opts, option, value)

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

def init_pycpa(implicit = False):
    """ Initialize pyCPA.
    This function parses the options and prints them for reference.
    It is called once automatically from get_opt() or set_opt()
    during the beginning of the analysis.
    It can also be called directly to control when initialization happens
    in order to modify options afterwards.
    """
    global _opts, _opts_dict
    _opts_dict = dict()
    if not implicit:
        # in this case we are explicitly initialized,
        # output welcome and consume cmdline parameters
        print (welcome)
        print ("invoked via: " + " ".join(sys.argv) + "\n")

        _opts = parser.parse_args()
    else:
        print ("implicitly invoked pycpa")
        # implicit init, through regression test or non-pycpa script
        # distill defaults and arguments from the parser and pretend nothing happend
        _opts = argparse.Namespace()
        for action in parser._actions:
            if action.default == argparse.SUPPRESS:
                continue
            setattr(_opts, action.dest, action.default)
#table of selected paramters

    table = list()
    for attr in dir(_opts):
        if not attr.startswith("_"):
            row = ["%s" % attr, str(getattr(_opts, attr))]
            _opts_dict[attr] = str(getattr(_opts, attr))
            table.append(row)
    if not implicit:
        pprintTable(sys.stdout, table)
        print("\n\n")
    # set up the general logging object
    if get_opt('verbose') == True:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


