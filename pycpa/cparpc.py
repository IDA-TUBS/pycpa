#!/usr/bin/env python
"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

XML-RPC server for pyCPA. It can be used to interface pycpa with
non-python (i.e. close-source) applications.
"""


from twisted.web import xmlrpc, server

from pycpa import model
from pycpa import analysis
from pycpa import options
from pycpa import schedulers

import logging

logger = logging.getLogger("xmlrpc")

def unique(obj):
    return id(obj)


PYCPA_XMLRPC_VERSION = 1

INVALID_SCHEDULER = 1
INVALID_SYSTEM = 2
INVALID_RESOURCE_ID = 3
INVALID_TASK_ID = 4
INVALID_EVENT_MODEL_DESC = 5
INVALID_EVENT_MODEL_TYPE = 6
INVALID_RESULTS = 7
ILLEGAL_SYSTEM = 8
NOT_SCHEDULABLE = 9

def check(func):
    """ check decorator
    looks for resource_id and task_id in the argument list of func.
    If found, it will check if there is a corresponding pycpa object,
    otherwise it will raise an xmlrpc.Fault
    """
    def inner(*args, **kwargs):
        self = args[0] # self is first by convention
        # always check system
        if self.pycpa_system is None:
            raise xmlrpc.Fault(INVALID_SYSTEM, "invalid system")
        return func(*args, **kwargs)
    return inner

class CPARPC(xmlrpc.XMLRPC):
    """An example object to be published."""
    def __init__(self, allowNone=False, useDateTime=False):
        xmlrpc.XMLRPC.__init__(self, allowNone, useDateTime)

        self.pycpa_system = None
        self.pycpa_resources = dict()
        self.pycpa_tasks = dict()
        self.pycpa_results = None
        self.scheduling_policies = {
                "spp" : schedulers.SPPScheduler}

    # TODO: can this become a private method?
    def check_task_id(self, task_id):
        if task_id not in self.pycpa_tasks:
            raise xmlrpc.Fault(INVALID_TASK_ID, "invalid task id")
        return self.pycpa_tasks[task_id]

    # TODO: can this become a private method?
    def check_resource_id(self, resource_id):
        if resource_id not in self.pycpa_resources:
            raise xmlrpc.Fault(INVALID_RESOURCE_ID, "invalid resource id")
        return self.pycpa_resources[resource_id]


    def xmlrpc_new_system(self, name):
        """ create new pycpa system"""
        name = str(name)
        self.pycpa_system = model.System(name)
        logger.debug("new system %s" %name)
        return unique(self.pycpa_system)

    def xmlrpc_protocol(self):
        return PYCPA_XMLRPC_VERSION

    @check
    def xmlrpc_new_resource(self, name):
        name = str(name)
        r = model.Resource(name)
        logger.debug("new resource %s" %name)
        self.pycpa_system.bind_resource(r)
        self.pycpa_resources[unique(r)] = r
        return unique(r)

    @check
    def xmlrpc_assign_scheduler(self, resource_id, scheduler_string):
        scheduler_string = str(scheduler_string)
        resource = self.check_resource_id(resource_id)
        scheduler = self.scheduling_policies.get(scheduler_string, None)
        if scheduler is None:
            logger.error("invalid scheduler %s selected" % (scheduler_string))
            raise xmlrpc.Fault(INVALID_SCHEDULER, "invalid scheduler")
        logger.debug("assigned policy %s to resource %s" % (scheduler_string, resource.name))
        resource.scheduler = scheduler()
        return 0

    @check
    def xmlrpc_tasks_by_name(self, name):
        return [task_id for task_id, task in self.pycpa_tasks.iteritems() if task.name == str(name)]

    @check
    def xmlrpc_new_task(self, resource_id, name):
        resource = self.check_resource_id(resource_id)
        task = model.Task(str(name))
        task_id = unique(task)
        self.pycpa_tasks[task_id] = task
        resource.bind_task(task)
        return task_id

    @check
    def xmlrpc_set_task_parameter(self, task_id, attribute, value):
        task = self.check_task_id(task_id)
        setattr(task, attribute, value)
        return 0

    @check
    def xmlrpc_get_task_parameter(self, task_id, param):
        return getattr(self.pycpa_tasks[task_id], param)

    @check
    def xmlrpc_link_task(self, task_id, target_id):
        task = self.check_task_id(task_id)
        target = self.check_task_id(target_id)
        task.link_dependent_task(target)
        return 0

    @check
    # TODO: refactor to assign_pjd_event_model
    def xmlrpc_assign_event_model(self, task_id, em_type, em_param):
        task = self.check_task_id(task_id)
        em = None
        if em_type == "PJd":
            try:
                period, jitter, min_dist = em_param.split(',')
                em = model.EventModel()
                em.set_PJd(int(period), int(jitter), int(min_dist))
            except ValueError:
                raise xmlrpc.Fault(INVALID_EVENT_MODEL_DESC, "invalid event model paramerization")
        else:
            raise xmlrpc.Fault(INVALID_EVENT_MODEL_TYPE, "invalid event model type")
        task.in_event_model = em
        return 0

    @check
    def xmlrpc_get_task_result(self, task_id):
        if self.pycpa_results is None:
            raise xmlrpc.Fault(INVALID_RESULTS, "no results available")
        task = self.check_task_id(task_id)
        if task not in self.pycpa_results:
            raise xmlrpc.Fault(INVALID_RESULTS, "no results for task")

        return self.pycpa_results[task]

    @check
    def xmlrpc_analyze_system(self):
        for r in self.pycpa_system.resources:
            if r.scheduler is None:
                raise xmlrpc.Fault(ILLEGAL_SYSTEM, "component %s has no scheduler assigned" % r.name)

        try:
            self.pycpa_results = analysis.analyze_system(self.pycpa_system)
        except analysis.NotSchedulableException as e:
            raise xmlrpc.Fault(NOT_SCHEDULABLE, "not schedulable")
        except Exception as e:
            return str(e)
        return 0

