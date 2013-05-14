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

It should be imported in scripts that do the analysis.
We model systems composed of resources and tasks.
Tasks are activated by events, modeled as event models.
The general System Model is described in Section 3.6.1 in [Jersak2005]_
or Section 3.1 in [Henia2005]_.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import math
import logging
import copy
import warnings

from . import options
from . import util

INFINITY = float('inf')

logger = logging.getLogger("pycpa")


def _warn_float(value, reason=""):
    """ Prints a warning with reason if value is float.
    """
    if type(value) == float:
        warnings.warn("You are using floats, "
                      "this may yield non-pessimistic results (" + reason +
                      ")", UserWarning)


class ConstraintsManager(object):
    """ This class manages all system-wide constraints such as deadlines,
    buffersizes and more.
    """

    def __init__(self):
        # # local task deadlines
        self._wcrt_constraints = dict()

        # # latency contraints
        self._path_constraints = dict()

        # # buffer size constraints
        self._backlog_constraints = dict()

        # # resource load constraints
        self._load_constraints = dict()

    def add_wcrt_constraint(self, task, deadline):
        """ adds a local task deadline constraint
        wcrt must be less or equal than deadline
        """
        self._wcrt_constraints[task] = deadline

    def add_path_constraint(self, path, deadline, n=1):
        """ adds a path latency constraint
        latency for n events must be less or equal than deadline
        """
        self._path_constraints[path] = (deadline, n)

    def add_backlog_constraint(self, task, size):
        """ adds a buffer size constraint
        backlog must be less or equal than size
        """
        self._backlog_constraints[task] = size

    def add_load_constraint(self, resource, load):
        """ adds a resource load constraint
        actual load on the specified resource must be less or equal than load
        """
        self._load_constraints[resource] = load



class EventModel (object):
    """ The event model describing the activation of tasks as described
    in [Jersak2005]_, [Richter2005]_, [Henia2005]_.
    Internally, we use :math:`\delta^-(n)` and  :math:`\delta^+(n)`,
    which represent the minimum/maximum time window containing n events.
    They can be transformed into
    :math:`\eta^+(\Delta t)` and :math:`\eta^-(\Delta t)`
    which represent the maximum/minimum number of events arriving within
    :math:`\Delta t`.
    """

    def __init__(self, name='min', cache=None):
        """ CTOR
        If called without parameters, a maximal event model (unbounded amount
        of activations) is created
        """

        # # Enables or disables caching
        self.en_caching = not options.get_opt('nocaching')

        # # Cache to speedup busy window calculations
        self.delta_min_cache = dict()
        self.delta_plus_cache = dict()

        self.eta_min_cache = dict()
        self.eta_plus_cache = dict()

        self.eta_min_closed_cache = dict()
        self.eta_plus_closed_cache = dict()

        # # Event model eta_plus-plus function (internal)
        # maximal model: unlimited activations
        self.deltaplus_func = lambda x: 0

        # # Event model eta_plus-minus function (internal)
        self.deltamin_func = lambda x: float(
            "inf")  # minimal model: no activation

        # # String description of event model
        self.__description__ = name



    @staticmethod
    def delta_min_from_eta_plus(etaplus_func):
        """ Delta-minus Function
            Return the minimum time window containing n activations.
            The delta_minus-function is derived from the eta_plus-function.
            This function is rarely needed, as EventModels are represented
            by delta-functions internally.
            Equation 3.7 from [Schliecker2011]_.
        """
        # TODO:_ binary search
        def delta_min(n):
            if n < 2:
                return 0
            x = 0
            while etaplus_func(x) < n:
                x += 1
            return  int(math.floor(x - 1))
        return delta_min

    @staticmethod
    def delta_plus_from_eta_min(etamin_func):
        """ Delta-plus Function
            Return the maximum time window containing n activations.
            The delta_plus-function is derived from the eta_minus-function.
            This function is rarely needed, as EventModels are represented
            by delta-functions internally.
            Equation 3.8 from [Schliecker2011]_.
        """
        # TODO:_ binary search
        def delta_plus(n):
            if n < 2:
                return 0
            x = 0
            while etamin_func(x) < n - 1:
                x += 1
            return  int(math.floor(x))
        return delta_plus

    def eta_plus(self, w):
        """ Eta-plus Function
            Return the maximum number of events in a time window w.
            Derived from Equation 3.5 from [Schliecker2011]_,
            but assuming half-open intervals for w
            as defined in [Richter2005]_.
        """
        n = self.eta_plus_cache.get(w, None)
        if n is not None:
            return n

        # the window for 0 activations is 0
        if w <= 0:
            return 0
        # if the window does not include 2 activations, assume that one has
        # occured
        if self.delta_min(2) > w:
            return 1
        # if delta_min is constant zero, eta_plus is always infinity
        if self.delta_min(INFINITY) == 0:
            return INFINITY
        hi = 10
        lo = 2

        # search an upper bound
        while self.delta_min(hi) < w:
            lo = hi
            hi *= 10

        # apply binary search
        while lo < hi:
            mid = (lo + hi) // 2
            midval = self.delta_min(mid)
            if midval < w:
                lo = mid + 1
            else:
                hi = mid
        hi -= 1

        assert self.delta_min(hi) < w
        assert self.delta_min(hi + 1) >= w

        if self.en_caching:
            self.eta_plus_cache[w] = hi

        return hi

    def eta_plus_closed(self, w):
        """ Eta-plus Function
            Return the maximum number of events in a time window w.
            Derived from Equation 3.5 from [Schliecker2011]_,
            but assuming CLOSED intervals for w
            as defined in [Richter2005]_.

            This is technically identical to eta_plus(w + EPSILON),
            but the use of epsilon has issues with float precision,
            as w+EPSILON == w for large w and small Epsilon
            (e.g. 40000000+1e-9)
        """
        n = self.eta_plus_closed_cache.get(w, None)
        if n is not None:
            return n

        # if the window does not include 2 activations, assume that one has
        # occured
        if self.delta_min(2) > w:
            return 1
        # if delta_min is constant zero, eta_plus is always infinity
        if self.delta_min(INFINITY) == 0:
            return INFINITY
        hi = 10
        lo = 2

        # search an upper bound
        while self.delta_min(hi) <= w:
            lo = hi
            hi *= 10

        # apply binary search
        while lo < hi:
            mid = (lo + hi) // 2
            midval = self.delta_min(mid)
            if midval <= w:
                lo = mid + 1
            else:
                hi = mid
        hi -= 1

        assert self.delta_min(hi) <= w
        assert self.delta_min(hi + 1) > w

        if self.en_caching:
            self.eta_plus_closed_cache[w] = hi

        return hi

    def eta_min(self, w):
        """ Eta-minus Function
            Return the minimum number of events in a time window w.
            Derived from Equation 3.6 from [Schliecker2011]_,
            but different, as Eq. 3.6 is wrong.
        """
        n = self.eta_min_cache.get(w, None)
        if n is not None:
            return n

        MAX_EVENTS = 10000
        n = 2
        while self.delta_plus(n) <= w:
            assert self.delta_plus(n) <= self.delta_plus(n + 1)
            if(n > MAX_EVENTS):
                logger.error("w=%f" % w + " n=%d" % n +
                             "deltaplus(n)=%d" % self.delta_plus(n))
                return n
            n += 1

        if self.en_caching:
            self.eta_min_cache[w] = n-2

        return n - 2

    def eta_min_closed(self, w):
        """ Eta-minus Function
            Return the minimum number of events in a time window w.
            Using CLOSED intevals
        """
        n = self.eta_min_closed_cache.get(w, None)
        if n is not None:
            return n

        MAX_EVENTS = 10000
        n = 2
        while self.delta_plus(n) < w:
            if(n > MAX_EVENTS):
                logger.error("w=%f" % w + " n=%d" % n +
                             "deltaplus(n)=%d" % self.delta_plus(n))
                return n
            n += 1

        if self.en_caching:
            self.eta_min_closed_cache[w] = n-2

        return n - 2

    def delta_min(self, n):
        """ Delta-minus Function
            Return the minimum time interval between
            the first and the last event
            of any series of n events.
            This is actually a wrapper to allow caching of delta functions.
        """
        if n < 2:
            return 0

        # # Caching is activated
        if self.en_caching == True:
            d = self.delta_min_cache.get(n, None)
            if d == None:
                d = self.deltamin_func(n)
                self.delta_min_cache[n] = d
            return d

        # # default policy
        return self.deltamin_func(n)


    def delta_plus(self, n):
        """ Delta-plus Function
            Return the maximum time interval between
            the first and the last event
            of any series of n events.
            This is actually a wrapper to allow caching of delta functions.
        """
        if n < 2:
            return 0

        # # Caching is activated
        if self.en_caching == True:
            d = self.delta_plus_cache.get(n, None)
            if d == None:
                d = self.deltaplus_func(n)
                self.delta_plus_cache[n] = d
            return d

        # # default policy
        return self.deltaplus_func(n)


    def load(self, accuracy=1000):
        """ Returns the asymptotic load,
        i.e. the avg. number of events per time
        """
        # print "load = ", float(self.eta_plus(accuracy)),"/",accuracy
        # return float(self.eta_plus(accuracy)) / accuracy
        if self.delta_min(accuracy) == 0:
            return float("inf")
        else:
            return float(accuracy) / self.delta_min(accuracy)

    def flush_cache(self):
        self.delta_min_cache = dict()
        self.delta_plus_cache = dict()

        self.eta_min_cache = dict()
        self.eta_plus_cache = dict()

        self.eta_min_closed_cache = dict()
        self.eta_plus_closed_cache = dict()

    def __repr__(self):
        """ Return a description of the Event-Model"""
        return self.__description__

class PJdEventModel (EventModel):
    """ A periodic, jitter, min-distance event model.
    """

    def __init__(self, P=0, J=0, dmin=0, phi=0, name='min', cache=None):
        """ Periodic, Jitter, min. distance event model. Offset can be supplied
        but is not evaluated by all analyses.
        """
        EventModel.__init__(self, name, cache)

        # setup event model
        self.set_PJd(P, J, dmin)

        # store parameters
        self.P = P
        self.J = J
        self.dmin = dmin

        # offset for some context sensitive analyses
        self.phi = phi

    def set_PJd(self, P, J=0, dmin=0, early_arrival=False):
        """ Sets the event model to a periodic activation
        with jitter and minimum distance.
        Equations 1 and 2 from [Schliecker2008]_.
        """
        _warn_float(P, "Period")
        _warn_float(J, "Jitter")
        _warn_float(dmin, "dmin")

        # save away the properties in case a local analysis uses them directly
        self.P = P
        self.J = J
        self.dmin = dmin

        self.__description__ = "P={} J={} d={}".format(P, J, dmin)
        if early_arrival:
            raise(NotImplementedError)
        else:
            self.deltaplus_func = lambda n: (n - 1) * P + J
            self.deltamin_func = lambda n: max((n - 1) * dmin, (n - 1) * P - J)


class CTEventModel (EventModel):
    """ c events every T time event model.
    """
    def __init__(self, c, T, dmin=1, name='min', cache=None):

        EventModel.__init__(self, name, cache)

        self.set_c_in_T(c, T, dmin)
        self.c = c
        self.T = T
        self.dmin = dmin


    def set_c_in_T(self, c, T, dmin=1):
        """ Sets the event-model to a periodic Task
         with period T and c activations per period.
         No minimum arrival rate is assumed (delta_plus = infinity)!
         Cf. Equation 1 in [Diemer2010]_.
        """
        self.__description__ = "%d every %d, dmin=%d" % (c, T, dmin)
        if c == 0 or T >= INFINITY:
            self.deltamin_func = lambda n: 0
        else:
            def c_in_T_deltamin_func(n):
                if n == INFINITY:
                    return INFINITY
                else:
                    return (n - 1) * dmin + int(math.floor(float(n - 1) / c)
                            * (T - c * dmin))

            self.deltamin_func = c_in_T_deltamin_func

        self.deltaplus_func = lambda n: INFINITY


class LimitedDeltaEventModel(EventModel):
    """ User supplied event model on a limited delta domain.
    """
    def __init__(self,
            limited_delta_min_func=None,
            limited_delta_plus_func=None,
            limit_q_min=float('inf'),
            limit_q_plus=float('inf'),
            min_additive=util.recursive_min_additive,
            max_additive=util.recursive_max_additive,
            name='min', cache=None):

        EventModel.__init__(self, name, cache)

        self.set_limited_delta(limited_delta_min_func, limited_delta_plus_func, limit_q_min, limit_q_plus, min_additive, max_additive)


    def set_limited_delta(self,
            limited_delta_min_func,
            limited_delta_plus_func,
            limit_q_min=float('inf'),
            limit_q_plus=float('inf'),
            min_additive=util.recursive_min_additive,
            max_additive=util.recursive_max_additive):
        """ Sets the event model to an arbitrary function specified
        by limited_delta_min_func and limited_delta_plus_func.
        Contrary to directly setting deltamin_func and deltaplus_func,
        the given functions are only valid in a limited domain [0, limit_q_min]
        and [0, limit_q_plus] respectively.
        For values of q beyond this range, a conservative extension
        (additive extension) is used.
        You can also supply a list() object to this function by using
        lambda x: limited_delta_min_list[x]
        """
        self.__description__ = "ltd. direct"


        def delta_min_func(n):
            if n == float("inf"):
                return float("inf")
            elif n > limit_q_min:  # return additive extension  if necessary
                q_max = limit_q_min - 1
                ret = max_additive(lambda x: self.delta_min(x + 1),
                        n - 1, q_max, self.delta_min_cache)
                return ret
            else:
                return limited_delta_min_func(n)

        def delta_plus_func(n):
            if n == float("inf"):
                return float("inf")
            elif n > limit_q_plus:  # return additive extension  if necessary
                q_max = limit_q_plus - 1
                ret = min_additive(lambda x: self.delta_plus(x + 1),
                        n - 1, q_max, self.delta_plus_cache)
                return ret
            else:
                return limited_delta_plus_func(n)

        self.deltaplus_func = delta_plus_func
        self.deltamin_func = delta_min_func


class TraceEventModel (LimitedDeltaEventModel):
    def __init__(self, trace_points=[], min_sample_size=20,
                 min_additive=util.recursive_min_additive,
                 max_additive=util.recursive_max_additive,
                 name='min', cache=None):
        LimitedDeltaEventModel.__init__(self, name=name, cache=cache)

        self.trace_points = trace_points
        self.min_sample_size = min_sample_size
        self.min_addititive = min_additive
        self.max_additive = max_additive

        self.set_limited_trace(trace_points, min_sample_size, min_additive, max_additive)

    def set_limited_trace(self,
            trace_points,
            min_sample_size=20,
            min_additive=util.recursive_min_additive,
            max_additive=util.recursive_max_additive):
        """ Compute a pseudo-conservative event model from a given trace
        (e.g. from SymTA/S TraceAnalyzer or similar).
        trace_points must be a list of integers encoding the arrival time
        of an event. The algorithm will compute delta_min and delta_plus based
        on the trace by evaluating all candidates.
        min_sample_size is the minimum amount of candidates that must
        be available to derive a representative deltamin/deltaplus
        """

        for p in set(trace_points):
            if type(p) == float:
                warnings.warn("You are using floats in your timestamps,"
                             " this may yield non-pessimistic results"
                             " consider using time conversion from pycpa.util")
                break


        # import numy only when needed
        import numpy as np
        trace = np.array(trace_points)
        q_max = trace.size

        def raw_deltamin_func(n):
            """ raw trace deltamin_func, only valid in the interval [0,q_max]
            """
            assert n >= 0
            assert n <= q_max
            d = float('inf')
            for q in range(0, q_max - n + 1):
                seq = trace[q:q + n ]
                assert seq.size == n
                d_new = seq[-1] - seq[0]
                assert d_new >= 0
                d = min(d_new, d)
            return d


        def raw_deltaplus_func(n):
            """ raw trace deltaplus_func, only valid in the interval [0,q_max]
            """
            assert n >= 0
            assert n <= q_max
            d = 0
            for q in range(0, q_max - n + 1):
                seq = trace[q:q + n ]
                assert seq.size == n
                d_new = seq[-1] - seq[0]
                assert d_new >= 0
                d = max(d_new, d)
            return d

        # set the trace as a limited delta function and let pycpa extrapolate
        limit_q_max = max(2, q_max - min_sample_size)
        # print("q_max", q_max, "trace_size", trace.size, limit_q_max)
        self.set_limited_delta(raw_deltamin_func, raw_deltaplus_func,
                limit_q_max, limit_q_max, min_additive, max_additive)

        self.__description__ = "trace-based"


class Junction (object):
    """ A junction combines multiple event models into one output event model
        This is used to model multi-input tasks.
        Valid semantics are "and" and "or" junctions.
        See Chapter 4 in [Jersak2005]_ for definitions and details.
    """

    def __init__(self, name="unknown", mode='and'):
        """ CTOR """
        # # Name
        self.name = name

        # # Semantics of the event concatenation
        self._mode = mode

        # # Set of input tasks
        self.prev_tasks = set()

        # # Output event model
        self.out_event_model = None

        # # Link to next Tasks or Junctions,
        # i.e. where to supply event model to
        self.next_tasks = set()

        self.in_event_models = set()

        # # at some point Junction looks like a task
        # i.e. provide wcet, bcet for duck-typing
        self.bcet = 0
        self.wcet = 0

    def invalidate_event_model_cache(self):
        for t in self.next_tasks:
            t.invalidate_event_model_cache()

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode):
        if mode == "and" or mode == "or":
            self._mode = mode
        else:
            raise TypeError(str(mode) + " is not a supported mode")

    def link_dependent_task(self, task):
        task.prev_task = self
        self.next_tasks.add(task)

    def clean(self):
        """ mark output event model as invalid """
        self.out_event_model = None

    def __repr__(self):
        return self.name + " " + self.mode + " junction"


class Task (object):
    """ A Task is an entity which is mapped on a resource and consumes service.
    Tasks are activated by events, which are described by EventModel.
    Events are queued in FIFO order at the input of the task,
    see Section 3.6.1 in [Jersak2005]_ or Section 3.1 in [Henia2005]_.
    """

    def __init__(self, name, *args, **kwargs):
        """ CTOR """
        # # Descriptive string
        self.name = name

        # # Link to Resource to which Task is mapped
        self.resource = None

        # # Link the Path if the task takes part in chained communication
        # FIXME: A task can be part of more than one path! Is this used anywhere?
        self.path = None

        # # Link to Mutex to which Task is mapped
        self.mutex = None

        # # Link to next Tasks, i.e. where to supply event model to
        # # Multiple tasks possible (fork semantic)
        self.next_tasks = set()

        # Link to previous Task, i.e. the one which supplies our in_event_model
        self.prev_task = None

        # # Worst-case execution time
        self.wcet = 0

        # # Best-case execution time
        self.bcet = 0

        # # Event model activating the Task
        self.in_event_model = None

        self.analysis_results = None

        # compatability to the old call semantics (name, bcet, wcet,
        # scheduling_parameter)
        if len(args) == 3:
            self.bcet = args[0]
            self.wcet = args[1]
            self.scheduling_parameter = args[2]

        # After all mandatory attributes have been initialized above, load
        # those set in kwargs
        for key in kwargs:
            setattr(self, key, kwargs[key])

        assert(self.bcet <= self.wcet)

    def __repr__(self):
        """ Returns string representation of Task """
        return self.name

    def bind_resource(self, r):
        """ Bind a Task t to a Resource/Mutex r """
        self.resource = r
        r.tasks.add(self)
        for t in r.tasks:
            assert t.resource == r

    def unbind_resource(self):
        """ Remove a task from its resource """
        if self.resource and self in self.resource.tasks:
            self.resource.tasks.remove(self)
        self.resource = None

    def bind_mutex(self, m):
        """ Bind a Task t to a Mutex r """
        self.mutex = m
        m.tasks.add(self)

    def unbind_mutex(self):
        """ Remove a task fromk its mutex """
        if self.mutex and self in self.mutex.tasks:
            self.mutex.tasks.remove(self)
        self.mutex = None

    def link_dependent_task(self, t):
        """ Link a dependent task t to the task
        The dependent task t is activated by the completion of the task.
        """
        self.next_tasks.add(t)
        if isinstance(t, Task):
            t.prev_task = self
        else:
            t.prev_tasks.add(self)

    def get_resource_interferers(self):
        """ returns the set of tasks sharing the same Resource as Task ti
            excluding ti itself
        """
        if self.resource is None:
            return []
        interfering_tasks = copy.copy(self.resource.tasks)
        interfering_tasks.remove(self)
        return interfering_tasks

    def get_mutex_interferers(self):
        """ returns the set of tasks sharing the same Mutex as Task ti
            excluding ti itself
        """
        if self.mutex is None:
            return []
        interfering_tasks = copy.copy(self.mutex.tasks)
        interfering_tasks.remove(self)
        return interfering_tasks

    def invalidate_event_model_cache(self):
        if self.in_event_model is not None:
            self.in_event_model.flush_cache()

    def clean(self):
        """ Cleans all intermediate analysis results """

        # invalidate downstream junctions
        for n in self.next_tasks:
            if isinstance(n, Junction):
                n.clean()

        # if this task is activated by another task, we discard the event model
        if self.prev_task:
            self.in_event_model = None
        else:
            self.in_event_model.flush_cache()

        if self.analysis_results is not None:
            self.analysis_results.clean()


class Resource (object):
    """ A Resource provides service to tasks. """

    def __init__(self, name=None, scheduler=None, **kwargs):
        """ CTOR """

        # # Set of tasks mapped to this Resource
        self.tasks = set()

        # # Resource identifier
        self.name = name

        # # Analysis function
        self.scheduler = scheduler

        # After all mandatory attributes have been initialized above, load
        # those set in kwargs
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __repr__(self):
        """ Return string representation of Resource """
        s = str(self.name)
        return s

    def load(self, accuracy=10000):
        """ returns the asymptotic load """
        l = 0
        for t in self.tasks:
            try:
                l += t.in_event_model.load(accuracy) * float(t.wcet)
            except TypeError:
                logger.warn("cannot compute load for %s, skipping load "
                    "analysis for this resource" % (self.name))
                return 0.
            assert l < float('inf'), "Load on resource {} is infinity"\
                    .format(self.name)
            assert l >= 0., "Load should be non-negative"
        return l

    def bind_task(self, t):
        """ Bind task t to resource
        Returns t """
        t.bind_resource(self)
        for task in self.tasks:
            assert task.resource == self
        return t

    def unmap_tasks(self):
        """ unmap all tasks from this resource """
        for task in self.tasks:
            task.resource = None
        self.tasks = set()


class Mutex(object):
    """ A mutually-exclusive shared Resource.
    Shared resources create timing interferences between tasks
    which may be executed on different resources (e.g. multi-core CPU)
    but require access to a common resource (e.g. shared main memory) to execute.
    See e.g. Chapter 5 in [Schliecker2011]_.
    """

    def __init__(self, name=None):
        """ CTOR """

        # # Set of tasks mapped to this Resource
        self.tasks = set()

        # # Resource identifier
        self.name = name


class Path(object):
    """ A Path describes a chain of tasks.
    Required for path analysis (e.g. end-to-end latency).
    The information stored in Path classes could be derived from the task graph
    (see Task.next_tasks and Task.prev_task),
    but having redundancy here is more flexible (e.g. path analysis may only be
    interesting for some task chains).
    """

    def __init__(self, name, tasks=None):
        """ CTOR """
        # # List of tasks in Path (must be in correct order)
        if tasks is not None:
            self.tasks = tasks
            self.__link_tasks(tasks)
        else:
            self.tasks = list()
        # # create backlink to this path from the tasks
        # # so a task knows its Path
        for t in self.tasks:
            t.path = self

        # # Name of Path
        self.name = name

        ## Constant overhead to add to the latency of the path
        self.overhead = 0

    def __link_tasks(self, tasks):
        """ linking all tasks along a path"""
        assert len(tasks) > 0
        if len(tasks) == 1:
            return  # This is a fake path with just one task
        for i in zip(tasks[0:-1], tasks[1:]):
            i[0].link_dependent_task(i[1])

    def __repr__(self):
        """ Return str representation """
        # return str(self.name)
        s = str(self.name) + ": "
        for c in self.tasks:
            s += " -> " + str(c)
        return s

    def print_all(self):
        """ Print all tasks in Path. Uses __str__() """
        print(str(self))


class System(object):
    """ The System is the top-level entity of the system model.
    It contains resources, junctions, tasks and paths.
    """

    def __init__(self, name=''):
        """ CTOR """

        # # Name
        self.name = name

        # Set of resources, indexed by an ID, e.g. (x,y) tuple for mesh systems
        self.resources = set()

        # # Set of task chains
        self.paths = set()

        # # Set of junctions
        self.junctions = set()

        # # constraints bookkeeping
        self.constraints = ConstraintsManager()

    def __repr__(self):
        """ Return a string representation of the System """
        s = 'paths:'
        for h in sorted(self.paths, key=str):
            s += str(h) + ", "
        s += '\nresources:'
        for r in sorted(self.resources, key=str):
            # s += str(k)+":"+str(r)+", "
            s += str(r) + ", "

        return s

    def bind_junction(self, j):
        """ Registers a junction object in the System.
            Logically, the junction neither belongs
            to a system nor to a resource,
            for sake of convenience we associate junctions with the system.
        """
        self.junctions.add(j)
        return j

    def bind_resource(self, r):
        """ Add a Resource to the System """
        self.resources.add(r)
        return r

    def bind_path(self, path):
        """ Add a Path to the System """
        self.paths.add(path)
        # NOTE: call to "link_dependent_tasks()" on each task of the path now
        # inside Path
        return path

    def print_subgraphs(self):
        """ enumerate all subgraphs of the application graph.
        if a subgraph is not well-formed (e.g. a source is missing),
        this algorithm may
        not work correctly (it will eventually produce to many subgraphs)
        """
        subgraphs = list()
        unreachable = set()

        for resource in self.resources:
            unreachable |= set(resource.tasks)

        while len(unreachable) > 0:
            # pick one random start task (in case the app graph is not well-
            # formed)
            root_task = iter(unreachable).next()
            # but prefer a task with a source attached
            for t in unreachable:
                if t.in_event_model is not None:
                    root_task = t
                    break

            reachable = util.breadth_first_search(root_task)
            subgraphs.append(reachable)
            unreachable = unreachable - reachable

        logger.info("Application graph consists of %d disjoint subgraphs:" %
                    len(subgraphs))

        idx = 0
        for subgraph in subgraphs:
            logger.info("Subgraph %d" % idx)
            idx += 1
            for task in subgraph:
                logger.info("\t%s" % task)

        return subgraphs
