'''
Created on Mar 29, 2011

@author: paxer
'''

import logging
from pycpa import analysis
from pycpa import symload
from pycpa import options

import os

## this is necessary because the file is also called from the regression test suite
path = os.path.dirname(os.path.realpath(__file__))

options.init_pycpa()

loader = symload.SymtaLoader14()
s = loader.parse(path + "/symta14_test.xml")
analysis.analyze_system(s)

print("Result:")
print(s)
for r in sorted(s.resources, key=str):
    print "results for resource %s" % r.name
    for t in sorted(r.tasks, key=str):
        print(str(t), " - ", t.wcrt)
