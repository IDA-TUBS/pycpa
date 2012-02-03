"""
| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

This module contains methods for real-time scheduling analysis.
It should be imported in scripts that do the analysis.
"""

import logging
import copy
import time
from collections import deque

import model
import options

logger = logging.getLogger("pycpa")


class NotSchedulableException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def _multi_activation_stopping_condition(task, q, w):
    """ Check if we have looked far enough
        compute the time the resource is busy processing q activations of task
        and activations of all other task during that time
        Returns True if stopping-condition is satisfied, False otherwise
    """
    busy_period = q * task.wcet
    for t in task.get_resource_interferers():
        # FIXME: what about my own activations??
        busy_period += t.in_event_model.eta_plus(w) * t.wcet
    # if there are no new activations when the
    # current busy period has been completed, we terminate
    if q >= task.in_event_model.eta_plus(busy_period):
        return True
    return False


def compute_wcrt(task, **kwargs):
    """ Compute the worst-case response time of Task
    Should not be called directly (use System.analyze() instead)
    Uses task.resource.w_function -- a function in the form f(task, q)
    that computes the busy-window of q activations of task
    (depending on the scheduler used)
    """

    if  "MAX_ITERATIONS" not in kwargs:
        kwargs['MAX_ITERATIONS'] = options.opts.max_iterations

    if  "MAX_WINDOW" not in kwargs:
        kwargs['MAX_WINDOW'] = options.opts.max_window

    MAX_ITERATIONS = kwargs['MAX_ITERATIONS']

    if task.resource.compute_wcrt is not None:
        return task.resource.compute_wcrt(task,
                                          MAX_ITERATIONS = MAX_ITERATIONS)

    stop_condition = _multi_activation_stopping_condition
    if task.resource.multi_activation_stopping_condition is not None:
        stop_condition = task.resource.multi_activation_stopping_condition

    # This could possibly be improved by using the previously computed
    #  WCRT and q as a starting point. Is this conservative?
    q = 1
    q_max = 1  # q for which the max wcrt was computed
    wcrt = task.bcet
    task.busy_times = [0]  # busy time of 0 activations
    while True:
        w = task.busy_time(q, **kwargs)
        task.busy_times.append(w)

        current_response = w - task.in_event_model.delta_min(q)
        logger.debug("%s window(q=%f):%f, response: %f" % (task.name, q, w, current_response))
        if current_response > wcrt:
            wcrt = current_response
            q_max = q

        # Check stopcondition
        if stop_condition(task, q, w) == True:
            break

        q += 1
        if q == MAX_ITERATIONS:
            logger.error("MAX_ITERATIONS reached, tasks (likely) not schedulable!")
            #raise NameError("MAX_ITERATIONS reached, tasks (likely) not schedulable!")
            raise NotSchedulableException("MAX_ITERATIONS for %s reached, tasks (likely) not schedulable!" % task.name)
            #return  float("inf")  #-1
    task.q_max = q_max
    logger.debug(task.name + " busy times: " + str(task.busy_times))
    return wcrt


def compute_service(task, t):
    """ Computes the worst-case service a Task receives within
    an interval of t, i.e. how many activations are at least
    computed within t.

    Call System.analyze() first if service depends on other resources
    to make sure all event models are up-to-date!
    This service is higher than the maximum arrival curve
    (requested service) of the task if the task is schedulable.
    """
    if t <= 0:
        return 0
    # infinite service if two events require zero time to process
    if task.resource.w_function(task, 2) <= 0:
        return float("inf")

    # TODO: apply binary search
    n = 1
    while task.resource.w_function(task, n) <= t:
        n += 1
    return n - 1


def compute_max_backlog(task, output_delay = 0):
    """ Compute the maximum backlog of Task t.
        This is the maximum number of outstanding activations.
    """
    t = 1
    TMAX = 300
    max_blog = 0
    while True:
        blog = task.in_event_model.eta_plus(t) - compute_service(task, t - output_delay)
        if blog > max_blog:
            max_blog = blog
        if blog <= 0:
            #print "T=",t
            return max_blog
        t += 1

        if t > TMAX:
            return float("inf")


def analyze_task(task, COMPUTE_BACKLOG = None):
    """ Analyze Task BUT DONT _propagate event model.
    This is the "local analysis step".
    """

    if  "COMPUTE_BACKLOG" is None:
        COMPUTE_BACKLOG = options.opts.backlog

    logger.debug("Analyzing " + task.name +
                  " input: " + str(task.in_event_model))
    logger.debug("eta_plus:  " + str([task.in_event_model.eta_plus(x) for x in range(15)]))
    logger.debug("delta_min: " + str([task.in_event_model.delta_min(x) for x in range(15)]))
    logger.debug("delta_plus: " + str([task.in_event_model.delta_plus(x) for x in range(15)]))
    for t in task.resource.tasks:
        assert(t.in_event_model is not None)

    assert(task.bcet <= task.wcet)
    task.bcrt = task.bcet  # conservative assumption BCRT = BCET

    new_wcrt = compute_wcrt(task)

    task.wcrt = new_wcrt

    if COMPUTE_BACKLOG:
        task.max_backlog = compute_max_backlog(task)
    else:
        task.max_backlog = float("inf")

    logger.debug("%s: bcrt=%g, wcrt=%g" % (task.name, task.bcrt, task.wcrt))
    assert(task.bcrt <= task.wcrt)


def out_event_model(task, dmin = 0):
    """ Wrapper to call the actual out_event_model_XXX. """
    # if there is no valid input model, there is no valid output model
    if task.in_event_model is None:
        return None
    if dmin < task.bcrt:
        # dmin is at least the best-case response time
        dmin = task.bcrt
    return task.resource.out_event_model(task, dmin)


def _out_event_model_jitter_offset(task, dmin = 0):
    """ Derive an output event model including offset from response time jitter
     and in_event_model (used as reference).
    """
    em = copy.copy(task.in_event_model)
    resp_jitter = task.wcrt - task.bcrt

    em.J += resp_jitter
    em.phi += task.bcet
    em.deltamin_func = lambda n: max(task.in_event_model.delta_min(n) - resp_jitter, (n - 1) * dmin)

    # TODO: deltaplus

    em.__description__ = task.in_event_model.__description__ + "+J=" + str(resp_jitter) + ",O=" + str(em.phi)
    return em


def _out_event_model_jitter(task, dmin = 0):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).
    Formula taken from schliecker2009response
    Uses a reference to task.deltamin_func
    """
    em = model.EventModel()
    resp_jitter = task.wcrt - task.bcrt

    assert resp_jitter >= 0
    nonrecursive = True  # if True, a non-recursive (but less accurate) computation is used
    if nonrecursive:
        em.deltamin_func = lambda n: max(task.in_event_model.delta_min(n) - resp_jitter, (n - 1) * dmin)
    else:
        em.deltamin_func = lambda n: \
            n == 2 and max(task.in_event_model.delta_min(2) - resp_jitter, dmin)\
                   or  max(task.in_event_model.delta_min(n) - resp_jitter, em.delta_min(n - 1) + dmin)

    # TODO: check deltaplus
    em.deltaplus_func = lambda n: task.in_event_model.delta_plus(n) + resp_jitter

    em.__description__ = task.in_event_model.__description__ + "+J=" + str(resp_jitter) + ",dmin=" + str(dmin)
    return em


def _out_event_model_busy_window(task, dmin = 0):
    """ Derive an output event model from busy window
     and in_event_model (used as reference).
    Gives better results than _out_event_model_jitter.
    Formula taken from schliecker2008providing
    """
    em = model.EventModel()
    busy_times = task.busy_times  # copy, because task.busy_times changes!
    max_k = len(busy_times)
    min_k = 1  # k \elem N+

    # there was no analysis yet, _propagate input model
    if max_k == 0:
        return copy.copy(task.in_event_model)

    assert max_k > min_k
#        for n in range(2,4):
#            for k in range(min_k,max_k):
#                logger.debug("n=%d, k=%d, busy_time(k)=%d, delta=" %(n,k, busy_times[k])+
#                              str(task.in_event_model.deltamin_func(n+k-1)-busy_times[k]
#                              + task.bcrt)
#                              + ", bcrt="+str(task.bcrt) + " = "
#                              + str(min( [task.in_event_model.deltamin_func(n+k-1) - busy_times[k]
#                      for k in range(min_k,max_k)]) + copy.copy(task.bcrt))
#                              + str([task.in_event_model.deltamin_func(n+k-1) - busy_times[k]
#                      for k in range(min_k,max_k)]))

    em.deltamin_func = lambda n: \
        max((n - 1) * task.bcet,
            min([task.in_event_model.delta_min(n + k - 1) - busy_times[k]
                  for k in range(min_k, max_k)])
            + copy.copy(task.bcrt)
            )

    # delta plus
    em.deltaplus_func = lambda n: \
        max([task.in_event_model.delta_plus(n - k + 1) + busy_times[k]
                  for k in range(min_k, max_k)]) \
            - copy.copy(task.bcrt)

    em.__description__ = task.in_event_model.__description__ + "++"
    return em


def _out_event_model_junction(junction, non_cycle_prev):
    """ calculate the output event model for this junction """
    junction.in_event_models = set()
    for t in non_cycle_prev:
        if out_event_model(t) is not None:
            junction.in_event_models.add(out_event_model(t))

    if len(junction.in_event_models) == 0:
        return None

    em = None
    if junction._mode == 'and':
            em = _out_event_model_junction_and(junction)
    else:
        em = _out_event_model_junction_or(junction)
    return em


def _out_event_model_junction_or(junction):
    raise NotImplementedError("OR not implemented")


def _out_event_model_junction_and(junction):
    assert len(junction.in_event_models) > 0
    em = model.EventModel()
    em.deltamin_func = lambda n: (min(emif.delta_min(n) for emif in junction.in_event_models))
    em.deltaplus_func = lambda n: (max(emif.delta_plus(n) for emif in junction.in_event_models))
    em.__description__ = "AND " + "".join([emif.__description__ for emif in  junction.in_event_models])
    return em


def _invalidate_event_model_caches(task):
    task.invalidate_event_model_cache()
    for t in _breadth_first_search(task):
        t.invalidate_event_model_cache()


def _propagate(task):
    _invalidate_event_model_caches(task)
    for t in task.next_tasks:
        # logger.debug("propagating to " + str(t))
        if isinstance(t, model.Task):
            t.in_event_model = out_event_model(task)
        elif isinstance(t, model.Junction):
            _propagate_junction(t)
        else:
            raise TypeError("invalid propagation target")


def _assert_event_model_conservativeness(emif_small, emif_large, n_max = 1000):
    if emif_small is None:
        return
    for n in range(2, n_max):
        assert emif_large.delta_min(n) <= emif_small.delta_min(n)


def _propagate_junction(junction):
    #cut function cycles
    propagate_tasks = copy.copy(junction.prev_tasks)

    # find potential functional cycles in the app-graph
    # _propagate tasks are all previous input tasks without cycles
    subgraph = _breadth_first_search(junction)
    for prev in junction.prev_tasks:
        if prev in subgraph:
            propagate_tasks.remove(prev)

    if len(propagate_tasks) == 0:
        raise NotSchedulableException("AND Junction %s consists only of a functional cycle without further stimulus" % junction)

    # check if we can reuse the existing output event model
    for t in propagate_tasks:
        if out_event_model(t) not in junction.in_event_models:
            new_output_event_model = _out_event_model_junction(junction, propagate_tasks)
            #_assert_event_model_conservativeness(junction.out_event_model, new_output_event_model)
            junction.out_event_model = new_output_event_model
            break

    for t in junction.next_tasks:
        t.in_event_model = junction.out_event_model


def _event_arrival(task, n, e_0):
    """ Returns the latest arrival time of the n-th event
    with respect to an event 0
    (cf. [schliecker2010recursive], Lemma 1)
    """

    if n > 0:
        e = e_0 + task.in_event_model.delta_plus(n + 1)
    elif n < 0:
        e = e_0 - task.in_event_model.delta_min(-n + 1)
    else:
        e = 0   # same event, so the difference is 0

    return e


def _event_exit(task, n, e_0):
    """ Returns the latest exit time of the n-th event
    relative to the arrival of an event 0
    (cf. [schliecker2010recursive], Lemma 2)
    """
    e = 0

    k_max = task.prev_task.in_event_model.delta_min(task.wcrt)
    print("k_max:", k_max)
    for k in range(k_max + 1):
        print("k:", k)
        e_k = task.event_arrival(n - k, e_0) + task.busy_time(k + 1)
        if e_k > e:
            e = e_k

    return e

def end_to_end_latency(stream, n = 1):
    """ Computes the worst-/best-case e2e latency for n tokens to pass the stream.
    Arguments: 
    stream: a task chain
    n: amount of tokens
    """
    if options.opts.e2e_improved == True:
        return end_to_end_latency_improved(stream, n)
    return end_to_end_latency_classic(stream, n)

def end_to_end_latency_classic(stream, n = 1, task_overhead = 0, stream_overhead = 0, reanalyzeTasks = True):
    """ Computes the worst-/best-case e2e latency
    Assumes that all tasks in the system have successfully been analyzed.
    Assumes that events enter the stream at maximum rate.
    The end-to-end latency is the sum of the individual task's worst-case response times
    A constant task_overhead is added once per task to both min and max latency
    A constant stream_overhead is added once per stream to both min and max latency
    """

    lmax = 0
    for t in stream.tasks:
        if reanalyzeTasks:
            analyze_task(t)
        if isinstance(t, model.Task):
            lmax += t.wcrt + task_overhead

    # add the latest possible release of event n
    lmax += stream.tasks[0].in_event_model.delta_min(n) + stream_overhead

    lmin = 0
    for t in stream.tasks:
        if isinstance(t, model.Task):
            lmin += t.bcrt + task_overhead

    # add the earliest possible release of event n
    lmin += stream.tasks[0].in_event_model.delta_min(n) + stream_overhead

    return lmin, lmax


def _event_arrival_stream(stream, n, e_0 = 0):
    """ Returns the latest arrival time of the n-th event
    with respect to an event 0 of task 0 (first task in stream)

    $e_0(n)$ (cf. [schliecker2009recursive], Lemma 1)
    """
    #if e_0 is None:
        # the entry time of the first event

    if n > 0:
        e = e_0 + stream.tasks[0].in_event_model.delta_plus(n + 1)
    elif n < 0:
        e = e_0 - stream.tasks[0].in_event_model.delta_min(-n + 1)
    else:
        e = 0   # same event, so the difference is 0

    return e


def _event_exit_stream(stream, i, n):
    """ Returns the latest exit time of the n-th event
    relative to the arrival of an event 0
    (cf. [schliecker2009recursive], Lemma 2)
    """

    logger.debug("calculating exit for task %d, n=%d" % (i, n))

    if i == -1:
        # Task -1 is the input event model of task 0,
        # so compute the arrival of n events at task 0
        e = _event_arrival_stream(stream, n)
    else:
        e = float('-inf')
        k_max = len(stream.tasks[i - 1].busy_times)
        #print("k_max:",k_max)
        for k in range(k_max + 1):
            e_k = _event_exit_stream(stream, i - 1, n - k) + stream.tasks[i].busy_time(k + 1)

            logger.debug("busy time for t%d (%d):%d" % (i, k + 1, stream.tasks[i].busy_time(k + 1)))
            #print("e_k:",e_k)
            if e_k > e:
                logger.debug("task %d, n=%d k=%d, new e=%d" % (i, n, k, e_k))
                e = e_k

    logger.debug("exit for task %d, n=%d is %d" % (i, n, e))
    return e


def end_to_end_latency_improved(stream, n = 1):
    """ Performs the path analysis presented in [schliecker2009recursive],
    which improves results compared to end_to_end_latency() for
    n>1 and bursty event models.
    lat(n)
    FIXME: Currently broken
    """

    lat = _event_exit_stream(stream, len(stream.tasks) - 1, n - 1) - 0

    return 0, lat


class AnalysisContext(object):
    """ Everything that is persistent during one analysis run is stored here.
    At the moment this is only the list of dirty tasks.
    Half the anlysis context is stored in the Task class itself!
    """
    def __init__(self, name = "global default"):
        ## Set of tasks requiring another local analysis due to updated input events
        self.dirtyTasks = set()
        ## Dictionary storing the dependent task sets of each task
        self.dependentTask = {}
        ## List of tasks sorted in the order in which the should be analyzed
        self.analysisOrder = []
        ## set of junctions used during depdency detection in order to avoid infinite recursions
        self.mark_junctions = set()

    def clean(self):
        """ Clear all intermediate analysis data """
        for t in self.dirtyTasks:
            t.clean()


def _mark_all_dirty(system, context):
    """ initialize analysis """
    #mark all tasks dirty
    for r in system.resources:
        for t in r.tasks:
            context.dirtyTasks.add(t)
            context.dependentTask[t] = set()


def _mark_dirty(task, context):
    """ add task and its dependencies to the dirty set """
    if isinstance(task, model.Task):  # skip junctions
        context.dirtyTasks.add(task)
        for t in task.get_resource_interferers():  # also mark all tasks on the same resource
            context.dirtyTasks.add(t)
        for t in task.get_mutex_interferers():  # also mark all tasks on the same shared resource
            context.dirtyTasks.add(t)

    for t in task.next_tasks:
        _mark_dirty(t, context)  # recursively mark all dependent tasks dirty


def _mark_dependents_dirty(task, context):
    """ add all dependencies of task to the dirty set """
    context.dirtyTasks |= context.dependentTask[task]


def _init_dependent_tasks(system, context):
    """ Initialize context.dependentTask """

    for r in system.resources:
        for task in r.tasks:
            # also mark all tasks on the same resource
            context.dependentTask[task] |= set(task.get_resource_interferers())
            # also mark all tasks on the same shared resource
            context.dependentTask[task] |= set(task.get_mutex_interferers())

    for r in system.resources:
        for task in r.tasks:
            for t in _breadth_first_search(task):
                if isinstance(t, model.Task):
                    context.dependentTask[task].add(t)
                    context.dependentTask[task] |= context.dependentTask[t]

    #for t in context.dependentTask.keys():
    #    print t, ":", context.dependentTask[t]


def _breadth_first_search(task, func = None):
    """ returns a set of nodes (tasks) which is reachable starting from the starting task.
    calls func on the first discover of a task
    """
    marked = set()
    queue = deque()

    queue.append(task)
    marked.add(task)

    if func is not None:
        func(task)

    while len(queue) > 0:
        v = queue.popleft()
        for e in v.next_tasks:
            if e not in marked:
                if func is not None:
                    func(task)
                marked.add(e)
                queue.append(e)
    return marked


def _generate_distance_map(system):
    """ Precomputes a distance-map for all tasks in the system.
    """
    dist = dict()
    for r in system.resources:
        for t in r.tasks:
            dist[t] = _dijkstra(t)
    return dist


def _dijkstra(source):
    """ Calculates a distance-map from the source node based on the dijkstra algorithm
    The edge weight is 1 for all linked tasks
    """
    dist = dict()
    previous = dict()

    # since we don't have a global view on the graph, we aquire a set of all nodes using BFS
    nodes = _breadth_first_search(source)

    for v in nodes:
        dist[v] = float('inf')
        previous[v] = None

    # init source
    dist[source] = 0

    # working set of nodes to revisit
    Q = nodes.copy()

    while len(Q) > 0:
        # get node with minimum distance
        u = min(Q, key = lambda x: dist[x])

        if dist[u] == float('inf'):
            break  # all remaining vertices are inaccessible from source

        Q.remove(u)

        for v in u.next_tasks:  # where v has not yet been removed from Q.
            alt = dist[u] + 1
            if alt < dist[v]:
                dist[v] = alt
                previous[v] = u
                Q.add(v)
    return dist


def print_subgraphs(system):
    """ enumerate all subgraphs of the application graph.
    if a subgraph is not well-formed (e.g. a source is missing), this algorithm may
    not work correctly (it will eventually produce to many subgraphs)"""
    subgraphs = list()
    unreachable = set()

    for resource in system.resources:
        unreachable |= set(resource.tasks)

    while len(unreachable) > 0:
        # pick one random start task (in case the app graph is not well-formed)
        root_task = iter(unreachable).next()
        # but prefere a task with a source attached
        for t in unreachable:
            if t.in_event_model is not None:
                root_task = t
                break

        reachable = _breadth_first_search(root_task)
        subgraphs.append(reachable)
        unreachable = unreachable - reachable

    logger.info("Application graph consists of %d disjoint subgraphs:" % len(subgraphs))

    idx = 0
    for subgraph in subgraphs:
        logger.info("Subgraph %d" % idx)
        idx += 1
        for task in subgraph:
            logger.info("\t%s" % task)

    return subgraphs


def init_analysis(system, context, clean = False):
    """ Initialize the analysis """

    _mark_all_dirty(system, context)

    _init_dependent_tasks(system, context)

    # analyze tasks with most dependencies first
    context.analysisOrder = context.dependentTask.keys()
    context.analysisOrder.sort(key = lambda x: len(context.dependentTask[x]), reverse = True)

#    print "analysis order:"
#    for x in context.analysisOrder:
#        print x.name, len(context.dependentTask[x])
#        for dt in context.dependentTask[x]:
#            print "  ", dt.name

    if clean:
        for t in context.dirtyTasks:
            t.clean()

    uninizialized = deque(context.dirtyTasks)
    while len(uninizialized) > 0:
        # if there in no task with an valid event event model, then the app-graph is
        # underspecified.
        appgraph_well_formed = False
        for t in uninizialized:
            if t.in_event_model is not None:
                appgraph_well_formed = True
                break

        if appgraph_well_formed == False:
            raise NotSchedulableException("Appgraph not well-formed. Dangling tasks: %s" % uninizialized)

        t = uninizialized.popleft()
        if t.in_event_model is not None:
            _propagate(t)
        else:
            uninizialized.append(t)

    for r in system.resources:
        if r.load() > 1.0:
            logger.warning("load on %s exceeds 1.0" % r.name)
            logger.warning("tasks: %s" % ([(x.name, x.wcet, x.in_event_model.delta_min(11) / 10) for x in r.tasks]))
            raise NotSchedulableException("load on %s exceeds 1.0" % r.name)


def analyze_system(system, clean = False, onlyDependent = False):
    """ Analyze all tasks until we find a fixed point

        system -- the system to analyze
        clean -- if true, all intermediate analysis results (from previous analysis) are cleaned
    """

    context = AnalysisContext()

    init_analysis(system, context, clean)

    iteration = 0
    while len(context.dirtyTasks) > 0:
        for t in context.analysisOrder:
            if t not in context.dirtyTasks:
                continue
            start = time.clock()

            #print len(context.dirtyTasks), "analyzing", t.name, len(t.get_resource_interferers()), "interferers", len(context.dependentTask[t]), "dependent"
            #print "interferers:", [x.name for x in t.get_resource_interferers()]

            context.dirtyTasks.remove(t)

            if onlyDependent and len(context.dependentTask[t]) == 0:
                continue  # skip analysis of tasks w/o dependents

            old_jitter = t.wcrt - t.bcrt
            old_busytimes = copy.copy(t.busy_times)
            analyze_task(t)
            new_jitter = t.wcrt - t.bcrt
            new_busytimes = t.busy_times

    #        assert(old_t.resource == t.resource)
    #        assert(old_t.priority == t.priority)
    #        assert(old_t.resource.idleSlope[old_t.priority] == t.resource.idleSlope[t.priority])

            if new_jitter != old_jitter or old_busytimes != new_busytimes:
                # If jitter has changed, the input event models of all
                # dependent task(s) have also changed,
                # including their dependent tasks and so forth...
                # so mark them and all other tasks on their resource for another analysis

                logger.info("Propagating output of %s to %d dependent tasks. busy_times=%s" %
                            (t.name, len(context.dependentTask[t]), t.busy_times))

                _propagate(t)  # TODO: This could go into mark_dirty...

                _mark_dependents_dirty(t, context)  # mark all dependencies dirty
                #_mark_all_dirty(system, context) # this is always conservative
                break  # break the for loop to restart iteration
            else:
                #print "Jitter: %g->%g" % (old_jitter, new_jitter)
                #print "Busy times \n%s -> \n%s" % (old_busytimes, new_busytimes)
                #print "Fixed Point at task %s:\n%s\n%s" % (t, old_t.busy_times, t.busy_times)
                pass

            elapsed = (time.clock() - start)
            logger.info("iteration: %d, time: %.1f task: %s wcrt: %f dirty: %d" % (iteration, elapsed, t.name, t.wcrt, len(context.dirtyTasks)))
            iteration += 1

    #print "Global iteration done after %d iterations" % (round)
