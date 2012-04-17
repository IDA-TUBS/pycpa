""" Generic Compositional Performance Analysis Algorithms

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



def compute_wcrt(task, **kwargs):
    """ Compute the worst-case response time of Task
    For this, we construct busy windows for q=1, 2, ... task activations (see [Lehoczky1990]_)
    and iterate until a stop condition (e.g. resource idle again).
    The response time is then the maximum time difference between
    the arrival and the completion of q events.
    See also Equations 2.3, 2.4, 2.5 in [Richter2005]_.
    Should not be called directly (use System.analyze() instead)
    Uses task.resource.w_function -- a function in the form f(task, q)
    that computes the busy-window of q activations of task
    (depending on the scheduler used).
    """

    if  "MAX_ITERATIONS" not in kwargs:
        kwargs['MAX_ITERATIONS'] = options.opts.max_iterations

    if  "MAX_WINDOW" not in kwargs:
        kwargs['MAX_WINDOW'] = options.opts.max_window

    MAX_ITERATIONS = kwargs['MAX_ITERATIONS']

    if task.resource.compute_wcrt is not None:
        return task.resource.compute_wcrt(task,
                                          MAX_ITERATIONS=MAX_ITERATIONS)

    assert task.resource.multi_activation_stopping_condition is not None

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


def compute_max_backlog(task, output_delay=0):
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


def analyze_task(task, COMPUTE_BACKLOG=None):
    """ Analyze Task BUT DONT propagate event model.
    This is the "local analysis step", see Section 7.1.4 in [Richter2005]_.
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


def out_event_model(task, dmin=0):
    """ Wrapper to call the actual out_event_model_XXX,
    which computes the output event model of a task.
    See Chapter 4 in [Richter2005]_ for an overview.    
    """
    # if there is no valid input model, there is no valid output model
    if task.in_event_model is None:
        return None
    if dmin < task.bcrt:
        # dmin is at least the best-case response time
        dmin = task.bcrt
    return task.resource.out_event_model(task, dmin)


def _out_event_model_jitter_offset(task, dmin=0):
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


def _out_event_model_jitter(task, dmin=0):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).
    
    This corresponds to Equations 1 (non-recursive) and 2 (recursive from [Schliecker2009]_    
    This is equivalent to Equation 5 in [Henia2005]_ or Equation 4.6 in [Richter2005]_.
    
    Uses a reference to task.deltamin_func
    """
    em = model.EventModel()
    resp_jitter = task.wcrt - task.bcrt

    if options.opts.propagation == 'jitter':
        # ignore dmin if propagation is jitter only
        dmin = 0

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


def _out_event_model_busy_window(task, dmin=0):
    """ Derive an output event model from busy window
     and in_event_model (used as reference).
    Gives better results than _out_event_model_jitter.
    
    This results from Theorems 1, 2 and 3 from [Schliecker2008]_.
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
    """ Calculate the output event model for this junction. 
    Actually a wrapper to .._or and .._and."""
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
    """ Compute output event models for an OR junction. 
    This corresponds to Section 4.2, Equations 4.11 and 4.12 in [Jersak2005]_.
    """
    raise NotImplementedError("OR not implemented")


def _out_event_model_junction_and(junction):
    """ Compute output event models for an AND junction.
    This corresponds to Lemma 4.2 in [Jersak2005]_.
    """
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
    """ Propagate the event models for a task.
    """
    _invalidate_event_model_caches(task)
    for t in task.next_tasks:
        # logger.debug("propagating to " + str(t))
        if isinstance(t, model.Task):
            t.in_event_model = out_event_model(task)
        elif isinstance(t, model.Junction):
            _propagate_junction(t)
        else:
            raise TypeError("invalid propagation target")


def _assert_event_model_conservativeness(emif_small, emif_large, n_max=1000):
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


def end_to_end_latency(path, n=1, task_overhead=(0, 0), path_overhead=(0, 0), reanalyzeTasks=True, **kwargs):
    """ Computes the worst-/best-case e2e latency for n tokens to pass the path.    

    :param path: the path
    :type path: model.Path
    :param n:  amount of events
    :type n: integer
    :param task_overhead: A constant task_overhead is added once per task to both min and max latency
    :type task_overhead: tuple (best case overhead, worst-case overhead)
    :param path_overhead:  A constant path_overhead is added once per path to both min and max latency
    :type path_overhead: tuple (best case overhead, worst-case overhead)
    :param reanalyzeTasks: reanalyze tasks (local analysis) before latency is calculated
    :type reanalyzeTasks: bool     
    :rtype: tuple (best-case latency, worst-case latency)
    """

    if options.opts.e2e_improved == True:
        (lmin, lmax) = end_to_end_latency_improved(path, n, **kwargs)
    else:
        (lmin, lmax) = end_to_end_latency_classic(path, n, **kwargs)

    for t in path.tasks:
        if reanalyzeTasks:
            analyze_task(t)

        if isinstance(t, model.Task):
            # add per-task overheads            
            lmin += task_overhead[0]
            lmax += task_overhead[1]

    # add per-path overhead
    lmin += path_overhead[0]
    lmax += path_overhead[1]

    return (lmin, lmax)

def end_to_end_latency_classic(path, n=1, injection_rate='max'):
    """ Computes the worst-/best-case end-to-end latency
    Assumes that all tasks in the system have successfully been analyzed.
    Assumes that events enter the path at maximum/minumum rate.
    The end-to-end latency is the sum of the individual task's worst-case response times.
    
    This corresponds to Definition 7.3 in [Richter2005]_.
    
    :param path: the path
    :type path: model.Path
    :param n:  amount of events
    :type n: integer   
    :param injection_rate: assumed injection rate is maximum or minimum
    :type injection_rate: string 'max' or 'min' 
    :rtype: tuple (best case latency, worst case latency)
    """

    lmax = 0
    lmin = 0
    for t in path.tasks:
        if isinstance(t, model.Task):
            # sum up best- and worst-case response times
            lmax += t.wcrt
            lmin += t.bcrt

    if injection_rate == 'max':
        # add the eastliest possible release of event n
        lmax += path.tasks[0].in_event_model.delta_min(n)

    elif injection_rate == 'min':
        # add the latest possible release of event n
        lmax += path.tasks[0].in_event_model.delta_plus(n)

    # add the earliest possible release of event n
    lmin += path.tasks[0].in_event_model.delta_min(n)

    return lmin, lmax


def _event_arrival_path(path, n, e_0=0):
    """ Returns the latest arrival time of the n-th event
    with respect to an event 0 of task 0 (first task in path)

    This is :math:`e_0(n)` from Lemma 1 in [Schliecker2009recursive]_.
    """
    #if e_0 is None:
        # the entry time of the first event

    if n > 0:
        e = e_0 + path.tasks[0].in_event_model.delta_plus(n + 1)
    elif n < 0:
        e = e_0 - path.tasks[0].in_event_model.delta_min(-n + 1)
    else:
        e = 0   # same event, so the difference is 0

    return e


def _event_exit_path(path, i, n):
    """ Returns the latest exit time of the n-th event
    relative to the arrival of an event 0
    (cf. Lemma 2 in [Schliecker2009recursive]_)
    """

    logger.debug("calculating exit for task %d, n=%d" % (i, n))

    if i == -1:
        # Task -1 is the input event model of task 0,
        # so compute the arrival of n events at task 0
        e = _event_arrival_path(path, n)
    else:
        e = float('-inf')
        k_max = len(path.tasks[i - 1].busy_times)
        #print("k_max:",k_max)
        for k in range(k_max + 1):
            e_k = _event_exit_path(path, i - 1, n - k) + path.tasks[i].busy_time(k + 1)

            logger.debug("busy time for t%d (%d):%d" % (i, k + 1, path.tasks[i].busy_time(k + 1)))
            #print("e_k:",e_k)
            if e_k > e:
                logger.debug("task %d, n=%d k=%d, new e=%d" % (i, n, k, e_k))
                e = e_k

    logger.debug("exit for task %d, n=%d is %d" % (i, n, e))
    return e


def end_to_end_latency_improved(path, n=1):
    """ Performs the path analysis presented in [Schliecker2009recursive]_,
    which improves results compared to end_to_end_latency() for
    n>1 and bursty event models.
    lat(n)
    FIXME: BROKEN
    """
    lmax = 0
    lmin = 0
    lmax = _event_exit_path(path, len(path.tasks) - 1, n - 1) - 0

    for t in path.tasks:
       if isinstance(t, model.Task):
           # sum up best-case response times        
           lmin += t.bcrt

    # add the earliest possible release of event n
    # TODO: Can lmin be improved?
    lmin += path.tasks[0].in_event_model.delta_min(n)

    return lmin, lmax


class AnalysisContext(object):
    """ Everything that is persistent during one analysis run is stored here.
    At the moment this is only the list of dirty tasks.
    Half the anlysis context is stored in the Task class itself!
    """
    def __init__(self, name="global default"):
        ## Set of tasks requiring another local analysis due to updated input events
        self.dirtyTasks = set()
        ## Dictionary storing the set of all tasks that are immediately dependent on each task
        ## (i.e. tasks that require re-analysis if a task's output changes)
        self.dependentTask = {}
        ## List of tasks sorted in the order in which the should be analyzed
        self.analysisOrder = []
        ## set of junctions used during depdency detection in order to avoid infinite recursions
        self.mark_junctions = set()

    def get_dependent_tasks(self, task):
        """ Return all tasks which immediately depend on task.
        """
        return self.dependentTask[task]

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

    # First find out which tasks need to be reanalyzed if the input of a specific task changes
    inputDependentTask = {}
    for r in system.resources:
        for task in r.tasks:
            inputDependentTask[task] = set()
            # all tasks on the same shared resource
            inputDependentTask[task] |= set(task.get_mutex_interferers())
            for t in task.next_tasks:
                if isinstance(t, model.Task): # skip junctions

                    # all directly dependent task
                    inputDependentTask[task].add(t)

                    # all tasks on the same resource as directly dependent tasks (only for tasks, not junctions)    
                    inputDependentTask[task] |= set(t.get_resource_interferers())

    context.dependentTask = inputDependentTask


def _init_analysis_order(context):
    """ Init the ananlysis order, using the number of all potentially tasks that require re-analysis 
     as an indicator as to which task to analyze first
    """

    all_dep_tasks = {}

    #print "building dependencies for %d tasks" % (len(context.dirtyTasks))
    for task in context.dirtyTasks: # go through all tasks
        all_dep_tasks[task] = _breadth_first_search(task, None, context.get_dependent_tasks)
        #print "got %d dependencies for task %s" % (len(all_dep_tasks[task]), task)

    #sort by name first (as secondary key in case the lengths are the same
    all_tasks_by_name = sorted(context.dependentTask.keys(), key = lambda x: x.name)
    context.analysisOrder = sorted(all_tasks_by_name, key = lambda x: len(all_dep_tasks[x]), reverse = True)



def _init_analysis_order_simple(context):
    """ Init the analysis order using only the number of immediately dependent
     tasks as an indicator as to which task to analyze first
    """
    #sort by name first (as secondary key in case the lengths are the same
    all_tasks_by_name = sorted(context.dependentTask.keys(), key = lambda x: x.name)
    context.analysisOrder = sorted(all_tasks_by_name, key = lambda x: len(context.dependentTask[x]), reverse = True)


def get_next_tasks(task):
    return task.next_tasks

def _breadth_first_search(task, func=None, get_reachable_tasks=get_next_tasks):
    """ returns a set of nodes (tasks) which is reachable starting from the starting task.
    calls func on the first discover of a task.
    
    get_reachable_tasks(task) specifies a function which returns all tasks considered immediately reachable for a given task.
    """
    marked = set()
    queue = deque()

    queue.append(task)
    marked.add(task)

    if func is not None:
        func(task)

    while len(queue) > 0:
        v = queue.popleft()
        for e in get_reachable_tasks(v):
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
        u = min(Q, key=lambda x: dist[x])

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


def init_analysis(system, context, clean=False):
    """ Initialize the analysis """

    _mark_all_dirty(system, context)

    _init_dependent_tasks(system, context)

    # analyze tasks with most dependencies first

    # TODO: Improve this:
    #  dependentTasks only contains immediate dependencies, which may have their own dependencies again.
    #  This should be respected in the analysis order, but NOT in the dependentTask,
    #  because that would mark too many tasks dirty after each analysis (which is safe but not efficient).
    _init_analysis_order(context)


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
        logger.info("load on %s: %f" % (r.name, r.load()))
        if r.load() >= 1.0:
            logger.warning("load on %s exceeds 1.0" % r.name)
            logger.warning("tasks: %s" % ([(x.name, x.wcet, x.in_event_model.delta_min(11) / 10) for x in r.tasks]))
            raise NotSchedulableException("load on %s exceeds 1.0" % r.name)


def analyze_system(system, clean=False, onlyDependent=False):
    """ Analyze all tasks until we find a fixed point

        system -- the system to analyze
        clean -- if true, all intermediate analysis results (from previous analysis) are cleaned
        
        This based on the procedure described in Section 7.2 in [Richter2005]_.
    """

    context = AnalysisContext()

    init_analysis(system, context, clean)

    iteration = 0
    logger.debug("analysisOrder: %s" % (context.analysisOrder))
    while len(context.dirtyTasks) > 0:
        logger.info("Analyzing, %d tasks left" %
                            (len(context.dirtyTasks)))

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

                logger.debug("Propagating output of %s to %d dependent tasks. busy_times=%s" %
                            (t.name, len(context.dependentTask[t]), t.busy_times))
                #print "dependents of %s: %s" % (t.name, context.dependentTask[t])

                _propagate(t)

                _mark_dependents_dirty(t, context)  # mark all dependencies dirty
                #_mark_all_dirty(system, context) # this is always conservative
                break  # break the for loop to restart iteration
            else:
                #print "Jitter: %g->%g" % (old_jitter, new_jitter)
                #print "Busy times \n%s -> \n%s" % (old_busytimes, new_busytimes)
                #print "Fixed Point at task %s:\n%s\n%s" % (t, old_t.busy_times, t.busy_times)
                pass

            elapsed = (time.clock() - start)
            logger.debug("iteration: %d, time: %.1f task: %s wcrt: %f dirty: %d" % (iteration, elapsed, t.name, t.wcrt, len(context.dirtyTasks)))
            iteration += 1

    #print "Global iteration done after %d iterations" % (round)


