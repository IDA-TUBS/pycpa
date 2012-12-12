"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

This example shows how to constraint a system
"""

from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import options

def constraints_example():

    options.init_pycpa()

    # generate an new system
    s = model.System()

    # add two resources (CPUs) to the system
    # and register the static priority preemptive scheduler
    r1 = s.bind_resource(model.Resource("R1", schedulers.SPPScheduler()))
    r2 = s.bind_resource(model.Resource("R2", schedulers.SPPScheduler()))

    # create and bind tasks to r1
    t11 = r1.bind_task(model.Task("T11", wcet=10, bcet=5, scheduling_parameter=1))
    t12 = r1.bind_task(model.Task("T12", wcet=3, bcet=1, scheduling_parameter=2))

    # create and bind tasks to r2
    t21 = r2.bind_task(model.Task("T21", wcet=2, bcet=2, scheduling_parameter=1))
    t22 = r2.bind_task(model.Task("T22", wcet=9, bcet=4, scheduling_parameter=2))

    # specify precedence constraints: T11 -> T21; T12-> T22
    t11.link_dependent_task(t21)
    t12.link_dependent_task(t22)

    # register a periodic with jitter event model for T11 and T12
    t11.in_event_model = model.EventModel(P=30, J=5)
    t12.in_event_model = model.EventModel(P=15, J=6)

    p1 = model.Path("myPath", [t11, t21])
    s.bind_path(p1)

    #deliberately overconstrain the system
    s.constraints.add_path_constraint(p1, 5, n=2)
    s.constraints.add_wcrt_constraint(t11, 1)
    s.constraints.add_load_constraint(r1, 0.5)
    s.constraints.add_backlog_constraint(t11, 1)

    # perform the analysis
    print("Performing analysis")
    task_results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print("%s: wcrt=%d" % (t.name, task_results[t].wcrt))


if __name__ == "__main__":
    constraints_example()

