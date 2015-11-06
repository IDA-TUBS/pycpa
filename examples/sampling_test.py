"""
| Copyright (C) 2015 Johannes Schlatow
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Johannes Schlatow

Description
-----------

Path analysis with time triggered asynchronous sampling (automatically includes sampling delay in
path analysis.
"""


from pycpa import model
from pycpa import analysis
from pycpa import graph
from pycpa import schedulers
from pycpa import options
from pycpa import junctions
from pycpa import path_analysis

def sampling_test(wclat_results):

    options.init_pycpa()

    # generate an new system
    s = model.System()

    # add two resources to the system
    # register two schedulers
    r1 = s.bind_resource(model.Resource("R1", schedulers.SPPScheduler()))

    # add a task
    t11 = r1.bind_task(model.Task(name="T11", wcet=3, bcet=1, scheduling_parameter=1))
    # register input event model
    t11.in_event_model = model.PJdEventModel(P=30, J=15)

    # add three more tasks, these will be triggered by other tasks
    t12 = r1.bind_task(model.Task(name="T12", wcet=3, bcet=2, scheduling_parameter=2))

    # add a sampling junction
    j1 = s.bind_junction(model.Junction(name="J1", strategy=junctions.SampledInput()))
    j1.strategy.set_trigger_event_model(model.PJdEventModel(P=50, J=0))

    # register a task chain as a stream: t11->j1->t12
    s1 = s.bind_path(model.Path("S1", [t11, j1, t12]))

    # graph the system
    graph.graph_system(s, "sampling_example.pdf")

    # analyze the system
    print("Performing analysis")
    results = analysis.analyze_system(s)

    # print the results
    print("Result:")
    for r in sorted(s.resources, key=str):
        print "load on resource %s: %0.2f" % (r.name, r.load())
        for t in sorted(r.tasks, key=str):
            print "  task %s - wcrt: %d" % (t.name, results[t].wcrt)

    # calculate the latency for the first 10 events
    for n in range(1, 11):
        best_case_latency, worst_case_latency = path_analysis.end_to_end_latency(s1, results, n)
        print("stream S1 e2e latency. best case: %d, worst case: %d" % (best_case_latency, worst_case_latency))
        assert(worst_case_latency == wclat_results[n-1])

if __name__ == "__main__":
    wclat_results = [59, 74, 104, 134, 164, 194, 224, 254, 284, 314]
    sampling_test(wclat_results)
