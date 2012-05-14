"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Simple SPP example
"""

import logging
from matplotlib import pyplot


from pycpa import *
from pycpa import spp
from pycpa import graph
from pycpa import options

def simple_test():
    # initialyze pycpa. (e.g. read command line switches and set up default options)
    # TODO: NOT NEEDED ANYMORE - Remove after fixing doc

    # generate an new system
    s = model.System()

    # instantiate a resource
    r1 = s.bind_resource(model.Resource("R1", spp.SPPScheduler()))

    # create and bind tasks to r1
    t11 = r1.bind_task(model.Task("T11", wcet=5, bcet=5,
                               scheduling_parameter=1))
    t12 = r1.bind_task(model.Task("T12", wcet=9, bcet=1,
                               scheduling_parameter=2))

    # connect communicating tasks: T11 -> T12
    t11.link_dependent_task(t12)

    # register a PJd event model
    t11.in_event_model = model.EventModel(P=30, J=60)

    # plot the system graph to visualize the architecture
    g = graph.graph_system(s, 'simple_graph.pdf')

    # perform the analysis
    print("Performing analysis")
    results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print("%s: wcrt=%d" % (t.name, results[t].wcrt))


if __name__ == "__main__":
    simple_test()

