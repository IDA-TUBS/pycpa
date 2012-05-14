"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------
Offset example
The taskset resembles the experiment in Palencia,Harbour 2002.
"""

from pycpa import *
from pycpa import spp_offset
from pycpa import options
from pycpa import graph



def offset_test():

    if options.get_opt('propagation') != "jitter_offset":
        print "propagation is forced to jitter_offset"
        options.set_opt('propagation', "jitter_offset")


    s = model.System()

    cpu1 = s.bind_resource(model.Resource("CPU1", spp_offset.SPPOffsetScheduler()))
    cpu2 = s.bind_resource(model.Resource("CPU2", spp_offset.SPPOffsetScheduler()))
    bus = s.bind_resource(model.Resource("BUS", spp_offset.SPPOffsetScheduler()))

    t11 = cpu1.bind_task(model.Task(name="T11", wcet=4, bcet=4))
    t11.scheduling_parameter = 1

    t21 = cpu1.bind_task(model.Task(name="T21", wcet=20, bcet=20))
    t21.scheduling_parameter = 3

    t22 = bus.bind_task(model.Task(name="T22", wcet=25, bcet=25))
    t22.scheduling_parameter = 1

    t23 = cpu2.bind_task(model.Task(name="T23", wcet=15, bcet=15))
    t23.scheduling_parameter = 2

    t24 = bus.bind_task(model.Task(name="T24", wcet=34, bcet=34))
    t24.scheduling_parameter = 1

    t25 = cpu1.bind_task(model.Task(name="T25", wcet=30, bcet=30))
    t25.scheduling_parameter = 3

    t31 = cpu2.bind_task(model.Task(name="T31", wcet=5, bcet=5))
    t31.scheduling_parameter = 1

    t51 = cpu2.bind_task(model.Task(name="T51", wcet=100, bcet=100))
    t51.scheduling_parameter = 3

    t11.in_event_model = model.EventModel()
    t11.in_event_model.set_PJd(20, 0, 0)

    t21.in_event_model = model.EventModel()
    t21.in_event_model.set_PJd(150, 0, 0)

    t31.in_event_model = model.EventModel()
    t31.in_event_model.set_PJd(30, 0, 0)

    t51.in_event_model = model.EventModel()
    t51.in_event_model.set_PJd(200, 0, 0)

    s1 = s.bind_path(model.Path("S1", (t21, t22, t23, t24, t25)))

    graph.graph_system(s, exec_times=True, show=options.get_opt('show'))

    for r in s.resources:
        for t in r.tasks:
            if not t.path:
                autostream = s.bind_path(model.Path("auto_" + t.name, [t]))


    print("Performing analysis")
    results = analysis.analyze_system(s)

    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print str(t), "-", results[t].wcrt


if __name__ == "__main__":

    offset_test()
