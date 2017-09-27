"""
| Copyright (C) 2017 Johannes Schlatow
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Johannes Schlatow

Description
-----------

Simple end to end analysis
"""


from pycpa import model
from pycpa import schedulers
from pycpa import analysis
from pycpa import path_analysis
from pycpa import options
from pycpa import graph

def effect_chain_test():
    options.init_pycpa()

    # generate an new system
    s = model.System()

    # add a resource to the system
    # register round robin scheduler
    r1 = s.bind_resource(model.Resource("R1", schedulers.SPPSchedulerActivationOffsets()))

    # map two tasks to
    t11 = r1.bind_task(model.Task("T11", wcet=1, bcet=1, scheduling_parameter=1))
    t12 = r1.bind_task(model.Task("T12", wcet=2, bcet=1, scheduling_parameter=2))
    t13 = r1.bind_task(model.Task("T13", wcet=2, bcet=1, scheduling_parameter=3))

    t11.in_event_model = model.PJdEventModel(P=20, J=2, phi=3)
    t12.in_event_model = model.PJdEventModel(P=40, J=2, phi=5)
    t13.in_event_model = model.PJdEventModel(P=10, J=2, phi=1)

    chain = model.EffectChain("C1", [t11, t12, t13])

    # perform a system analysis
    print("analyzing")
    task_results = analysis.analyze_system(s)

    # calculate the latency for the first 10 events
    data_age = path_analysis.cause_effect_chain_data_age(chain, task_results)
    print("chain C1 data age. worst case: %d" % (data_age))

if __name__ == "__main__":
    effect_chain_test()
