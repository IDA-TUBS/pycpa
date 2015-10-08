""" Generic Compositional Performance Analysis Algorithms

| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer
         - Johannes Schlatow

Description
-----------

This module contains methods for real-time scheduling analysis.
It should be imported in scripts that do the analysis.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


import gc
import logging
import copy
import time
from collections import deque
import functools

from . import model
from . import options
from . import util
from . import path_analysis

gc.enable()
logger = logging.getLogger(__name__)


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

class JunctionStrategy(object):
    """ This class encapsulates the junction-specific analysis """

    def __init__(self):
        self.name = None

    def propagate(self, junction, task_results):
        """ Propagate event model over a junction """
        # cut function cycles
        propagate_tasks = copy.copy(junction.prev_tasks)

        # find potential functional cycles in the app-graph
        # _propagate tasks are all previous input tasks without cycles
        # TODO This should only be done for AND junctions (see issue #4).
        subgraph = util.breadth_first_search(junction)
        for prev in junction.prev_tasks:
            if prev in subgraph:
                logger.warning("Cutting functional cycle at join.")
                propagate_tasks.remove(prev)

        if len(propagate_tasks) == 0:
            raise NotSchedulableException("AND Junction %s "
                                          "consists only of a functional"
                                          " cycle without further stimulus"
                                          % junction)

        # recalculate the output event model
        self.reload_in_event_models(junction, task_results, propagate_tasks)

        # check if all input event models of this junction are valid,
        # i.e. not None
        if self.out_event_models_valid(junction, propagate_tasks):
            # All input event models valid. Use junction strategy to
            # derive output event model.
            new_output_event_model = self.calculate_out_event_model(junction)
        else:
            # Some input event models of this junction are still invalid,
            # i.e. None. Propagate "weak" event model in this case.
            new_output_event_model = self.get_weak_event_model()

        # _assert_event_model_conservativeness(junction.out_event_model,
        # new_output_event_model)
        junction.out_event_model = new_output_event_model

        for t in junction.next_tasks:
            t.in_event_model = junction.out_event_model

    def get_weak_event_model(self):
        new_output_event_model = model.EventModel()
        new_output_event_model.deltamin_func = lambda n: (INFINITY)
        new_output_event_model.deltaplus_func = lambda n: (INFINITY)
        return new_output_event_model


    def reload_in_event_models(self, junction, task_results, non_cycle_prev):
        """ Helper function, reloads input event models of junction from tasks in non_cycle_prev"""
        junction.in_event_models.clear()
        for t in non_cycle_prev:
            out = out_event_model(t, task_results, junction)
            if out is not None:
                junction.in_event_models[t] = out

    def out_event_models_valid(self, junction, non_cycle_prev):
        return len(non_cycle_prev) == len(junction.in_event_models)

    def __repr__(self):
        return self.name


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

    def compute_wcrt(self, task, task_results=None):
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

        logger.debug('compute wcrt of %s' % (task.name))

        # This could possibly be improved by using the previously computed
        #  WCRT and q as a starting point. Is this conservative?
        q = 1
        # q for which the max wcrt was computed
        q_wcrt = 1
        # datatype of task.wcet is not known here
        # (e.g. variable execution times)
        wcrt = 0

        b_wcrt = dict()  # store details of busy window leading to wcrt
        if task_results:
            task_results[task].busy_times = [0]  # busy time of 0 activations
        self.b_plus(task, 1, details=b_wcrt)
        while True:
            logger.debug('iteration for q=%d' %(q))
            w = self.b_plus(task, q)
            if task_results:
                logger.debug('setting results %d', w)
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
        if task_results:
            task_results[task].q_wcrt = q_wcrt
            task_results[task].wcrt = wcrt
            task_results[task].b_wcrt = b_wcrt
        # logger.debug(task.name + " busy times: " +
        # str(task_results[task].busy_times))
        return wcrt

    def compute_bcrt(self, task, task_results=None):
        """ Return the best-case response time for q activations of a task.
        Convenience function which calls the minimum busy-time.
        The bcrt is also stored in task_results.

        """
        bcrt = self.b_min(task, 1)
        if task_results:
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
    assert task is not None
    assert task_results is not None
    assert task in task_results

    for t in task.resource.tasks:
        assert (t.in_event_model is not None), 'task must have event model'

    assert (task.bcet <= task.wcet), 'BCET must not be larger '\
            'than WCET for task %s' % (task.name)

    task.resource.scheduler.compute_bcrt(task, task_results)
    task.resource.scheduler.compute_wcrt(task, task_results)
    task.resource.scheduler.compute_max_backlog(task, task_results)

    assert (task_results[task].bcrt <= task_results[task].wcrt),\
            'Task:%s, BCRT (%d) must not be larger than WCRT (%d)' % \
            (task.name, task_results[task].bcrt, task_results[task].wcrt)


def out_event_model(task, task_results, dst_task=None):
    """ Wrapper to call the actual out_event_model_*,
    which computes the output event model of a task.
    See Chapter 4 in [Richter2005]_ for an overview.
    """
    # if there is no valid input model, there is no valid output model
    if task.in_event_model is None:
        return None

    # "shortcut" input event model if propagation is disabled for this task
    if task.no_propagation:
        return task.in_event_model

    method = options.get_opt('propagation')
    if method == 'jitter_offset':
        OutEventModelClass = JitterOffsetPropagationEventModel
    elif method == 'busy_window':
        OutEventModelClass = BusyWindowPropagationEventModel
    elif  method == 'jitter_dmin' or method == 'jitter':
        OutEventModelClass = JitterPropagationEventModel
    elif method == 'jitter_bmin':
        OutEventModelClass = JitterBminPropagationEventModel
    elif method == 'optimal':
        OutEventModelClass = OptimalPropagationEventModel
    else:
        raise NotImplementedError

    em = OutEventModelClass(task, task_results)

    if isinstance(task, model.Fork):
        assert dst_task is not None
        task.out_event_model = em
        return task.strategy.output_event_model(task, dst_task, task_results)
    else:
        return em


class JitterPropagationEventModel(model.EventModel):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).

    This corresponds to Equations 1 (non-recursive) and
    2 (recursive from [Schliecker2009]_
    This is equivalent to Equation 5 in [Henia2005]
    or Equation 4.6 in [Richter2005]_.

    Uses a reference to task.deltamin_func
    """
    def __init__(self, task, task_results, nonrecursive=True):
        self.task = task
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.dmin = task_results[task].bcrt
        self.nonrecursive = nonrecursive

        name = task.in_event_model.__description__ + "+J=" + \
            str(self.resp_jitter) + ",dmin=" + str(self.dmin)

        model.EventModel.__init__(self,name,task.in_event_model.container)

        if options.get_opt('propagation') == 'jitter':
            # ignore dmin if propagation is jitter only
            self.dmin = 0

        assert self.resp_jitter >= 0, 'response time jitter must be positive'


    def deltamin_func(self, n):
        if self.nonrecursive:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                    (n - 1) * self.dmin)
        else:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                        self.delta_min(n - 1) + self.dmin)

    def deltaplus_func(self, n):
        return self.task.in_event_model.delta_plus(n) + self.resp_jitter


class JitterOffsetPropagationEventModel(model.EventModel):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).

    This corresponds to Equations 1 (non-recursive) and
    2 (recursive from [Schliecker2009]_
    This is equivalent to Equation 5 in [Henia2005]
    or Equation 4.6 in [Richter2005]_.

    Uses a reference to task.deltamin_func
    """
    def __init__(self, task, task_results,nonrecursive=True):

        self.phi = task.in_event_model.phi + task.bcet
        self.task = task
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.J = task.in_event_model.J + self.resp_jitter
        self.P = task.in_event_model.P
        self.dmin = task_results[task].bcrt

        name = task.in_event_model.__description__ + "+J=" + \
        str(self.resp_jitter) + ",O=" + str(self.phi)

        model.EventModel.__init__(self,name,task.in_event_model.container)


        assert self.resp_jitter >= 0, 'response time jitter must be positive'

    def deltamin_func(self, n):
        return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                    (n - 1) * self.dmin)

    def deltaplus_func(self, n):
        return self.task.in_event_model.delta_plus(n) + self.resp_jitter

class JitterBminPropagationEventModel(model.EventModel):
    """ Derive an output event model from response time jitter,
    the b_min as well as
    the in_event_model (used as reference).

    Uses a reference to task.deltamin_func
    """

    def __init__(self, task, task_results,nonrecursive=True):

        self.task = task
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.nonrecursive = nonrecursive
        self.dmin = task_results[task].bcrt

       # set proper name
        name = task.in_event_model.__description__ + "+J=" + \
        str(self.resp_jitter) + ",dmin=" + str(self.dmin)

        model.EventModel.__init__(self,name,task.in_event_model.container)
        assert self.resp_jitter >= 0, 'response time jitter must be positive'


    def bmin(self, n):
        """ minimum production time for n events at the output"""
        return max(self.task.resource.scheduler.b_min(self.task, n-1),
                         (n-1)*self.dmin)

    def deltamin_func(self, n):
        if self.nonrecursive:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                    self.bmin(n))
        else:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                        self.delta_min(n - 1) + self.dmin, self.bmin(n))

    def deltaplus_func(self, n):
        return self.task.in_event_model.delta_plus(n) + self.resp_jitter

class BusyWindowPropagationEventModel(model.EventModel):
    """ Derive an output event model from busy window
     and in_event_model (used as reference).
    Gives better results than _out_event_model_jitter.

    This results from Theorems 1, 2 and 3 from [Schliecker2008]_.
    """

    def __init__(self, task, task_results, nonrecursive=True):
        # set proper name
        name = task.in_event_model.__description__ + "++"

        model.EventModel.__init__(self,name,task.in_event_model.container)

        self.task = task
        self.dmin = task_results[task].bcrt
        self.bcrt = task_results[task].bcrt
        self.busy_times = task_results[task].busy_times

    def deltamin_func(self, n):
        max_k = len(self.busy_times)
        min_k = 1  # k \elem N+
        bcrt = self.bcrt

        if max_k <= 1:
            # if this task has not been analysed, propagate input event model
            return self.task.in_event_model.delta_min(n)

        assert max_k > min_k

        return max((n - 1) * self.dmin,
            min([self.task.in_event_model.delta_min(n + k - 1) - self.busy_times[k]
                 for k in range(min_k, max_k)])
            + bcrt)

    def deltaplus_func(self, n):
        max_k = len(self.busy_times)
        min_k = 1  # k \elem N+
        bcrt = self.bcrt

        if max_k <= 1:
            # if this task has not been analysed, propagate input event model
            return self.task.in_event_model.delta_min(n)

        assert max_k > min_k

        return max([self.task.in_event_model.delta_plus(n - k + 1) + self.busy_times[k]
             for k in range(min_k, max_k)]) - bcrt

class OptimalPropagationEventModel(JitterBminPropagationEventModel,
                                   BusyWindowPropagationEventModel):
    """ Optimal event model based on jitter and busy_window
    propagation.
    For some schedulers, such as FIFO and EDF neither busy_window
    nor jitter propagation is optimal. This will
    try both and take choses the best result.
    """
    def __init__(self, task, task_results, nonrecursive=True):
        self.task = task
        self.task_result = task_results[task]
        self.dmin = task_results[task].bcrt
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.nonrecursive = nonrecursive

        name = task.in_event_model.__description__ + "++"
        model.EventModel.__init__(self,name,task.in_event_model.container)

    def deltamin_func(self, n):
        return max(JitterBminPropagationEventModel.deltamin_func(self, n),
                BusyWindowPropagationEventModel.deltamin_func(self, n))

    def deltaplus_func(self, n):
        return min(JitterBminPropagationEventModel.deltaplus_func(self, n),
                BusyWindowPropagationEventModel.deltaplus_func(self, n))


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
            t.in_event_model = out_event_model(task, task_results, t)
            t.update_execution_time()
        elif isinstance(t, model.Junction):
            t.strategy.propagate(t, task_results)
        else:
            raise TypeError("invalid propagation target")


def _assert_event_model_conservativeness(emif_small, emif_large, n_max=1000):
    """ Assert that emif_large is no greater than emif_small """
    if emif_small is None:
        return
    for n in range(2, n_max):
        assert emif_large.delta_min(n) <= emif_small.delta_min(n)


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

        # # clean old analysis state before we start a new analysis
        self.clean_analysis_state()

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
            # if there in no task with an valid event model, then the
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
        # FIXME dead code
        """ add task and its dependencies to the dirty set """
        if isinstance(task, model.Task):  # skip junctions
            self.dirtyTasks.add(task)
            for t in task.get_resource_interferers():
                # also mark all tasks on the same resource
                self.dirtyTasks.add(t)
            for t in task.get_mutex_interferers():
                # also mark all tasks on the same shared resource
                print("marked diry, mutex")
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
                self._add_dependent_tasks(task, task.next_tasks, inputDependentTask)

        self.dependentTask = inputDependentTask

    def _add_dependent_tasks(self, task, dependent_tasks, inputDependentTask):
        """ Helper function for _init_depentent_tasks(). Will be called recursively. """
        for t in dependent_tasks:
            if isinstance(t, model.Task):
                # all directly dependent task
                inputDependentTask[task].add(t)

                # all tasks on the same resource as directly dependent
                # tasks (only for tasks, not junctions)
                inputDependentTask[
                    task] |= set(t.get_resource_interferers())
            elif isinstance(t, model.Junction):
                self._add_dependent_tasks(task, t.next_tasks, inputDependentTask)


    def _init_analysis_order(self):
        """ Init the analysis order,
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
                if not t.no_propagation:
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

        # explicitly invoke garbage collection because there seem to be circluar references
        # TODO should be using weak references instead for model propagation
        gc_count = gc.collect()
        for t in analysis_state.analysisOrder:
            if t not in analysis_state.dirtyTasks:
                continue
            start = time.clock()

            analysis_state.dirtyTasks.remove(t)

            # skip analysis for tasks w/ disable propagation
            if t.no_propagation:
                continue

            if only_dependent_tasks and len(analysis_state.
                                            dependentTask[t]) == 0:
                continue  # skip analysis of tasks w/o dependents

            old_jitter = task_results[t].wcrt - task_results[t].bcrt
            old_busytimes = copy.copy(task_results[t].busy_times)
            analyze_task(t, task_results)

            #sanity check
            assert functools.reduce(lambda x, y: x and y,\
                           [b - a >= t.wcet for a,b \
                            in util.window(task_results[t].busy_times)]) == True, "Busy_times for task %s on resource %s: %s" % (t.name, t.resource.name, str(task_results[t].busy_times))

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
        backlog_violations = _check_backlog_constraints(constraints, task_results)
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

def _check_backlog_constraints(constraints, task_results):
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
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
