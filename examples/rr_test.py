"""
| Copyright (C) 2010 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

Round Robin Example
"""


from __future__ import print_function

from pycpa import model
from pycpa import analysis
from pycpa import roundrobin
from pycpa import options


def rr_test():

    s = model.System()
    r1 = s.bind_resource(model.Resource("R1", roundrobin.w_roundrobin, roundrobin.rr_multi_activation_stopping_condition))
    r2 = s.bind_resource(model.Resource("R2", roundrobin.w_roundrobin, roundrobin.rr_multi_activation_stopping_condition))

    # create and bind tasks
    # the scheduling_parameter denotes the slot size
    t11 = r1.bind_task(model.Task(name="T11", wcet=1, bcet=1, scheduling_parameter=1))
    t12 = r1.bind_task(model.Task(name="T12", wcet=1, bcet=1, scheduling_parameter=1))
    t21 = r2.bind_task(model.Task(name="T21", wcet=1, bcet=1, scheduling_parameter=1))
    t22 = r2.bind_task(model.Task(name="T22", wcet=1, bcet=1, scheduling_parameter=1))

    t11.link_dependent_task(t21)
    t22.link_dependent_task(t12)

    t11.in_event_model = model.EventModel(c=2, T=15)
    t22.in_event_model = model.EventModel(c=3, T=17)

    print("Performing analysis")
    results = analysis.analyze_system(s)

    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print(t, " - ", results[t].wcrt)

if __name__ == "__main__":
    rr_test()
