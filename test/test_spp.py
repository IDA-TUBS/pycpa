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

from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import graph


def test_spp():
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
    t11.in_event_model = model.PJdEventModel(P=30, J=5)
    t12.in_event_model = model.PJdEventModel(P=15, J=6)

    # perform the analysis
    task_results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    busy_times_t11 = [0, 10]
    busy_times_t12 = [0, 13, 16]
    busy_times_t21 = [0, 2]
    busy_times_t22 = [0, 11, 20, 31, 40]

    assert task_results[t11].busy_times == busy_times_t11
    assert task_results[t12].busy_times == busy_times_t12
    assert task_results[t21].busy_times == busy_times_t21
    assert task_results[t22].busy_times == busy_times_t22

    assert task_results[t11].wcrt == 10
    assert task_results[t12].wcrt == 13
    assert task_results[t21].wcrt == 2
    assert task_results[t22].wcrt == 19


if __name__ == "__main__":
    test_spp()
