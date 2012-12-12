"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Simple EDF example, taken from Spuri1996
"""

from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import graph
from pycpa import options

def edf_test():

    options.init_pycpa()

    # generate an new system
    s = model.System()

    # add two resources (CPUs) to the system
    # and register the static priority preemptive scheduler
    r1 = s.bind_resource(model.Resource("R1", schedulers.EDFPScheduler()))
    #r2 = s.bind_resource(model.Resource("R2", edf.EDFPScheduler()))

    # create and bind tasks to r1
    t1 = r1.bind_task(model.Task("T1", wcet=1, bcet=1, deadline=4))
    t2 = r1.bind_task(model.Task("T2", wcet=2, bcet=1, deadline=9))
    t3 = r1.bind_task(model.Task("T3", wcet=2, bcet=1, deadline=6))
    t4 = r1.bind_task(model.Task("T4", wcet=2, bcet=1, deadline=12))

    # create and bind tasks to r2
    #t21 = r2.bind_task(model.Task("T21", wcet=2, bcet=2, deadline=7))
    #t22 = r2.bind_task(model.Task("T22", wcet=9, bcet=4, deadline=18))

    # specify precedence constraints: T11 -> T21; T12-> T22
    #t11.link_dependent_task(t21)
    #t12.link_dependent_task(t22)

    # register a periodic with jitter event model for T11 and T12
    t1.in_event_model = model.EventModel(P=4, J=0)
    t2.in_event_model = model.EventModel(P=6, J=0)
    t3.in_event_model = model.EventModel(P=8, J=0)
    t4.in_event_model = model.EventModel(P=16, J=0)

    # plot the system graph to visualize the architecture
    g = graph.graph_system(s, 'edf_graph.pdf')

    # perform the analysis
    print("Performing analysis")
    #task_results = dict()
    #task_results[t3] = analysis.TaskResult()
    #analysis.analyze_task(t3, task_results)
    task_results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print("%s: wcrt=%d" % (t.name, task_results[t].wcrt))


if __name__ == "__main__":
    edf_test()

