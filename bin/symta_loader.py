#!/usr/bin/env python
"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

SymTA/S 1.4 Loader example
"""


from pycpa import analysis
from pycpa import symload
from pycpa import options

import os

## this is necessary because the file is also called from the regression test suite
path = os.path.dirname(os.path.realpath(__file__))

options.init_pycpa()
loader = symload.SymtaLoader14()
s = loader.parse(path + "/symta14_test.xml")
results = analysis.analyze_system(s)

print("Result:")
for r in sorted(s.resources, key=str):
    print "results for resource %s" % r.name
    for t in sorted(r.tasks, key=str):
        print str(t), "-", results[t].wcrt
