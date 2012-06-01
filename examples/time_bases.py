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

from pycpa import spp
from pycpa import model
from pycpa import analysis
from pycpa import util
from pycpa import options

def time_bases_test(auto=True):
    # print the welcome message
    options.init_pycpa(
                       )
    # generate an new system
    s = model.System()

    # add two resources (CPUs) to the system
    # and register the static priority preemptive scheduler
    r1 = s.bind_resource(model.Resource("R1", spp.SPPScheduler(), frequency=333333333))
    r2 = s.bind_resource(model.Resource("R2", spp.SPPScheduler(), frequency=100000000))

    # get a common time-base
    common_time_base = util.ns

    if auto == True:
        common_time_base = util.calculate_base_time([r.frequency for r in s.resources])

    print "basetime is %d Hz" % common_time_base

    # create and bind tasks to r1. Here the timing is specified in absolute time (i.e. 10 ms)
    t11 = r1.bind_task(model.Task("T11",
                                  wcet=util.time_to_time(10, util.ms, common_time_base, 'ceil'),
                                  bcet=util.time_to_time(5, util.ms, common_time_base, 'floor'),
                                  scheduling_parameter=1))
    t12 = r1.bind_task(model.Task("T12",
                                  wcet=util.time_to_time(3, util.ms, common_time_base, 'ceil'),
                                  bcet=util.time_to_time(1, util.ms, common_time_base, 'floor'),
                                  scheduling_parameter=2))

    # create and bind tasks to r2. Here the timing is specified in cycle time (i.e. 10000 cycles)
    t21 = r2.bind_task(model.Task("T21",
                                  wcet=util.cycles_to_time(200000, r2.frequency, common_time_base, 'ceil'),
                                  bcet=util.cycles_to_time(200000, r2.frequency, common_time_base, 'floor'),
                                  scheduling_parameter=1))
    t22 = r2.bind_task(model.Task("T22",
                                  wcet=util.cycles_to_time(900000, r2.frequency, common_time_base, 'ceil'),
                                  bcet=util.cycles_to_time(400000, r2.frequency, common_time_base, 'floor'),
                                  scheduling_parameter=2))
    print t21.wcet
    print t22.wcet

    # specify precedence constraints: T11 -> T21; T12-> T22
    t11.link_dependent_task(t21)
    t12.link_dependent_task(t22)

    # register a periodic with jitter event model for T11 and T12
    t11.in_event_model = model.EventModel(P=util.time_to_time(30, util.ms, common_time_base, 'floor'),
                                          J=util.time_to_time(5, util.ms, common_time_base, 'ceil'))
    t12.in_event_model = model.EventModel(P=util.time_to_time(15, util.ms, common_time_base, 'floor'),
                                          J=util.time_to_time(6, util.ms, common_time_base, 'ceil'))

    # perform the analysis
    print("Performing analysis")
    task_results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            wcrt_ms = util.time_to_time(task_results[t].wcrt, common_time_base, util.ms, 'ceil')
            print("%s: wcrt=%d ms" % (t.name, wcrt_ms))


if __name__ == "__main__":
    time_bases_test(False)

