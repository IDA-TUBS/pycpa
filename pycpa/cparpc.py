"""
| Copyright (C) 2012 Philip Axer, Jonas Diemer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer
         - Jonas Diemer

Description
-----------

XML-RPC server for pyCPA. It can be used to interface pycpa with
non-python (e.g. close-source) applications.
"""

from twisted.web import xmlrpc

from pycpa import model
from pycpa import schedulers
from pycpa import analysis
from pycpa import path_analysis


import logging

logger = logging.getLogger("xmlrpc")

def _unique(obj):
    """ Returns a unique id for obj """
    # Convert to string, because XML RPC does not support long ints
    return str(id(obj))


PYCPA_XMLRPC_VERSION = 2

GENERAL_ERROR = 1
INVALID_SCHEDULER = 2
INVALID_ID = 3
INVALID_EVENT_MODEL_DESC = 5
INVALID_RESULTS = 7
ILLEGAL_SYSTEM = 8
NOT_SCHEDULABLE = 9


class CPARPC(xmlrpc.XMLRPC):
    """ Basic XML RPC Server for pyCPA.

    Methods prefixed with "xmlrpc_" are actually callable from the client.

    Please see :py:mod:`pycpa.model` for more details about the pyCPA model
    and :py:mod:`pycpa.analysis` for information about the analysis.

    """
    def __init__(self):
        xmlrpc.XMLRPC.__init__(self, allowNone=False, useDateTime=False)

        self._pycpa_systems = dict()
        self._pycpa_resources = dict()
        self._pycpa_tasks = dict()
        self._pycpa_paths = dict()
        self._task_results = dict()

        #: Dictionary of scheduler classes.
        self.scheduling_policies = {
                "spp" : schedulers.SPPScheduler
        }

    def _check_task_id(self, task_id):
        """
        :returns: a reference to the task with task_id
        :rtype: string
        """
        if task_id not in self._pycpa_tasks:
            raise xmlrpc.Fault(INVALID_ID, "invalid task id")
        return self._pycpa_tasks[task_id]

    def _check_resource_id(self, resource_id):
        """ Return a reference to the resource with resource_id """
        if resource_id not in self._pycpa_resources:
            raise xmlrpc.Fault(INVALID_ID, "invalid resource id")
        return self._pycpa_resources[resource_id]

    def _check_system_id(self, system_id):
        """ Return a reference to the system with system_id """
        if system_id not in self._pycpa_systems:
            raise xmlrpc.Fault(INVALID_ID, "invalid system id")
        return self._pycpa_systems[system_id]

    def _check_path_id(self, path_id):
        """ Return a reference to the path with path_id """
        if path_id not in self._pycpa_paths:
            raise xmlrpc.Fault(INVALID_ID, "invalid path id")
        return self._pycpa_paths[path_id]

    def _check_results_id(self, results_id):
        """ Return a reference to the results with results_id """
        if results_id not in self._task_results:
            raise xmlrpc.Fault(INVALID_ID, "invalid results id")
        return self._task_results[results_id]


    def xmlrpc_new_system(self, name):
        """ create new pycpa system and return it's id

        :param name: Name of the system.
        :type name: string
        :returns: ID of the created system
        :rtype: string

        """
        name = str(name)
        s = model.System(name)
        self._pycpa_systems[_unique(s)] = s
        logger.debug("new system %s" % name)
        return _unique(s)

    def xmlrpc_protocol(self):
        """
        :returns: protocol version
        :rtype: integer
        """
        return PYCPA_XMLRPC_VERSION

    def xmlrpc_new_resource(self, system_id, name):
        """ Create a new resource with name and bind it to a system.

        :param system_id: ID of the system
        :type system_id: string
        :param name: Name of the resurce.
        :type name: string
        :returns: ID of the created resource
        :rtype: string
        """
        system = self._check_system_id(system_id)
        name = str(name)
        r = model.Resource(name)
        logger.debug("new resource %s" % name)
        system.bind_resource(r)
        self._pycpa_resources[_unique(r)] = r
        return _unique(r)

    def xmlrpc_assign_scheduler(self, resource_id, scheduler_string):
        """ Assign a scheduler to a resource.
        See :func:`xmlrpc_get_valid_schedulers` for a list of valid schedulers.

        :param resource_id: ID of the resource to which to assign the scheduler.
        :type resource_id: integer
        :param scheduler_string: Identifies the type of scheduler to set.
        :type scheduler_string: string
        :returns: 0 for success
        """
        scheduler_string = str(scheduler_string)
        resource = self._check_resource_id(resource_id)
        scheduler = self.scheduling_policies.get(scheduler_string, None)
        if scheduler is None:
            logger.error("invalid scheduler %s selected" % (scheduler_string))
            raise xmlrpc.Fault(INVALID_SCHEDULER, "invalid scheduler")
        logger.debug("assigned policy %s to resource %s" %
                     (scheduler_string, resource.name))
        resource.scheduler = scheduler()
        return 0

    def xmlrpc_get_valid_schedulers(self):
        """ Find out which schedulers are supported.

        :returns: List of valid schedulers
        :rtype: list of strings
        """

        return self.scheduling_policies.keys()

    def xmlrpc_tasks_by_name(self, system_id, name):
        """
        :returns: a list of tasks of system_id matching name
        :rtype: list of strings
        """
        system = self._check_system_id(system_id)
        system_tasks = set()
        for r in system.resources:
            system_tasks += r.tasks

        return [task_id for task_id, task in self._pycpa_tasks.iteritems()
                if task in system_tasks and task.name == name]

    def xmlrpc_new_task(self, resource_id, name):
        """ Create a new task and bind it to a ressource.

        :param resource_id: ID of the resource
        :type resource_id: string
        :param name: Name of the task.
        :type name: string
        :returns: ID of the created task
        :rtype: string
        """
        resource = self._check_resource_id(resource_id)
        task = model.Task(str(name))
        task_id = _unique(task)
        self._pycpa_tasks[task_id] = task
        resource.bind_task(task)
        return task_id

    def xmlrpc_set_task_parameter(self, task_id, attribute, value):
        """ Set the attribute of a task to value.

        This method can be used to set any attribute,
        but each scheduler expects certain attributes,
        see scheduler documentation for details
        (e.g. :py:mod:`pycpa.schedulers`).

        :param task_id: ID of the task to set the parameter for.
        :type task_id: string
        :param attribute: Attribute to set.
        :type attribute: string.
        :param value: Value to set the attribute to
        :type value: Depends on attribute.

        """
        task = self._check_task_id(task_id)
        setattr(task, attribute, value)
        return 0

    def xmlrpc_get_task_parameter(self, task_id, attribute):
        """ Return the attribute of a task.

        :param task_id: ID of the task to get the parameter from.
        :type task_id: string
        :param attribute: Attribute to get.
        :type attribute: string.
        :returns: Value of the attribute
        :rtype: Depends on attribute.
        """
        return getattr(self._pycpa_tasks[task_id], attribute)

    def xmlrpc_set_resource_parameter(self, resource_id, attribute, value):
        """ Set the attribute of a resource to value.

        This method can be used to set any attribute,
        but each scheduler expects certain attributes,
        see scheduler documentation for details
        (e.g. :py:mod:`pycpa.schedulers`).

        :param resource_id: ID of the resource to set the parameter for.
        :type resource_id: string
        :param attribute: Attribute to set.
        :type attribute: string.
        :param value: Value to set the attribute to
        :type value: Depends on attribute.

        """
        resource = self._check_resource_id(resource_id)
        setattr(resource, attribute, value)
        return 0

    def xmlrpc_get_resource_parameter(self, resource_id, attribute):
        """ Return the attribute of a resource.

        :param resource_id: ID of the resource to get the parameter from.
        :type resource_id: string
        :param attribute: Attribute to get.
        :type attribute: string.
        :returns: Value of the attribute
        :rtype: Depends on attribute.

        """
        return getattr(self._pycpa_resources[resource_id], attribute)

    def xmlrpc_link_task(self, task_id, target_id):
        """ Make task with target_id dependent of the task with task_id.

        :param task_id: ID of the task that activates the target task
        :type task_id: string
        :param target_id: ID of the task that is activate by the task.
        :type target_id: string
        :returns: 0

        """
        task = self._check_task_id(task_id)
        target = self._check_task_id(target_id)
        task.link_dependent_task(target)
        return 0

    def xmlrpc_new_path(self, system_id, name, task_ids):
        """ Adds a path consisting of a list of tasks to the system.

        :param system_id: ID of the system
        :type system_id: string
        :param name: Name of the path
        :type name: string
        :param task_ids: List of task ids corresponding to the tasks in the path.
        :type task_ids: list of strings
        :returns: ID of the created path
        :rtype: string
        """
        system = self._check_system_id(system_id)

        tasks = []
        for t_id in task_ids:
            t = self._check_task_id(t_id)
            tasks.append(t)

        p = model.Path(name, tasks)

        system.bind_path(p)
        self._pycpa_paths[_unique(p)] = p
        return _unique(p)

    def xmlrpc_assign_pjd_event_model(self, task_id, period, jitter, min_dist):
        """ Create an eventmodel and assign it to task.

        :param task_id: ID of the task
        :type task_id: string
        :param period: Period (in unit time)
        :type period: integer
        :param jitter: Jitter (in unit time)
        :type jitter: integer
        :param min_dist: Minimum distance between events (in unit time)
        :type min_dist: integer
        :returns: 0

        """
        task = self._check_task_id(task_id)
        em = None
        try:
            em = model.PJdEventModel(int(period), int(jitter), int(min_dist))
        except ValueError:
            raise xmlrpc.Fault(INVALID_EVENT_MODEL_DESC,
                               "invalid event model parametrization")
        task.in_event_model = em
        return 0

    def xmlrpc_assign_ct_event_model(self, task_id, c, T, min_dist):
        """ Create an eventmodel and assign it to task.
        The event model will represent a periodic burst with c activations
        every T time units, with the activations in each burst being
        min_dist time units apart from each other.

        :param task_id: ID of the task
        :type task_id: string
        :param c: Number of activations per burst
        :type c: integer
        :param T: Period of the bursts
        :type T: integer
        :param min_dist: Minimum distance between events (in unit time)
        :type min_dist: integer
        :returns: 0

        """
        task = self._check_task_id(task_id)
        em = None
        try:
            em = model.CTEventModel(int(c), int(T), int(min_dist))
        except ValueError:
            raise xmlrpc.Fault(INVALID_EVENT_MODEL_DESC,
                               "invalid event model parametrization")
        task.in_event_model = em
        return 0

    def xmlrpc_get_task_result(self, results_id, task_id):
        """ Obtain the analysis results for a task.

        :param results_id: ID of the results object
        :type task_id: string
        :param task_id: ID of the task
        :type task_id: string
        :returns: a dictionary of results for task_id.
        :rtype: :py:class:`pycpa.analysis.TaskResult`

        """
        results = self._check_results_id(results_id)
        task = self._check_task_id(task_id)
        if task not in results:
            raise xmlrpc.Fault(INVALID_RESULTS, "no results for task")

        return results[task]

    def xmlrpc_analyze_system(self, system_id):
        """ Analyze system and return a result id.

        :param system_id: ID of the system to analyze
        :type system_id: string
        :returns: ID of a results object
        :rtype: string
        """
        system = self._pycpa_systems[system_id]
        results = None
        for r in system.resources:
            if r.scheduler is None:
                raise xmlrpc.Fault(ILLEGAL_SYSTEM,
                                   "component %s has no scheduler assigned"
                                   % r.name)
        try:
            results = analysis.analyze_system(system)
            self._task_results[_unique(results)] = results
        except analysis.NotSchedulableException as e:
            raise xmlrpc.Fault(NOT_SCHEDULABLE, "not schedulable")
        except Exception as e:
            # TODO: Log stack trace to server for debugging
            raise xmlrpc.Fault(GENERAL_ERROR, str(e))
        return _unique(results)

    def xmlrpc_end_to_end_latency(self, path_id, results_id, n):
        """ Perform a path analysis to obtain the end-to-end latency.
        Requires that the system has been analyzed before
        to obtain the results_id.

        :param path_id: ID of the path
        :type path_id: string
        :param results_id: ID of the results
        :type results_id: string
        :param n: Number of activations to obtain the latency for
        :type n: integer
        :returns: best- and worst-case latency for n events along path.
        :rtype: tuple of integers
        """
        # TODO: add overheads?

        path = self._check_path_id(path_id)
        results = self._check_results_id(results_id)
        return path_analysis.end_to_end_latency(path, results, n)

    def xmlrpc_graph_system(self, system_id, filename):
        """ Generate a graph of the system (in server directory).

        :param system_id: ID of the system to analyze
        :type system_id: string
        :param filename: File name (relative to server working directory) to which to store the graph.
        :type filename: string
        :returns: 0

        """
        try:
            from pycpa import graph
        except ImportError:
            raise xmlrpc.Fault(GENERAL_ERROR, "graph not supported on this platform.")

        s = self._check_system_id(system_id)

        graph.graph_system(s, filename)
        return 0


