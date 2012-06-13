"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

SMFF Loader/Annotation example
"""


import os
import string

from pycpa import analysis
from pycpa import smff_loader
from pycpa import graph
from pycpa import options

def smff_test(filename, outfile, plot, verbose):

    print "loading", filename
    loader = smff_loader.SMFFLoader()
    s = loader.parse(filename)


    if plot == True:
        # graph the smff system
        graph_file = string.replace(os.path.basename(filename), ".xml", "") + ".pdf"
        graph.graph_system(s, sched_param=True, exec_times=True, filename=graph_file)

    try:
        # analyze the system            
        results = analysis.analyze_system(s)

        # print some analysis results

        print("Result:")
        for r in sorted(s.resources, key=str):
            print "results for resource %s" % r.name
            for t in sorted(r.tasks, key=str):
                print("%s - %d " % (str(t.name) , results[t].wcrt))

        if outfile is not None:
            # backannotate the xml
            loader.annotate_results()

            # write it
            loader.write(filename=outfile)

    except analysis.NotSchedulableException as (e):
        print str(e)

if __name__ == "__main__":
    # this is necessary because the file is also called from the regression test suite
    default_file = os.path.dirname(os.path.realpath(__file__)) + "/smff_system.xml"
    default_outfile = os.path.dirname(os.path.realpath(__file__)) + "/smff_system_annotated.xml"

    options.parser.add_argument('--file', '-f', type=str, default=default_file,
                    help='File to load.')
    options.parser.add_argument('--ofile', '-of', type=str, default=default_outfile,
                    help='annotated output xml')
    options.parser.add_argument('--graph', '-g', action='store_true',
                    help='Graph the system, file will be saved to FILE.pdf. Where FILE is the input xml.')

    smff_test(options.get_opt('file'), options.get_opt('ofile'), options.get_opt('graph'), options.get_opt('verbose'))
