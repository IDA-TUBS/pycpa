"""
| Copyright (C) 2017 Johannes Schlatow
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Johannes Schlatow

"""

from pycpa import *

def run(s, paths=list(), plot_in=list(), chains=list()):
    # graph the system to visualize the architecture
    g = graph.graph_system(s, filename='%s.pdf' % s.name, dotout='%s.dot' % s.name, show=False, chains=chains)

    # perform the analysis
    print("\nPerforming analysis of system '%s'" % s.name)
    task_results = analysis.analyze_system(s)

    # plot input event models of selected tasks
    for t in plot_in:
        plot.plot_event_model(t.in_event_model, 7, separate_plots=False, file_format='pdf', file_prefix='event-model-%s'
                % t.name, ticks_at_steps=False)

    # print the worst case response times (WCRTs)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks & set(task_results.keys()), key=str):
            print("%s: wcrt=%d" % (t.name, task_results[t].wcrt))
            print("    b_wcrt=%s" % (task_results[t].b_wcrt_str()))

    # perform path analysis of selected paths
    for p in paths:
        best_case_latency, worst_case_latency = path_analysis.end_to_end_latency(p, task_results, n=1)
        print("path %s e2e latency. best case: %d, worst case: %d" % (p.name, best_case_latency, worst_case_latency))

    # perform effect-chain analysis
    for c in chains:
        details = dict()
        data_age = path_analysis.cause_effect_chain_data_age(c, task_results, details)
        print("chain %s data age: %d" % (c.name, data_age))
        print("  %s" % str(details))




def _setup_base_scenario():
    # generate an new system
    s = model.System('step1')

    # add three resources (2 CPUs, 1 Bus) to the system
    # and register the SPP scheduler (and SPNP for the bus)
    r1 = s.bind_resource(model.Resource("CPU1", schedulers.SPPScheduler()))
    r2 = s.bind_resource(model.Resource("BUS",  schedulers.SPNPScheduler()))
    r3 = s.bind_resource(model.Resource("CPU2", schedulers.SPPScheduler()))

    # create and bind tasks to r1
    t11 = r1.bind_task(model.Task("T11", wcet=10, bcet=5, scheduling_parameter=2))
    t12 = r1.bind_task(model.Task("T12", wcet=3, bcet=1, scheduling_parameter=3))

    # create and bind tasks to r2
    t21 = r2.bind_task(model.Task("T21", wcet=2, bcet=2, scheduling_parameter=2))
    t22 = r2.bind_task(model.Task("T22", wcet=9, bcet=5, scheduling_parameter=3))

    # create and bind tasks to r3
    t31 = r3.bind_task(model.Task("T31", wcet=5, bcet=3, scheduling_parameter=3))
    t32 = r3.bind_task(model.Task("T32", wcet=3, bcet=2, scheduling_parameter=2))

    # specify precedence constraints: T11 -> T21 -> T31; T12-> T22 -> T32
    t11.link_dependent_task(t21).link_dependent_task(t31)
    t12.link_dependent_task(t22).link_dependent_task(t32)

    # register a periodic with jitter event model for T11 and T12
    t11.in_event_model = model.PJdEventModel(P=30, J=3)
    t12.in_event_model = model.PJdEventModel(P=15, J=1)

    # specify paths
    p1 = s.bind_path(model.Path("P1", [t11, t21, t31]))
    p2 = s.bind_path(model.Path("P2", [t12, t22, t32]))

    return s, r1, r2, r3, t11, t12, t21, t22, t31, t32, [p1, p2]

def base_scenario():
    s, r1, r2, r3, t11, t12, t21, t22, t31, t32, paths = _setup_base_scenario()
    run(s, paths)

def refined_scenario():
    s, r1, r2, r3, t11, t12, t21, t22, t31, t32, paths = _setup_base_scenario()
    s.name = 'step2'

    # use correlated event stream analysis from [Rox2010]_ on CPU2
    r3.scheduler = schedulers.SPPSchedulerCorrelatedRox()
    for t in r2.tasks:
        t.OutEventModelClass = propagation.SPNPBusyWindowPropagationEventModel

    run(s, paths)

def junction_scenario():
    s, r1, r2, r3, t11, t12, t21, t22, t31, t32, paths = _setup_base_scenario()
    s.name = 'step3'

    class PathJitterForkStrategy(object):

        class PathJitterPropagationEventModel(propagation.JitterPropagationEventModel):
            """ Derive an output event model from an in_event_model of the given task and
                the end-to-end jitter along the given path.
            """
            def __init__(self, task, task_results, path):
                self.task = task
                path_result = path_analysis.end_to_end_latency(path, task_results, 1)
                self.resp_jitter = path_result[1] - path_result[0]
                self.dmin = 0
                self.nonrecursive = True

                name = task.in_event_model.__description__ + "+J=" + \
                    str(self.resp_jitter) + ",dmin=" + str(self.dmin)

                model.EventModel.__init__(self,name,task.in_event_model.container)

                assert self.resp_jitter >= 0, 'response time jitter must be positive'

        def __init__(self):
            self.name = "Fork"

        def output_event_model(self, fork, dst_task, task_results):
            src_task = fork.get_mapping(dst_task)
            p = model.Path(src_task.name + " -> " + fork.name, util.get_path(src_task, fork))
            return PathJitterForkStrategy.PathJitterPropagationEventModel(src_task, task_results, p)

    # remove links between t12, t22 and t32
    t12.next_tasks = set()
    t22.next_tasks = set()

    # add one more task to R1 
    t13 = r1.bind_task(model.Task("T13", wcet=5, bcet=2, scheduling_parameter=4))
    t13.in_event_model = model.PJdEventModel(P=50, J=2)
    # add TX task on R1
    ttx = r1.bind_task(model.Task("TX", wcet=2, bcet=1, scheduling_parameter=1))

    # add OR junction to system
    j1 = s.bind_junction(model.Junction(name="J1", strategy=junctions.ORJoin()))

    # link t12 and t13 to junction
    t12.link_dependent_task(j1)
    t13.link_dependent_task(j1)

    # link junction to tx
    j1.link_dependent_task(ttx)

    # add one more task to R3
    t33 = r3.bind_task(model.Task("T33", wcet=5, bcet=2, scheduling_parameter=4))
    # add RX task (fork) on R3
    trx = r3.bind_task(model.Fork("RX", wcet=2, bcet=1, scheduling_parameter=1,
        strategy=PathJitterForkStrategy()))

    # link rx to t32 and t33
    trx.link_dependent_task(t32)
    trx.link_dependent_task(t33)

    # link tx to t22 to rx
    ttx.link_dependent_task(t22).link_dependent_task(trx)

    # map source and destination tasks (used by fork strategy)
    trx.map_task(t32, t12)
    trx.map_task(t33, t13)

    plot_in = [t12, t32, ttx]
    run(s, plot_in=plot_in)

def effectchain_scenario():
    s, r1, r2, r3, t11, t12, t21, t22, t31, t32, paths = _setup_base_scenario()
    s.name = 'step4'

    r1.name = 'CPU1.1'
    r10 = s.bind_resource(model.Resource("CPU1.0", schedulers.SPPScheduler()))

    t01 = r10.bind_task(model.Task("T01", wcet=5, bcet=2, scheduling_parameter=1))
    t02 =  r1.bind_task(model.Task("T02", wcet=5, bcet=2, scheduling_parameter=4))

    t01.in_event_model = model.PJdEventModel(P=10, phi=0)
    t02.in_event_model = model.PJdEventModel(P=60, phi=6)

    chains = [ model.EffectChain(name='Chain1', tasks=[t01, t02, t11]) ]

    run(s, paths, chains=chains)

def taskchain_scenario():
    try:
        from taskchain import model as tc_model
        from taskchain import schedulers as tc_schedulers
    except ImportError:
        print("taskchain repository not found")
        return

    s = model.System(name='step5')

    # add two resources (CPUs) to the system
    # and register the static priority preemptive scheduler
    r1 = s.bind_resource(tc_model.TaskchainResource("Resource 1", tc_schedulers.SPPSchedulerSync()))
    r2 = s.bind_resource(tc_model.TaskchainResource("Resource 2", tc_schedulers.SPPSchedulerSync()))

    # create and bind tasks to r1
    t11 = r1.bind_task(model.Task("T11", wcet=10, bcet=1, scheduling_parameter=1))
    t12 = r1.bind_task(model.Task("T12", wcet=2, bcet=2, scheduling_parameter=3))
    t13 = r1.bind_task(model.Task("T13", wcet=4, bcet=2, scheduling_parameter=6))

    t31 = r1.bind_task(model.Task("T31", wcet=5, bcet=3, scheduling_parameter=4))
    t32 = r1.bind_task(model.Task("T32", wcet=5, bcet=3, scheduling_parameter=2))

    t21 = r2.bind_task(model.Task("T21", wcet=3, bcet=1, scheduling_parameter=2))
    t22 = r2.bind_task(model.Task("T22", wcet=9, bcet=4, scheduling_parameter=2))

    # specify precedence constraints
    t11.link_dependent_task(t12).link_dependent_task(t13).link_dependent_task(t21).\
            link_dependent_task(t22).link_dependent_task(t31).link_dependent_task(t32)

    # register a periodic with jitter event model for T11
    t11.in_event_model = model.PJdEventModel(P=50, J=5)

    # register task chains
    c1 = r1.bind_taskchain(tc_model.Taskchain("C1", [t11, t12, t13]))
    c2 = r2.bind_taskchain(tc_model.Taskchain("C2", [t21, t22]))
    c3 = r1.bind_taskchain(tc_model.Taskchain("C3", [t31, t32]))

    # register a path
    s1 = s.bind_path(model.Path("S1", [t11, t12, t13, t21, t22, t31, t32]))

    run(s, paths=[s1])

options.parser.add_argument('--steps', type=str, nargs='+', default=['step1', 'step2', 'step3', 'step4', 'step5'])

if __name__ == "__main__":
    # init pycpa and trigger command line parsing
    options.init_pycpa()

    # Step 1
    if 'step1' in options.get_opt('steps'):
        base_scenario()

    # Step 2 (refining the analysis)
    if 'step2' in options.get_opt('steps'):
        refined_scenario()
    
    # Step 3 (junctions and forks)
    if 'step3' in options.get_opt('steps'):
        junction_scenario()

    # Step 4 (cause-effect chains)
    if 'step4' in options.get_opt('steps'):
        effectchain_scenario()

    # Step 5 (complex run-time environments)
    if 'step5' in options.get_opt('steps'):
        taskchain_scenario()
