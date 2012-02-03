"""
| Copyright (C) 2010 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

Simple end to end analysis
"""


from pycpa import model
from pycpa import analysis
from pycpa import roundrobin
from pycpa import options


def e2e_test():
    # initialyze pycpa. (e.g. read command line switches and set up default options)
    options.init_pycpa()

    # generate an new system
    s = model.System()
    
    # add a resource to the system
    # register round robin scheduler
    r1 = s.add_resource("R1", roundrobin.w_roundrobin)

    # map two tasks to 
    t11 = r1.bind_task(model.Task("T11", wcet = 1, bcet = 1))
    t12 = r1.bind_task(model.Task("T12", wcet = 2, bcet = 1))

    # register precedence constraint
    t11.link_dependent_task(t12)


    t11.in_event_model = model.EventModel(P=4, J=3)

    # register a task chain as a stream
    s1 = s.add_stream("S1", [t11, t12])

    # perform a system analysis
    print("analyzing")
    analysis.analyze_system(s)

    # calculate the latency for the first 10 events
    for n in range(1,11):
        best_case_latency, worst_case_latency = analysis.end_to_end_latency(s1, n)
        print("stream S1 e2e latency. best case: %d, worst case: %d" % (best_case_latency, worst_case_latency ))


if __name__ == "__main__":
    e2e_test()    
