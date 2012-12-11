"""
| Copyright (C) 2011 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

Regression test of all examples
This file is invoked by nosetest
"""

import subprocess
import glob

def test_examples():
    """ run examples in a nose generator test
    """
    directory = "../examples/"
    for e in sorted(glob.glob(directory + '*.py')):
        yield run_example, e

def run_example(example):
    retval = subprocess.check_call(['python', example])
    assert retval == 0
