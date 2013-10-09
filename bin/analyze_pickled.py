#!/usr/bin/env python2
"""
| Copyright (C) 2013 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Simple pickled system analyzer
"""

from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import graph
from pycpa import options

try:
    import cPickle as pickle
except ImportError:
    import pickle

import sys

options.parser.add_argument('--file', type=str,
                            help='filename of the pickled system. MUST BE THE LAST ARGUMENT')

def main():
    """ Loads the pickled system and analyzes it with the given command
    line parameter settings.
    """
    system = None

    # read the last argument without the help of argparse
    # since argparse is not initialized yet!
    if len(sys.argv) < 3:
        print ("Please specify a filename!")
        print ("Format: analyze_pickled.py [optinal pycpa parameters] --file FILENAME ")
        exit(1)

    filename = sys.argv[-1]
    print("Loading: %s" % filename)

    try:
        with open(filename, 'rb') as f:
            s = pickle.load(f)
    except IOError as e:
        print e
        exit(1)

    print ("DONE")
    print ("... handing over to the pycpa kernel\n\n\n")

    # init pycpa and trigger command line parsing
    # this must be done late, as the modules dynamically loaded
    # by pickle can add additional argparse arguments
    options.init_pycpa()

    task_results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print("%s: wcrt=%d" % (t.name, task_results[t].wcrt))
            print("    b_wcrt=%s" % (task_results[t].b_wcrt_str()))


if __name__ == "__main__":
    main()

