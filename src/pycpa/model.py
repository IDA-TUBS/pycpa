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

from __future__ import print_function

import math
import logging
import copy
import warnings

import options

import analysis
import path_analysis

INFINITY = float('inf')

CACHE_MISS = 0
CACHE_HIT = 0

logger = logging.getLogger("pycpa")


def _warn_float(value, reason=""):
    """ Prints a warning with reason if value is float.
    """
    if type(value) == float:
        warnings.warn("You are using floats, this may yield non-pessimistic results (" + reason + ")", UserWarning)


class ConstraintsManager(object):
    """ This class manages all system-wide constraints such as deadlines, buffersizes and more.
    """

    def __init__(self):
        ## local task deadlines
        self._wcrt_constraints = dict()

        ## latency contraints
        self._path_constraints = dict()

        ## buffer size constraints
        self._backlog_constraints = dict()

        ## resource load constraints
        self._load_constraints = dict()

    def check_violations(self, task_results, wcrt=True, path=True, backlog=True, load=True):
        """ Check all if all constraints are satisfied. Returns True if there are constraint violations.
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
            deadline_violations = self._check_wcrt_constraints(task_results)
            for v in deadline_violations:
                logger.error("Deadline violated for task %s, wcrt=%d, deadline=%d" %
                             (v.name, task_results[v].wcrt, self._wcrt_constraints[v]))
            violations = violations or (len(deadline_violations) > 0)

        if path == True:
            latency_violations = self._check_path_constraints(task_results)
            for v, latency in latency_violations:
                deadline, n = self._path_constraints[v]
                logger.error("Path latency constraint violated for path %s, latency=%d, deadline=%d, n=%d" % (v, latency, deadline, n))
            violations = violations or (len(latency_violations) > 0)

        if backlog == True:
            backlog_violations = self._check_backlog_constrains(task_results)
            for v in backlog_violations:
                logger.error("Backlog constraint violated for task %s, backlog=%f, deadline=%d" % (v.name, task_results[v].backlog, self._backlog_constraints[v]))
            violations = violations or (len(backlog_violations) > 0)

        if load == True:
            load_violations = self._check_load_constrains(task_results)
            for v in load_violations:
                logger.error("Load constraint violated for resource %s, actual load=%f, threshold=%f" % (v.name, v.load(), self._load_constraints[v]))
            violations = violations or (len(load_violations) > 0)

        return violations

    def _check_wcrt_constraints(self, task_results):
        """ Check all wcrt constraints and return a list of violating tasks
        """
        violations = list()
        for task, deadline in self._wcrt_constraints.items():
            if task_results[task].wcrt > deadline:
                violations.append(task)
        return violations

    def _check_path_constraints(self, task_results):
        """ Check all path constraints and return a list of violations.
        Each entry is a tuple of the form (path, latency)
        """
        violations = list()
        for path, (deadline, n) in self._path_constraints.items():
            bcl, wcl = path_analysis.end_to_end_latency(path, task_results, n)
            if  wcl > deadline:
                violations.append((path, wcl))
        return violations

    def _check_backlog_constrains(self, task_results):
        """ Check all backlog constraints and return a list of tasks that violate their constraint.
        """
        violations = list()
        for task, size in self._backlog_constraints.items():
            task_results[task].backlog = task.resource.scheduler.compute_max_backlog(
                task)
            if task_results[task].backlog > size:
                violations.append(task)
        return violations

    def _check_load_constrains(self, task_results):
        """ Check all load constraints and return a list of resources which violate their constraint
        """
        violations = list()
        for resource, load in self._load_constraints.items():
            if resource.load() > load:
                violations.append(resource)
        return violations

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
    """ The event model describing the activation of tasks as described in [Jersak2005]_, [Richter2005]_, [Henia2005]_.
    Internally, we use :math:`\delta^-(n)` and  :math:`\delta^+(n)`,
    which represent the minimum/maximum time window containing n events.
    They can be transformed into :math:`\eta^+(\Delta t)` and :math:`\eta^-(\Delta t)`
    which represent the maximum/minimum number of events arriving within :math:`\Delta t`.
    """

    def __init__(self, P=None, J=None, dmin=None, c=None, T=None, phi=None, name='min', cache=None):
        """ CTOR
        If called without parameters, a minimal event model (1 single activation) is created
        """

        if cache is None:
            cache = not options.get_opt('nocaching')

        ## Cache to speedup busy window calculations
        self.delta_min_cache = dict()
        self.delta_plus_cache = dict()

        ## Enables or disables delta_min caching
        self.delta_caching(cache)

        ## Event model eta_plus-plus function (internal)
        self.deltaplus_func = lambda x: 0  # minimal model: no activation

        ## Event model eta_plus-minus function (internal)
        self.deltamin_func = lambda x: float(
            "inf")   # minimal model: no activation

        ## String description of event model
        self.__description__ = name

        ## Offset for context sensitive analysis
        self.phi = phi

        ## Metadata for standard event models
        self.P = 0
        self.J = 0
        self.dmin = 0

        if c is not None and T is not None:
            self.set_c_in_T(c, T)

        if P is not None:
            if J is None:
                J = 0
            if dmin is None:
                dmin = 0
            self.set_PJd(P, J, dmin)

    @staticmethod
    def delta_min_from_eta_plus(n, eta_plus):
        """ Delta-minus Function
            Return the minimum time window containing n activations.
            The delta_minus-function is derived from the eta_plus-function.
            This function is rarely needed, as EventModels are represented by delta-functions internally.
            Equation 3.7 from [Schliecker2011]_.
        """
        MAXX = 1000
        if n < 2:
            return 0
        x = options.get_opt('epsilon')
        while eta_plus(x) < n:
            #print "eta_plus(",x,")=",self.eta_plus(x)
            x += 1
            if x > MAXX:
                return -1
        return  int(math.floor(x))

    @staticmethod
    def delta_plus_from_eta_min(n, eta_min):
        """ Delta-plus Function
            Return the maximum time window containing n activations.
            The delta_plus-function is derived from the eta_minus-function.
            This function is rarely needed, as EventModels are represented by delta-functions internally.
            Equation 3.8 from [Schliecker2011]_.
        """
        MAXX = 1000
        if n < 2:
            return 0
        x = options.get_opt('epsilon')
        while eta_min(x) < n:
            #print "eta_plus(",x,")=",self.eta_plus(x)
            x += 1
            if x > MAXX:
                return -1
        return  int(math.floor(x))

    def eta_plus(self, w):
        """ Eta-plus Function
            Return the maximum number of events in a time window w.
            Derived from Equation 3.5 from [Schliecker2011]_,
            but assuming half-open intervals for w
            as defined in [Richter2005]_.
        """
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

        return hi

    def eta_plus_closed(self, w):
        """ Eta-plus Function
            Return the maximum number of events in a time window w.
            Derived from Equation 3.5 from [Schliecker2011]_,
            but assuming CLOSED intervals for w
            as defined in [Richter2005]_.

            This is technically identical to eta_plus(w + EPSILON),
            but the use of epsilon has issues with float precision,
            as w+EPSILON == w for large w and small Epsilon (e.g. 40000000+1e-9)
        """
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

        return hi

    def eta_min(self, w):
        """ Eta-minus Function
            Return the minimum number of events in a time window w.
            Derived from Equation 3.6 from [Schliecker2011]_,
            but different, as Eq. 3.6 is wrong.
        """
        MAX_EVENTS = 10000
        n = 2
        while self.delta_plus(n) <= w:
            if(n > MAX_EVENTS):
                logger.error("w=%f" % w + " n=%d" % n +
                             "deltaplus(n)=%d" % self.delta_plus(n))
                return n
            n += 1

        return n - 2

    def eta_min_closed(self, w):
        """ Eta-minus Function
            Return the minimum number of events in a time window w.
            Using CLOSED intevals
        """
        MAX_EVENTS = 10000
        n = 2
        while self.delta_plus(n) < w:
            if(n > MAX_EVENTS):
                logger.error("w=%f" % w + " n=%d" % n +
                             "deltaplus(n)=%d" % self.delta_plus(n))
                return n
            n += 1

        return n - 2

    def delta_min(self, n):
        """ Delta-minus Function
            Return the minimum time interval between the first and the last event
            of any series of n events.
            This is actually a wrapper to allow caching of delta functions.
        """
        if n < 2:
            return 0

        ## Caching is activated
        if self.en_delta_caching == True:
            d = self.delta_min_cache.get(n, None)
            if d == None:
                d = self.deltamin_func(n)
                self.delta_min_cache[n] = d
                global CACHE_MISS
                CACHE_MISS += 1
            else:
                global CACHE_HIT
                CACHE_HIT += 1
            return d

        ## default policy
        return self.deltamin_func(n)

    @property
    def deltamin_func(self):
        """
            Getter to hide deltamin_func
        """
        return self._deltamin_func

    @deltamin_func.setter
    def deltamin_func(self, func):
        """
            Setter to hide deltamin_func
        """
        self._deltamin_func = func

    def delta_plus(self, n):
        """ Delta-plus Function
            Return the maximum time interval between the first and the last event
            of any series of n events.
            This is actually a wrapper to allow caching of delta functions.
        """
        if n < 2:
            return 0

        ## Caching is activated
        if self.en_delta_caching == True:
            d = self.delta_plus_cache.get(n, None)
            if d == None:
                d = self.deltaplus_func(n)
                self.delta_plus_cache[n] = d
                global CACHE_MISS
                CACHE_MISS += 1
            else:
                global CACHE_HIT
                CACHE_HIT += 1
            return d

        ## default policy
        return self.deltaplus_func(n)

    def set_PJd(self, P, J=0, dmin=0, early_arrival=False):
        """ Sets the event model to a periodic activation with jitter and minimum distance.
        Equations 1 and 2 from [Schliecker2008]_.
        """
        _warn_float(P, "Period")
        _warn_float(J, "Jitter")
        _warn_float(dmin, "dmin")

        #save away the properties in case a local analysis uses them directly
        self.P = P
        self.J = J
        self.dmin = dmin

        self.__description__ = "P=%g J=%g" % (P, J)
        if early_arrival:
            raise(NotImplementedError)
        else:
            self.deltaplus_func = lambda n: (n - 1) * P + J
            self.deltamin_func = lambda n: max((n - 1) * dmin, (n - 1) * P - J)

    def set_PJ(self, P, J=0, early_arrival=False):
        """ Sets the event model to a periodic activation with jitter."""
        return self.set_PJd(P, J, 0, early_arrival)

    def set_periodic(self, P, early_arrival=False, offset=0):
        """ Sets the event model to a periodic activation."""
        return self.set_PJd(P, 0, 0, early_arrival)

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
                    return (n - 1) * dmin + int(math.floor(float(n - 1) / c) * (T - c * dmin))

            self.deltamin_func = c_in_T_deltamin_func

        self.deltaplus_func = lambda n: INFINITY

    def load(self, accuracy=1000):
        """ Returns the asymptotic load, i.e. the avg. number of events per time """
        #print "load = ", float(self.eta_plus(accuracy)),"/",accuracy
        #return float(self.eta_plus(accuracy)) / accuracy
        if self.delta_min(accuracy) == 0:
            return float("inf")
        else:
            return float(accuracy) / self.delta_min(accuracy)

    def delta_caching(self, active=True):
        self.en_delta_caching = active

    def flush_cache(self):
        self.delta_min_cache = dict()

    def __repr__(self):
        """ Return a description of the Event-Model"""
        return self.__description__


class Junction (object):
    """ A junction combines multiple event models into one output event model
        This is used to model multi-input tasks.
        Valid semantics are "and" and "or" junctions.
        See Chapter 4 in [Jersak2005]_ for definitions and details.
    """

    def __init__(self, name="unknown", mode='and'):
        """ CTOR """
        ## Name
        self.name = name

        ## Semantics of the event concatenation
        self._mode = mode

        ## Set of input tasks
        self.prev_tasks = set()

        ## Output event model
        self.out_event_model = None

        ## Link to next Tasks or Junctions, i.e. where to supply event model to
        self.next_tasks = set()

        self.in_event_models = set()

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
    """ A Task is an entity which is mapped on a resource and consumes its service.
    Tasks are activated by events, which are described by EventModel.
    Events are queued in FIFO order at the input of the task,
    see Section 3.6.1 in [Jersak2005]_ or Section 3.1 in [Henia2005]_.
    """

    def __init__(self, name, *args, **kwargs):
        """ CTOR """
        ## Descriptive string
        self.name = name

        ## Link to Resource to which Task is mapped
        self.resource = None

        ## Link the Path if the task takes part in chained communication
        self.path = None  # FIXME: A task can be part of more than one path! Is this used anywhere?

        ## Link to Mutex to which Task is mapped
        self.mutex = None

        ## Link to next Tasks, i.e. where to supply event model to
        ## Multiple tasks possible (fork semantic)
        self.next_tasks = set()

        # Link to previous Task, i.e. the one which supplies our in_event_model
        self.prev_task = None

        ## Worst-case execution time
        self._wcet = 0

        ## Best-case execution time
        self._bcet = 0

        ## Event model activating the Task
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

    @property
    def wcet(self):
        """ worst case execution time """
        return self._wcet

    @wcet.setter
    def wcet(self, value):
        _warn_float(value, "WCET")
        self._wcet = value

    @property
    def bcet(self):
        """ best case execution time """
        return self._bcet

    @bcet.setter
    def bcet(self, value):
        _warn_float(value, "BCET")

        self._bcet = value

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

        ## Set of tasks mapped to this Resource
        self.tasks = set()

        ## Resource identifier
        self.name = name

        ## Analysis function
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
            l += t.in_event_model.load(accuracy) * float(t.wcet)
            assert l < float("inf")
            assert l >= 0.
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


class Mutex:
    """ A mutually-exclusive shared Resource.
    Shared resources create timing interferences between tasks
    which may be executed on different resources (e.g. multi-core CPU)
    but require access to a common resource (e.g. shared main memory) to execute.
    See e.g. Chapter 5 in [Schliecker2011]_.
    """

    def __init__(self, name=None):
        """ CTOR """

        ## Set of tasks mapped to this Resource
        self.tasks = set()

        ## Resource identifier
        self.name = name


class Path:
    """ A Path describes a chain of tasks.
    Required for path analysis (e.g. end-to-end latency).
    The information stored in Path classes could be derived from the task graph (see Task.next_tasks and Task.prev_task),
    but having redundancy here is more flexible (e.g. path analysis may only be interesting for some task chains).
    """

    def __init__(self, name, tasks=None):
        """ CTOR """
        ## List of tasks in Path (must be in correct order)
        if tasks is not None:
            self.tasks = tasks
            self.__link_tasks(tasks)
        else:
            self.tasks = list()
        ## create backlink to this path from the tasks
        ## so a task knows its Path
        for t in self.tasks:
            t.path = self

        ## Name of Path
        self.name = name

    def __link_tasks(self, tasks):
        """ linking all tasks along a path"""
        assert len(tasks) > 0
        if len(tasks) == 1:
            return  # This is a fake path with just one task
        for i in zip(tasks[0:-1], tasks[1:]):
            i[0].link_dependent_task(i[1])

    def __repr__(self):
        """ Return str representation """
        #return str(self.name)
        s = str(self.name) + ": "
        for c in self.tasks:
            s += " -> " + str(c)
        return s

    def print_all(self):
        """ Print all tasks in Path. Uses __str__() """
        print(str(self))


class System:
    """ The System is the top-level entity of the system model.
    It contains resources, junctions, tasks and paths.
    """

    def __init__(self):
        """ CTOR """

        # Set of resources, indexed by an ID, e.g. (x,y) tuple for mesh systems
        self.resources = set()

        ## Set of task chains
        self.paths = set()

        ## Set of junctions
        self.junctions = set()

        ## constraints bookkeeping
        self.constraints = ConstraintsManager()

    def __repr__(self):
        """ Return a string representation of the System """
        s = 'paths:'
        for h in sorted(self.paths, key=str):
            s += str(h) + ", "
        s += '\nresources:'
        for r in sorted(self.resources, key=str):
            #s += str(k)+":"+str(r)+", "
            s += str(r) + ", "

        return s

    def bind_junction(self, j):
        """ Registers a junction object in the System.
            Logically, the junction neither belongs to a system nor to a resource,
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
        if a subgraph is not well-formed (e.g. a source is missing), this algorithm may
        not work correctly (it will eventually produce to many subgraphs)"""
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

            reachable = analysis._breadth_first_search(root_task)
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
