"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved

:Authors:
         - Philip Axer

Description
-----------

SMFF Loader/Annotation example
"""


import os

from pycpa import analysis
from pycpa import smff_loader
from pycpa import graph
from pycpa import options

def smff_test():

    ## this is necessary because the file is also called from the regression test suite
    path = os.path.dirname(os.path.realpath(__file__))

    options.init_pycpa()

    loader = smff_loader.SMFFLoader()
    s = loader.parse(path + "/smff_system.xml")


    # graph the smff system
    graph.graph_system(s, filename="smff_graph.pdf")
    
    # analyze the system
    analysis.analyze_system(s)
    
    # print some analysis results
    print("Result:")
    print(s)
    for r in sorted(s.resources, key=str):
        print "results for resource %s" % r.name
        for t in sorted(r.tasks, key=str):
            print("%s - %d " % (str(t.name) , t.wcrt))

    # backannotate the xml
    loader.annotate_results()
    
    # write it
    loader.write(filename="smff_annotated.xml")
    
if __name__ == "__main__":
    smff_test()        
