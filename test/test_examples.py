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
"""

import unittest
import subprocess
import glob
import runpy
import sys

class ExamplesTest(unittest.TestCase):
    def __init__(self, f, fsock=sys.stdout):
        unittest.TestCase.__init__(self)
        self.file = f
        self.fsock = fsock
        self._testMethodDoc = "Run example " + f

    def runTest(self):
        # call, pro: no outputs, con: no exceptions
        self.fsock.write("######################################################")
        self.fsock.write("# RUNNING EXAMPLE: %s" % self.file)
        self.fsock.write("######################################################")

        retval = subprocess.check_call(['python', self.file], stderr = self.fsock, stdout = self.fsock)

        self.fsock.write("######################################################")
        # like above:
        #retval = subprocess.call(['python', self.file], stderr = subprocess.PIPE, stdout = subprocess.PIPE)
        #self.assertEqual(retval, 0)

        # runs files directly, pro: we get exceptions, con: we get all outpus
        #runpy.run_path(self.file)


if __name__ == "__main__":

    directory = "../examples/"


    suite = unittest.TestSuite()
    fsock = open('examples.log', 'w')

    for e in sorted(glob.glob(directory + '*.py')):
        suite.addTest(ExamplesTest(e, fsock))

    unittest.TextTestRunner(verbosity = 2).run(suite)

    fsock.close()
