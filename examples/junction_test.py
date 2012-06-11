"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Simple and-junction analysis
"""


from pycpa import model
from pycpa import analysis
from pycpa import graph
from pycpa import schedulers

def junction_test():
    # generate an new system
    s = model.System()

    # add two resources to the system
    # register two schedulers
    r1 = s.bind_resource(model.Resource("R1", schedulers.SPPScheduler()))
    r2 = s.bind_resource(model.Resource("R2", schedulers.SPPScheduler()))

    # add a task
    t11 = r1.bind_task(model.Task(name="T11", wcet=3, bcet=1, scheduling_parameter=1))
    # register input event model
    t11.in_event_model = model.EventModel(P=30, J=15)

    # add three more tasks, these will be triggered by other tasks
    t12 = r1.bind_task(model.Task(name="T12", wcet=3, bcet=2, scheduling_parameter=2))
    t21 = r2.bind_task(model.Task(name="T21", wcet=4, bcet=2, scheduling_parameter=1))
    t22 = r2.bind_task(model.Task(name="T22", wcet=6, bcet=4, scheduling_parameter=2))

    # add a junction (this is an AND junction by default)
    j1 = s.bind_junction(model.Junction())

    # define the precedence contraints, e.g. t21 AND t22 activate j1, j1 then activates t12
    t11.link_dependent_task(t21)
    t11.link_dependent_task(t22)

    t21.link_dependent_task(j1)
    t22.link_dependent_task(j1)

    j1.link_dependent_task(t12)

    # graph the system
    graph.graph_system(s, "junction_example.pdf")

    # analyze the system
    print("Performing analysis")
    results = analysis.analyze_system(s)


    # print the results
    print("Result:")
    for r in sorted(s.resources, key=str):
        print "load on resource %s: %0.2f" % (r.name, r.load())
        for t in sorted(r.tasks, key=str):
            print "  task %s - wcrt: %d" % (t.name, results[t].wcrt)

if __name__ == "__main__":
    junction_test()
