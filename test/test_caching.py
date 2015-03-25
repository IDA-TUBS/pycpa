"""
| Copyright (C) 2015 Johannes Schlatow
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Johannes Schlatow

Description
-----------
TODO
"""

from pycpa import model
from pycpa import analysis
from pycpa import path_analysis
from pycpa import schedulers
from pycpa import graph
from pycpa import options
import itertools

def _run_test(scheduler, priorities):
    # generate an new system
    s = model.System()

    # add two resources (CPUs) to the system
    # and register the static priority preemptive scheduler
    r1 = s.bind_resource(model.Resource("R1", scheduler))

    # create and bind tasks to r1
    t11 = r1.bind_task(model.Task("T11", wcet=10, bcet=1, scheduling_parameter=priorities[0]))
    t21 = r1.bind_task(model.Task("T21", wcet=2, bcet=2, scheduling_parameter=priorities[1]))
    t31 = r1.bind_task(model.Task("T31", wcet=4, bcet=2, scheduling_parameter=priorities[2]))

    # specify precedence constraints: T11 -> T21 -> T31
    t11.link_dependent_task(t21)
    t21.link_dependent_task(t31)

    # register a periodic with jitter event model for T11
    t11.in_event_model = model.PJdEventModel(P=20, J=5)

    # perform the analysis
    print("Performing analysis")
    task_results = analysis.analyze_system(s)

    failed = False
    for t in r1.tasks:
        for n in range (1,11):
            if t.in_event_model.delta_min(n) != t.in_event_model.deltamin_func(n):
                failed = True
                print("%s: cached EM of != uncached EM" % (t.name))
                print("delta_min(%d) = %d != %d" % (n, t.in_event_model.delta_min(n), t.in_event_model.deltamin_func(n)))
                print("for priorities = %s" % str(priorities))
                break

    return not failed

def test():
    # init pycpa and trigger command line parsing
    options.init_pycpa()

#    priorities = [2, 1, 6]

    failed = False
    for priorities in itertools.permutations([1,2,3]):
        if not _run_test(schedulers.SPPScheduler(), priorities):
            failed = True

    assert not failed

if __name__ == "__main__":
    test()
