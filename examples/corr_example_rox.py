"""
:Authors:
         - Marc Boyer
         - Johannes Schlatow

Description
-----------

Implementation of the example given in
   "Exploiting Inter-Event Stream Correlations Between Output Event
    Streams of non-Preemptively Scheduled Tasks", Jonas Rox and Rolf
    Ernst
    http://dl.acm.org/citation.cfm?id=1870980

Made of one CAN bus and one CPU.
"""


from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import graph
from pycpa import options
from pycpa import plot
from pycpa import propagation

try:
    import matplotlib
    matplotlib.use('Agg')
except ImportError:
    print("matplotlib not available")
    exit(0)


def DATE_2010(scheduler_inst, slow=False):

    bcet_factor = 1
    if slow:
        bcet_factor = 2

    # generate an new system
    s = model.System()
    can = s.bind_resource(model.Resource("CAN-Bus", schedulers.SPNPScheduler()))
    m1 = can.bind_task(model.Task("M1", wcet=976, bcet=bcet_factor*400, scheduling_parameter=1,
        OutEventModelClass=propagation.SPNPBusyWindowPropagationEventModel))
    m1.in_event_model = model.PJdEventModel(P=15000, J=0)

    m2 = can.bind_task(model.Task("M2", wcet=736, bcet=bcet_factor*304, scheduling_parameter=2,
        OutEventModelClass=propagation.SPNPBusyWindowPropagationEventModel))
    m2.in_event_model = model.PJdEventModel(P=30000, J=0)

    m3 = can.bind_task(model.Task("M3", wcet=1056, bcet=bcet_factor*432, scheduling_parameter=3,
        OutEventModelClass=propagation.SPNPBusyWindowPropagationEventModel))
    m3.in_event_model = model.PJdEventModel(P=75000, J=0)

    m4 = can.bind_task(model.Task("M4", wcet=1056, bcet=bcet_factor*432, scheduling_parameter=4,
        OutEventModelClass=propagation.SPNPBusyWindowPropagationEventModel))
    m4.in_event_model = model.PJdEventModel(P=40000, J=0)

    m5 = can.bind_task(model.Task("M5", wcet=736, bcet=bcet_factor*304, scheduling_parameter=5,
        OutEventModelClass=propagation.SPNPBusyWindowPropagationEventModel))
    m5.in_event_model = model.PJdEventModel(P=15000, J=0)


    cpu = s.bind_resource(model.Resource("CPU1", scheduler_inst))
    T1 = cpu.bind_task(model.Task("T1", wcet=800, bcet=800, scheduling_parameter=1))
    T2 = cpu.bind_task(model.Task("T2", wcet=350, bcet=350, scheduling_parameter=2))
    T3 = cpu.bind_task(model.Task("T3", wcet=150, bcet=150, scheduling_parameter=3))
    T4 = cpu.bind_task(model.Task("T4", wcet=400, bcet=400, scheduling_parameter=4))
    T5 = cpu.bind_task(model.Task("T5", wcet=1000, bcet=1000, scheduling_parameter=5))

    m1.link_dependent_task(T1)
    m2.link_dependent_task(T2)
    m3.link_dependent_task(T3)
    m4.link_dependent_task(T4)
    m5.link_dependent_task(T5)

    
    # plot the system graph to visualize the architecture
    g = graph.graph_system(s, 'DATE_2010.pdf')

    # perform the analysis
    print("Performing analysis")
    task_results = analysis.analyze_system(s)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print("%s: wcrt=%5.3f" % (t.name, task_results[t].wcrt))
            print("    b_wcrt=%s" % (task_results[t].b_wcrt_str()))
            


if __name__ == "__main__":
    # init pycpa and trigger command line parsing
    options.init_pycpa()

    print("\n------------------------------")
    print("Approx. results, slow bus")
    print("------------------------------\n")
    DATE_2010(schedulers.SPPSchedulerCorrelatedRox(), slow = True)

    print("\n------------------------------")
    print("Exact results, slow bus")
    print("------------------------------\n")
    DATE_2010(schedulers.SPPSchedulerCorrelatedRoxExact(), slow = True)

    print("\n------------------------------")
    print("Approx. results, fast bus")
    print("------------------------------\n")
    DATE_2010(schedulers.SPPSchedulerCorrelatedRox())

    print("\n------------------------------")
    print("Exact results, fast bus")
    print("------------------------------\n")
    DATE_2010(schedulers.SPPSchedulerCorrelatedRoxExact())
