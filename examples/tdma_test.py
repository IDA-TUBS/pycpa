"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

TDMA analysis example
"""

from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import graph
from pycpa import options


def tdma_test():

    options.init_pycpa()

    s = model.System()
    r1 = s.bind_resource(model.Resource("R1", schedulers.TDMAScheduler()))
    r2 = s.bind_resource(model.Resource("R2", schedulers.TDMAScheduler()))

    # scheduling_parameter denotes the slotsize
    t11 = r1.bind_task(model.Task("T11", wcet=10, bcet=5, scheduling_parameter=2))
    t12 = r1.bind_task(model.Task("T12", wcet=3, bcet=1, scheduling_parameter=2))


    t21 = r2.bind_task(model.Task("T21", wcet=2, bcet=2, scheduling_parameter=2))
    t22 = r2.bind_task(model.Task("T22", wcet=3, bcet=3, scheduling_parameter=2))


    t11.link_dependent_task(t21)
    t12.link_dependent_task(t22)

    t11.in_event_model = model.PJdEventModel()
    t11.in_event_model.set_PJd(30, 5)

    t12.in_event_model = model.PJdEventModel()
    t12.in_event_model.set_PJd(15, 6)

    g = graph.graph_system(s, 'tdma_graph.pdf')

    print("Performing analysis")
    results = analysis.analyze_system(s)

    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print str(t), " - ", results[t].wcrt
            print "    ", results[t].b_wcrt_str()


if __name__ == "__main__":

    tdma_test()

