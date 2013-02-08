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

from __future__ import absolute_import

import logging
import copy
import time
from collections import deque

from . import model
from . import options
from . import util
from . import path_analysis

logger = logging.getLogger("pycpa")


class NotSchedulableException(Exception):
    """ Thrown if the system is not schedulable """
    def __init__(self, value):
        super(NotSchedulableException, self).__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)


class TaskResult(object):
    """ This class stores all analysis results for a single task """

    # : Worst-case response time
    wcrt = 0
    # : Best-case response time
    bcrt = 0  # init wcrt, bcrt with 0 so initial response time jitter is 0
    # : List of busy-times
    busy_times = list()
    # : Worst-case activation backlog
    max_backlog = float('inf')
    # : Number of activations q for which the worst-case response-time was found
    q_wcrt = 0
    # : dict containing details on the busy-window of the worst-case response
    # time
    b_wcrt = dict()

    def __init__(self):
        self.clean()

    def clean(self):
        """ Clean up """
        # initialize both wcrt and bcrt with zero to make response time jitter
        # zero initially
        self.wcrt = 0
        self.bcrt = 0
        self.busy_times = list()
        self.max_backlog = float('inf')
        self.q_wcrt = 0

    def b_wcrt_str(self):
        """ Returns a string with the components of b_wcrt
        sorted alphabetically """
        s = ''
        for k in sorted(self.b_wcrt.keys()):
            s += k + ':' + str(self.b_wcrt[k]) + ', '
        return s[:-2]


class Scheduler(object):
    """ This class encapsulates the scheduler-specific analysis """

    def __init__(self):
        pass

    def b_plus(self, task, q, details=None):
        """ Maximum Busy-Time for q activations of a task.

        This default implementation assumes that all other tasks
        disturb the task under consideration,
        which is the behavior of a "random priority preemptive" scheduler
        or a "least-remaining-load-last" scheduler.
        This is a conservative bound for all work-conserving schedulers.

        .. warning::
            This default implementation should be overridden for any scheduler.

        :param task: the analyzed task
        :type task: model.Task
        :param q: the number of activations
        :type q: integer
        :param details: reference to a dict of details on the busy window (instead of busy time)
        :type q: boolean
        :rtype: integer (max. busy-time for q activations)
        """

        w = q * task.wcet
        while True:
            s = 0
            for ti in task.get_resource_interferers():
                s += ti.wcet * ti.in_event_model.eta_plus(w)
            w_new = q * task.wcet + s
            if w == w_new:
                if details is not None:
                    sum_dict = dict()
                    sum_dict['q*WCET'] = q * task.wcet
                    details['q*WCET'] = str(q) + '*' + str(task.wcet)
                    for ti in task.get_resource_interferers():
                        sum_dict[str(ti) + '.eta*WCET'] = \
                            ti.in_event_model.eta_plus(w) * ti.wcet
                        desc_string = str(ti.in_event_model.eta_plus(w))\
                                        + '*' + str(ti.wcet)
                        details[str(ti) + ':eta*WCET'] = desc_string
                        details['sum'] = sum_dict
                return w
            w = w_new

    def b_min(self, task, q):
        """ Minimum Busy-Time for q activations of a task.

        This default implementation should be conservative for all schedulers
        but can be overridden for improving the results with scheduler knowledge.

        :param task: the analyzed task
        :type task: model.Task
        :param q: the number of activations
        :type q: integer
        :rtype: integer (max. busy-time for q activations)
        """

        return q * task.bcet

    def stopping_condition(self, task, q, w):
        """ Return true if a sufficient number of activations q
        have been evaluated for a task during the busy-time w.

        This default implementation continues analysis as long as
        there are new activations of the task within its current busy window.

        .. warning::
            This default implementation works only for certain schedulers (e.g. SPP)
            and must be overridden otherwise.

        :param task: the analyzed task
        :type task: model.Task
        :param q: the number of activations
        :type q: integer
        :param w: the current busy-time
        :type w: integer
        :rtype: integer (max. busy-time for q activations)
        """

        if task.in_event_model.delta_min(q + 1) >= w:
            return True
        return False

    def compute_wcrt(self, task, task_results):
        """ Compute the worst-case response time of Task

        .. warning::
            This default implementation works only for certain schedulers
            and must be overridden otherwise.

        :param task: the analyzed task
        :type task: model.Task
        :param task_results: dictionary which stores analysis results
        :type task_results: dict (analysis.TaskResult)
        :rtype: integer (worst-case response time)

        For this, we construct busy windows for q=1, 2, ... task activations
        (see [Lehoczky1990]_)
        and iterate until a stop condition (e.g. resource idle again).
        The response time is then the maximum time difference between
        the arrival and the completion of q events.
        See also Equations 2.3, 2.4, 2.5 in [Richter2005]_.
        Should not be called directly (use System.analyze() instead).
        """

        max_iterations = options.get_opt('max_iterations')

        # This could possibly be improved by using the previously computed
        #  WCRT and q as a starting point. Is this conservative?
        q = 1
        # q for which the max wcrt was computed
        q_wcrt = 1
        # datatype of task.wcet is not known here
        # (e.g. variable execution times)
        wcrt = 0

        b_wcrt = dict()  # store details of busy window leading to wcrt
        task_results[task].busy_times = [0]  # busy time of 0 activations
        self.b_plus(task, 1, details=b_wcrt)
        while True:
            w = self.b_plus(task, q)
            task_results[task].busy_times.append(w)

            current_response = w - task.in_event_model.delta_min(q)
            # logger.debug("%s window(q=%f):%d, response: %d" % (task.name, q,
            # w, current_response))

            if current_response > wcrt:
                wcrt = current_response
                q_wcrt = q
                self.b_plus(task, q, details=b_wcrt)

            # TODO: this should go in central "constraint checking" function
            if options.get_opt('max_wcrt') < wcrt:
                raise NotSchedulableException("max_wcrt > wcrt of %s, "
                                              "tasks (likely) not schedulable!"
                                              % task.name)

            # Check stopcondition
            if self.stopping_condition(task, q, w) == True:
                break

            q += 1
            if q == max_iterations:
                logger.error(
                    "max_iterations reached, tasks (likely) not schedulable!")
                # raise NameError("max_iterations reached, tasks (likely) not
                # schedulable!")
                raise NotSchedulableException("max_iterations for %s reached, "
                                              "tasks (likely) not schedulable!"
                                              % task.name)
                # return  float("inf")  #-1
        task_results[task].q_wcrt = q_wcrt
        task_results[task].wcrt = wcrt
        task_results[task].b_wcrt = b_wcrt
        # logger.debug(task.name + " busy times: " +
        # str(task_results[task].busy_times))
        return wcrt

    def compute_bcrt(self, task, task_results):
        """ Return the best-case response time for q activations of a task.
        Convenience function which calls the minimum busy-time.
        The bcrt is also stored in task_results.

        """
        bcrt = self.b_min(task, 1)
        task_results[task].bcrt = bcrt
        return bcrt

    def compute_service(self, task, t):
        """ Computes the worst-case service a Task receives within
        an interval of t, i.e. how many activations are at least
        computed within t.

        Call System.analyze() first if service depends on other resources
        to make sure all event models are up-to-date!
        This service is higher than the maximum arrival curve
        (requested service) of the task if the task is schedulable.
        """
        # TODO: do we still need this? Can this be used as an interface with MPA?
        if t <= 0:
            return 0
        # infinite service if two events require zero time to process
        if task.resource.scheduler.b_plus(task, 2) <= 0:
            return float("inf")

        # TODO: apply binary search
        n = 1
        while task.resource.scheduler.b_plus(task, n) <= t:
            n += 1
        return n - 1

    def compute_max_backlog(self, task, task_results, output_delay=0):
        """ Compute the maximum backlog of Task t.
        This is the maximum number of outstanding activations.
        Implemented as shown in Eq.17 of [Diemer2012]_.
        """
        q_max = len(task_results[task].busy_times)
        b = [0] + [task.in_event_model.eta_plus(
            task_results[task].busy_times[q] + output_delay) - q + 1
            for q in range(1, q_max)]
        max_backlog = max(b)
        task_results[task].max_backlog = max_backlog
        return max_backlog


def analyze_task(task, task_results):
    """ Analyze Task BUT DONT propagate event model.
    This is the "local analysis step", see Section 7.1.4 in [Richter2005]_.
    """

    for t in task.resource.tasks:
        assert(t.in_event_model is not None)

    assert(task.bcet <= task.wcet)
    task.resource.scheduler.compute_bcrt(task, task_results)
    task.resource.scheduler.compute_wcrt(task, task_results)
    task.resource.scheduler.compute_max_backlog(task, task_results)

    assert(task_results[task].bcrt <= task_results[task].wcrt)


def out_event_model(task, task_results, dmin=0):
    """ Wrapper to call the actual out_event_model_*,
    which computes the output event model of a task.
    See Chapter 4 in [Richter2005]_ for an overview.
    """
    # if there is no valid input model, there is no valid output model
    if task.in_event_model is None:
        return None
    if dmin < task_results[task].bcrt:
        # dmin is at least the best-case response time
        dmin = task_results[task].bcrt

    method = options.get_opt('propagation')
    if method == 'jitter_offset':
        _out_event_model = _out_event_model_jitter_offset
    elif method == 'busy_window':
        _out_event_model = _out_event_model_busy_window
    elif  method == 'jitter_dmin' or method == 'jitter':
        _out_event_model = _out_event_model_jitter
    else:
        raise NotImplementedError

    return _out_event_model(task, task_results, dmin)


def _out_event_model_jitter_offset(task, task_results, dmin=0):
    """ Derive an output event model including offset from response time jitter
    and in_event_model (used as reference).
    """

    em = copy.copy(task.in_event_model)
    resp_jitter = task_results[task].wcrt - task_results[task].bcrt

    em.J += resp_jitter
    em.phi += task.bcet
    em.deltamin_func = lambda n: max(
        task.in_event_model.delta_min(n) - resp_jitter, (n - 1) * dmin)

    em.deltaplus_func = lambda n: task.in_event_model.delta_plus(
        n) + resp_jitter

    em.__description__ = task.in_event_model.__description__ + "+J=" + \
        str(resp_jitter) + ",O=" + str(em.phi)
    return em


def _out_event_model_jitter(task, task_results, dmin=0):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).

    This corresponds to Equations 1 (non-recursive) and
    2 (recursive from [Schliecker2009]_
    This is equivalent to Equation 5 in [Henia2005]
    or Equation 4.6 in [Richter2005]_.

    Uses a reference to task.deltamin_func
    """
    em = model.EventModel()
    resp_jitter = task_results[task].wcrt - task_results[task].bcrt

    if options.get_opt('propagation') == 'jitter':
        # ignore dmin if propagation is jitter only
        dmin = 0

    assert resp_jitter >= 0

    # if True, a non-recursive (but less accurate) computation is used
    nonrecursive = True
    if nonrecursive:
        em.deltamin_func = lambda n: max(
            task.in_event_model.delta_min(n) - resp_jitter, (n - 1) * dmin)
    else:
        em.deltamin_func = lambda n: \
            n == 2 and max(task.in_event_model.delta_min(2)
                           - resp_jitter, dmin) or max(
                               task.in_event_model.delta_min(n) - resp_jitter,
                               em.delta_min(n - 1) + dmin)

    em.deltaplus_func = lambda n: task.in_event_model.delta_plus(
        n) + resp_jitter

    em.__description__ = task.in_event_model.__description__ + "+J=" + \
        str(resp_jitter) + ",dmin=" + str(dmin)
    return em


def _out_event_model_busy_window(task, task_results, dmin=0):
    """ Derive an output event model from busy window
     and in_event_model (used as reference).
    Gives better results than _out_event_model_jitter.

    This results from Theorems 1, 2 and 3 from [Schliecker2008]_.
    """
    em = model.EventModel()
    # copy, because task.busy_times changes!
    busy_times = task_results[task].busy_times
    max_k = len(busy_times)
    min_k = 1  # k \elem N+

    # there was no analysis yet, _propagate input model
    if max_k == 0:
        return copy.copy(task.in_event_model)

    assert max_k > min_k

    em.deltamin_func = lambda n: \
        max((n - 1) * dmin,
            min([task.in_event_model.delta_min(n + k - 1) - busy_times[k]
                 for k in range(min_k, max_k)])
            + copy.copy(task_results[task].bcrt)
            )

    # delta plus
    em.deltaplus_func = lambda n: \
        max([task.in_event_model.delta_plus(n - k + 1) + busy_times[k]
             for k in range(min_k, max_k)]) \
        - copy.copy(task_results[task].bcrt)

    em.__description__ = task.in_event_model.__description__ + "++"
    return em


def _out_event_model_junction(junction, task_results, non_cycle_prev):
    """ Calculate the output event model for this junction.
    Actually a wrapper to .._or and .._and."""
    junction.in_event_models = set()
    for t in non_cycle_prev:
        if out_event_model(t, task_results) is not None:
            junction.in_event_models.add(out_event_model(t, task_results))

    if len(junction.in_event_models) == 0:
        return None

    em = None
    if junction.mode == 'and':
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
    em.deltamin_func = lambda n: (
        min(emif.delta_min(n) for emif in junction.in_event_models))
    em.deltaplus_func = lambda n: (
        max(emif.delta_plus(n) for emif in junction.in_event_models))
    em.__description__ = "AND " + \
            "".join([emif.__description__
                     for emif in junction.in_event_models])
    return em


def _invalidate_event_model_caches(task):
    """ Invalidate all event model caches """
    task.invalidate_event_model_cache()
    for t in util.breadth_first_search(task):
        t.invalidate_event_model_cache()


def _propagate(task, task_results):
    """ Propagate the event models for a task.
    """
    _invalidate_event_model_caches(task)
    for t in task.next_tasks:
        # logger.debug("propagating to " + str(t))

        if isinstance(t, model.Task):
            # print("propagating to " + str(t) + "l=", out_event_model(task,
            # task_results).load())
            t.in_event_model = out_event_model(task, task_results)
        elif isinstance(t, model.Junction):
            _propagate_junction(t, task_results)
        else:
            raise TypeError("invalid propagation target")


def _assert_event_model_conservativeness(emif_small, emif_large, n_max=1000):
    """ Assert that emif_large is no greater than emif_small """
    if emif_small is None:
        return
    for n in range(2, n_max):
        assert emif_large.delta_min(n) <= emif_small.delta_min(n)


def _propagate_junction(junction, task_results):
    """ Propagate event model over a junction """
    # cut function cycles
    propagate_tasks = copy.copy(junction.prev_tasks)

    # find potential functional cycles in the app-graph
    # _propagate tasks are all previous input tasks without cycles
    subgraph = util.breadth_first_search(junction)
    for prev in junction.prev_tasks:
        if prev in subgraph:
            propagate_tasks.remove(prev)

    if len(propagate_tasks) == 0:
        raise NotSchedulableException("AND Junction %s "
                                      "consists only of a functional"
                                      " cycle without further stimulus"
                                      % junction)

    # check if we can reuse the existing output event model
    for t in propagate_tasks:
        if out_event_model(t, task_results) not in junction.in_event_models:
            new_output_event_model = _out_event_model_junction(
                junction, task_results, propagate_tasks)
            # _assert_event_model_conservativeness(junction.out_event_model,
            # new_output_event_model)
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
        e = 0  # same event, so the difference is 0

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


class GlobalAnalysisState(object):
    """ Everything that is persistent during one analysis run is stored here.
    At the moment this is only the list of dirty tasks.
    Half the anlysis context is stored in the Task class itself!
    """
    def __init__(self, system, task_results):
        """ Initialize the analysis """
        # Set of tasks requiring another local analysis due to updated input
        # events
        self.dirtyTasks = set()
        # Dictionary storing the set of all tasks that are immediately
        # dependent on each task
        # # (i.e. tasks that require re-analysis if a task's output changes)
        self.dependentTask = {}
        # # List of tasks sorted in the order in which the should be analyzed
        self.analysisOrder = []
        # set of junctions used during depdency detection in order to avoid
        # infinite recursions
        self.mark_junctions = set()

        self._mark_all_dirty(system)

        self._init_dependent_tasks(system)

        # analyze tasks with most dependencies first

        # TODO: Improve this:
        # dependentTasks only contains immediate dependencies, which may have
        # their own dependencies again.
        # This should be respected in the analysis order, but NOT in the
        # dependentTask,
        # because that would mark too many tasks dirty after each analysis
        # (which is safe but not efficient).
        self._init_analysis_order()

        uninizialized = deque(self.dirtyTasks)
        while len(uninizialized) > 0:
            # if there in no task with an valid event event model, then the
            # app-graph is
            # underspecified.
            appgraph_well_formed = False
            for t in uninizialized:
                if t.in_event_model is not None:
                    appgraph_well_formed = True
                    break

            if appgraph_well_formed == False:
                raise NotSchedulableException("Appgraph not well-formed."
                                              "Dangling tasks: %s" %
                                              uninizialized)

            t = uninizialized.popleft()
            if t.in_event_model is not None:
                _propagate(t, task_results)
            else:
                uninizialized.append(t)

        for r in system.resources:
            load = r.load()
            logger.info("load on %s: %f" % (r.name, load))
            if load >= 1.0:
                logger.warning(
                    "load too high: load on %s is %f" % (r.name, load))
                # logger.warning("tasks: %s" % ([(x.name, x.wcet,
                # x.in_event_model.delta_min(11) / 10) for x in r.tasks]))
                raise NotSchedulableException("load too high: "
                                              "load on %s exceeds 1.0"
                                              "(load is %f)" % (r.name, load))

    def clean_analysis_state(self):
        """ Clean the analysis state """
        for t in self.dirtyTasks:
            t.clean()

    def get_dependent_tasks(self, task):
        """ Return all tasks which immediately depend on task.
        """
        return self.dependentTask[task]

    def clean(self):
        """ Clear all intermediate analysis data """
        for t in self.dirtyTasks:
            t.clean()

    def _mark_all_dirty(self, system):
        """ initialize analysis """
        # mark all tasks dirty
        for r in system.resources:
            for t in r.tasks:
                self.dirtyTasks.add(t)
                self.dependentTask[t] = set()

    def _mark_dirty(self, task):
        """ add task and its dependencies to the dirty set """
        if isinstance(task, model.Task):  # skip junctions
            self.dirtyTasks.add(task)
            for t in task.get_resource_interferers():
                # also mark all tasks on the same resource
                self.dirtyTasks.add(t)
            for t in task.get_mutex_interferers():
                # also mark all tasks on the same shared resource
                self.dirtyTasks.add(t)

        for t in task.next_tasks:
            self._mark_dirty(t)  # recurse for all dependent tasks

    def _mark_dependents_dirty(self, task):
        """ add all dependencies of task to the dirty set """
        self.dirtyTasks |= self.dependentTask[task]

    def _init_dependent_tasks(self, system):
        """ Initialize dependentTask """

        # First find out which tasks need to be reanalyzed if the input of a
        # specific task changes
        inputDependentTask = {}
        for r in system.resources:
            for task in r.tasks:
                inputDependentTask[task] = set()
                # all tasks on the same shared resource
                inputDependentTask[task] |= set(task.get_mutex_interferers())
                for t in task.next_tasks:
                    if isinstance(t, model.Task):  # skip junctions

                        # all directly dependent task
                        inputDependentTask[task].add(t)

                        # all tasks on the same resource as directly dependent
                        # tasks (only for tasks, not junctions)
                        inputDependentTask[
                            task] |= set(t.get_resource_interferers())

        self.dependentTask = inputDependentTask

    def _init_analysis_order(self):
        """ Init the ananlysis order,
        using the number of all potentially tasks that require re-analysis
        as an indicator as to which task to analyze first
        """

        all_dep_tasks = {}

        # print "building dependencies for %d tasks" % (len(context.dirtyTasks))
        for task in self.dirtyTasks:  # go through all tasks
            all_dep_tasks[task] = util.breadth_first_search(
                task, None, self.get_dependent_tasks)

        # sort by name first (as secondary key in case the lengths are the same
        all_tasks_by_name = sorted(
            self.dependentTask.keys(), key=lambda x: x.name)
        self.analysisOrder = sorted(all_tasks_by_name,
                                    key=lambda x: len(all_dep_tasks[x]),
                                    reverse=True)

    def _init_analysis_order_simple(self):
        """ Init the analysis order using only the number
        of immediately dependent tasks as an indicator
        as to which task to analyze first
        """
        # sort by name first (as secondary key in case the lengths are the same
        all_tasks_by_name = sorted(
            self.dependentTask.keys(), key=lambda x: x.name)
        self.analysisOrder = sorted(all_tasks_by_name,
                                    key=lambda x: len(self.dependentTask[x]),
                                    reverse=True)


def analyze_system(system, task_results=None, only_dependent_tasks=False,
                   progress_hook=None):
    """ Analyze all tasks until we find a fixed point

        system -- the system to analyze
        task_results -- if not None, all intermediate analysis
        results from a previous run are reused

        Returns a dictionary with results for each task.

        This based on the procedure described in Section 7.2 in [Richter2005]_.
    """
    if task_results is None:
        task_results = dict()
        for r in system.resources:
            for t in r.tasks:
                task_results[t] = TaskResult()
                t.analysis_results = task_results[t]

    analysis_state = GlobalAnalysisState(system, task_results)

    iteration = 0
    logger.debug("analysisOrder: %s" % (analysis_state.analysisOrder))
    while len(analysis_state.dirtyTasks) > 0:

        if progress_hook is not None:
            progress_hook(analysis_state)

        logger.info("Analyzing, %d tasks left" %
                   (len(analysis_state.dirtyTasks)))

        for t in analysis_state.analysisOrder:
            if t not in analysis_state.dirtyTasks:
                continue
            start = time.clock()

            analysis_state.dirtyTasks.remove(t)

            if only_dependent_tasks and len(analysis_state.
                                            dependentTask[t]) == 0:
                continue  # skip analysis of tasks w/o dependents

            old_jitter = task_results[t].wcrt - task_results[t].bcrt
            old_busytimes = copy.copy(task_results[t].busy_times)
            analyze_task(t, task_results)
            new_jitter = task_results[t].wcrt - task_results[t].bcrt
            new_busytimes = task_results[t].busy_times

            if new_jitter != old_jitter or old_busytimes != new_busytimes:
                # If jitter has changed, the input event models of all
                # dependent task(s) have also changed,
                # including their dependent tasks and so forth...
                # so mark them and all other tasks on their resource for
                # another analysis

                # propagate event model
                _propagate(t, task_results)

                # mark all dependencies dirty
                analysis_state._mark_dependents_dirty(t)
                break  # break the for loop to restart iteration

            elapsed = (time.clock() - start)
            logger.debug("iteration: %d, time: %.1f task: %s wcrt: %f dirty: %d"
                         % (iteration, elapsed, t.name,
                            task_results[t].wcrt,
                            len(analysis_state.dirtyTasks)))
            iteration += 1

        # # check for constraint violations
        if options.get_opt("check_violations"):
            violations = system.constraints.check_violations(task_results)
            if violations == True:
                logger.error("Analysis stopped!")
                break

    # print "Global iteration done after %d iterations" % (round)

    # # also print the violations if on-the-fly checking was turned off
    if not options.get_opt("check_violations"):
        check_violations(system.constraints, task_results)

    return task_results


def check_violations(constraints, task_results, wcrt=True, path=True,
        backlog=True, load=True):
    """ Check all if all constraints are satisfied.
    Returns True if there are constraint violations.
    :param task_results: dictionary which stores analysis results
    :type task_results: dict (analysis.TaskResult)
    :param wcrt: if True, check wcrt
    :param path: if True, check path latencies
    :param backlog: if True, check buffersized
    :param load: if True, check loads
    :rtype: boolean
    """
    violations = False
    if wcrt == True:
        deadline_violations = _check_wcrt_constraints(constraints, task_results)
        for v in deadline_violations:
            logger.error("Deadline violated for task %s, "
                    "wcrt=%d, deadline=%d" %
                    (v.name, task_results[v].wcrt,
                        constraints._wcrt_constraints[v]))
        violations = violations or (len(deadline_violations) > 0)

    if path == True:
        latency_violations = _check_path_constraints(constraints, task_results)
        for v, latency in latency_violations:
            deadline, n = constraints._path_constraints[v]
            logger.error("Path latency constraint violated for path %s,"
                         " latency=%d, deadline=%d, n=%d" % (v, latency, deadline, n))
        violations = violations or (len(latency_violations) > 0)

    if backlog == True:
        backlog_violations = _check_backlog_constrains(constraints, task_results)
        for v in backlog_violations:
            logger.error("Backlog constraint violated for task %s,"
                         " backlog=%f, deadline=%d" % (v.name, task_results[v].backlog,
                                                       constraints._backlog_constraints[v]))
        violations = violations or (len(backlog_violations) > 0)

    if load == True:
        load_violations = _check_load_constrains(constraints, task_results)
        for v in load_violations:
            logger.error("Load constraint violated for resource %s,"
                         " actual load=%f, threshold=%f" % (v.name, v.load(),
                                                            constraints._load_constraints[v]))
        violations = violations or (len(load_violations) > 0)

    return violations

def _check_wcrt_constraints(constraints, task_results):
    """ Check all wcrt constraints and return a list of violating tasks
    """
    violations = list()
    for task, deadline in constraints._wcrt_constraints.items():
        if task_results[task].wcrt > deadline:
            violations.append(task)
    return violations

def _check_path_constraints(constraints, task_results):
    """ Check all path constraints and return a list of violations.
    Each entry is a tuple of the form (path, latency)
    """
    violations = list()
    for path, (deadline, n) in constraints._path_constraints.items():
        bcl, wcl = path_analysis.end_to_end_latency(path, task_results, n)
        if  wcl > deadline:
            violations.append((path, wcl))
    return violations

def _check_backlog_constrains(constraints, task_results):
    """ Check all backlog constraints and return a list of tasks that violate their constraint.
    """
    violations = list()
    for task, size in constraints._backlog_constraints.items():
        task.resource.scheduler.compute_max_backlog(task, task_results)
        if task_results[task].max_backlog > size:
            violations.append(task)
    return violations

def _check_load_constrains(constraints, task_results):
    """ Check all load constraints and return a list of resources
    which violate their constraint
    """
    violations = list()
    for resource, load in constraints._load_constraints.items():
        if resource.load() > load:
            violations.append(resource)
    return violations
