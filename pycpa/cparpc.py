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
from pycpa import graph

import logging

logger = logging.getLogger("xmlrpc")

def unique(obj):
    """ Returns a unique id for obj """
    return id(obj)


PYCPA_XMLRPC_VERSION = 1

GENERAL_ERROR = 1
INVALID_SCHEDULER = 2
INVALID_ID = 3
INVALID_EVENT_MODEL_DESC = 5
INVALID_RESULTS = 7
ILLEGAL_SYSTEM = 8
NOT_SCHEDULABLE = 9


class CPARPC(xmlrpc.XMLRPC):
    """ Basic XML RPC Server for pyCPA. """
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
        """ Return a reference to the task with task_id """
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
        """ create new pycpa system and return it's id """
        name = str(name)
        s = model.System(name)
        self._pycpa_systems[unique(s)] = s
        logger.debug("new system %s" % name)
        return unique(s)

    def xmlrpc_protocol(self):
        """ Return protocol version """
        return PYCPA_XMLRPC_VERSION

    def xmlrpc_new_resource(self, system_id, name):
        """ Create a new resource with name and bind it to a system. """
        system = self._check_system_id(system_id)
        name = str(name)
        r = model.Resource(name)
        logger.debug("new resource %s" % name)
        system.bind_resource(r)
        self._pycpa_resources[unique(r)] = r
        return unique(r)

    def xmlrpc_assign_scheduler(self, resource_id, scheduler_string):
        """ Assign a scheduler to a resource. """
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

    def xmlrpc_tasks_by_name(self, system_id, name):
        """ Return a list of tasks of system_id matching name """
        system = self._check_system_id(system_id)
        system_tasks = set()
        for r in system.resources:
            system_tasks += r.tasks

        return [task_id for task_id, task in self._pycpa_tasks.iteritems()
                if task in system_tasks and task.name == name]

    def xmlrpc_new_task(self, resource_id, name):
        """ Create a new task and bind it to a ressource. """
        resource = self._check_resource_id(resource_id)
        task = model.Task(str(name))
        task_id = unique(task)
        self._pycpa_tasks[task_id] = task
        resource.bind_task(task)
        return task_id

    def xmlrpc_set_task_parameter(self, task_id, attribute, value):
        """ Set the attribute of a task to value. """
        task = self._check_task_id(task_id)
        setattr(task, attribute, value)
        return 0

    def xmlrpc_get_task_parameter(self, task_id, attribute):
        """ Return the attribute of a task. """
        return getattr(self._pycpa_tasks[task_id], attribute)

    def xmlrpc_set_resource_parameter(self, resource_id, attribute, value):
        """ Set the attribute of a resource to value. """
        resource = self._check_resource_id(resource_id)
        setattr(resource, attribute, value)
        return 0

    def xmlrpc_get_resource_parameter(self, resource_id, attribute):
        """ Return the attribute of a resource. """
        return getattr(self._pycpa_resources[resource_id], attribute)

    def xmlrpc_link_task(self, task_id, target_id):
        """ Make task with target_id dependent of the task with task_id. """
        task = self._check_task_id(task_id)
        target = self._check_task_id(target_id)
        task.link_dependent_task(target)
        return 0

    def xmlrpc_new_path(self, system_id, name, task_ids):
        """ Adds a path consisting of a list of tasks to the system.
        Returns path id.
        """
        system = self._check_system_id(system_id)

        tasks = []
        for t_id in task_ids:
            t = self._check_task_id(t_id)
            tasks.append(t)

        p = model.Path(name, tasks)

        system.bind_path(p)
        self._pycpa_paths[unique(p)] = p
        return unique(p)

    def xmlrpc_assign_pjd_event_model(self, task_id, period, jitter, min_dist):
        """ Create an eventmodel and assign it to task. """
        task = self._check_task_id(task_id)
        em = None
        try:
            em = model.PJdEventModel(int(period), int(jitter), int(min_dist))
        except ValueError:
            raise xmlrpc.Fault(INVALID_EVENT_MODEL_DESC,
                               "invalid event model parametrization")
        task.in_event_model = em
        return 0

    def xmlrpc_get_task_result(self, results_id, task_id):
        """ Return a dictionary of results for task_id. """
        results = self._check_results_id(results_id)
        task = self._check_task_id(task_id)
        if task not in results:
            raise xmlrpc.Fault(INVALID_RESULTS, "no results for task")

        return results[task]

    def xmlrpc_analyze_system(self, system_id):
        """ Analyze system and return a result id. """
        system = self._pycpa_systems[system_id]
        results = None
        for r in system.resources:
            if r.scheduler is None:
                raise xmlrpc.Fault(ILLEGAL_SYSTEM,
                                   "component %s has no scheduler assigned"
                                   % r.name)
        try:
            results = analysis.analyze_system(system)
            self._task_results[unique(results)] = results
        except analysis.NotSchedulableException as e:
            raise xmlrpc.Fault(NOT_SCHEDULABLE, "not schedulable")
        except Exception as e:
            # TODO: Log stack trace to server for debugging
            raise xmlrpc.Fault(GENERAL_ERROR, str(e))
        return unique(results)

    def xmlrpc_end_to_end_latency(self, path_id, results_id, n):
        """ Returns best- and worst-case latency for n events along path. """
        # TODO: add overheads?

        path = self._check_path_id(path_id)
        results = self._check_results_id(results_id)
        return path_analysis.end_to_end_latency(path, results, n)

    def xmlrpc_graph_system(self, system_id, filename):
        """ Generate a graph of the system (in server directory). """
        s = self._check_system_id(system_id)

        graph.graph_system(s, filename)
        return 0


