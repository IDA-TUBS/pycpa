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
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import traceback

from twisted.web import xmlrpc

from pycpa import model
from pycpa import schedulers
from pycpa import analysis
from pycpa import path_analysis
from pycpa import graph

import logging

logger = logging.getLogger("xmlrpc")

PYCPA_XMLRPC_VERSION = 6

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

        # dictionary to store all object references
        self._objects = dict()

        #: Specifies how unique IDs are generated
        self.id_type = 'id_numeric'

        #: Dictionary of scheduler classes.
        self.scheduling_policies = {
                "spp" : schedulers.SPPScheduler
        }

        #: Prefix for function calls in debug output
        self.debug_prefix = 'proxy.'

    def _unique(self, obj):
        """ Returns a unique id for obj """

        if self.id_type == 'numeric':
            # Convert to string, because XML RPC does not support long ints
            return str(id(obj))

        if self.id_type == 'id_numeric':
            return 'id_{}'.format(id(obj))

        if isinstance(obj, dict):
            # results does not have a name property
            uid = 'results'
        else:
            uid = obj.name

        if self.id_type == 'full':
            #TODO: Prefix uid with full name
            raise NotImplementedError

        # Generate unique name by suffixing a number
        uid_base = uid
        suffix = 1
        while ((uid in self._objects) and
               (self._objects[uid] != obj)):
            # only generate a new ID if the duplicate isnt the obj
            uid = uid_base + str(suffix)
            suffix += 1

        return uid


    def _obj_from_id(self, identifier, check_type=None):
        """ Return a reference to the object with the supplied id.
        If check_type is not None, the object is checked to be of type check_type.
        """
        if identifier not in self._objects:
            raise xmlrpc.Fault(INVALID_ID, "invalid id '{0}'"
                               .format(identifier))
        else:
            obj = self._objects[identifier]
            if check_type is not None and not isinstance(obj, check_type):
                raise xmlrpc.Fault(INVALID_ID, "type of '{0}' is not {1}".
                                   format(obj, check_type))
        return obj


    def xmlrpc_set_id_type(self, id_type):
        ''' Select the type for returned IDs.
        'numeric' generates numeric IDs (strings of long int)
        'id_numeric' like 'numeric', but prefixes 'id_' (makes debug output executable)
        'name' generates the ID from the objects' name
        'full' is like 'name', but prefixes name by parent's name (TODO)

        In case of 'name' or 'full', the ID is suffixed in case of duplicates.

        :param id_type: 'numeric', 'id_numeric', 'name', or 'full'
        :type id_type: string
        :returns: 0
        '''
        if id_type in {'numeric', 'id_numeric', 'name', 'full'}:
            self.id_type = id_type
        else:
            raise xmlrpc.Fault(GENERAL_ERROR, 'invalid id type')
        return 0


    def xmlrpc_new_system(self, name):
        """ create new pycpa system and return it's id

        :param name: Name of the system.
        :type name: string
        :returns: ID of the created system
        :rtype: string

        """
        name = str(name)
        s = model.System(name)
        sid = self._unique(s)
        self._objects[sid] = s
        logger.debug("{} = {}new_system('{}')".format(sid, self.debug_prefix,
                                                      name))
        return sid

    def xmlrpc_protocol(self):
        """
        :returns: protocol version
        :rtype: integer
        """
        return PYCPA_XMLRPC_VERSION


    def xmlrpc_clear_models(self):
        """ Delete all models, i.e. all systems, resources, tasks, results etc.

        :returns: 0
        """
        self._objects.clear()
        logger.debug("{}clear_models()".format(self.debug_prefix))
        return 0

    def xmlrpc_new_resource(self, system_id, name):
        """ Create a new resource with name and bind it to a system.

        :param system_id: ID of the system
        :type system_id: string
        :param name: Name of the resurce.
        :type name: string
        :returns: ID of the created resource
        :rtype: string
        """
        system = self._obj_from_id(system_id, model.System)
        name = str(name)
        r = model.Resource(name)
        system.bind_resource(r)
        rid = self._unique(r)
        self._objects[rid] = r
        logger.debug("{} = {}new_resource({}, '{}')"
                     .format(rid, self.debug_prefix, system_id, name))
        return rid

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
        resource = self._obj_from_id(resource_id, model.Resource)
        scheduler = self.scheduling_policies.get(scheduler_string, None)
        if scheduler is None:
            logger.error("invalid scheduler %s selected" % (scheduler_string))
            raise xmlrpc.Fault(INVALID_SCHEDULER, "invalid scheduler")
        logger.debug("{}assign_scheduler({}, '{}')"
                     .format(self.debug_prefix, resource_id, scheduler_string))
        resource.scheduler = scheduler()
        return 0

    def xmlrpc_get_valid_schedulers(self):
        """ Find out which schedulers are supported.

        :returns: List of valid schedulers
        :rtype: list of strings
        """

        return self.scheduling_policies.keys()


    def xmlrpc_set_attribute(self, obj_id, attribute, value):
        ''' Set the attribute of the object to value.

        This method can be used to set any attribute
        of any previously created object.,
        However, each scheduler or analysis expects certain attributes
        that must be set and ignores all others.
        See scheduler documentation for details
        (e.g. :py:mod:`pycpa.schedulers`).

        :param obj_id: ID of the task to set the parameter for.
        :type obj_id: string
        :param attribute: Attribute to set.
        :type attribute: string.
        :param value: Value to set the attribute to
        :type value: Depends on attribute.
        :returns: 0
        '''
        obj = self._obj_from_id(obj_id)
        setattr(obj, attribute, value)
        logger.debug("{}set_attribute({}, {}, {})"
                     .format(self.debug_prefix, obj_id, attribute, value))
        return 0


    def xmlrpc_get_attribute(self, obj_id, attribute):
        """ Return the attribute of a task.

        :param obj_id: ID of the task to get the parameter from.
        :type obj_id: string
        :param attribute: Attribute to get.
        :type attribute: string.
        :returns: Value of the attribute
        :rtype: Depends on attribute.
        """
        return getattr(self._objects[obj_id], attribute)


    def xmlrpc_tasks_by_name(self, system_id, name):
        """
        :returns: a list of tasks of system_id matching name
        :rtype: list of strings
        """
        system = self._obj_from_id(system_id, model.System)
        system_tasks = set()
        for r in system.resources:
            system_tasks += r.tasks

        return [task_id for task_id, task in self._objects
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
        resource = self._obj_from_id(resource_id, model.Resource)
        task = model.Task(str(name))
        task_id = self._unique(task)
        self._objects[task_id] = task
        resource.bind_task(task)
        logger.debug("{} = {}new_task({}, '{}')"
                     .format(task_id, self.debug_prefix, resource_id, name))
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
        logger.warn("Method set_task_parameter() is deprecated,"
                    " use set_attribute() instead!")
        task = self._obj_from_id(task_id, model.Task)
        setattr(task, attribute, value)
        logger.debug("{}set_task_parameter({}, {}, {})"
                     .format(self.debug_prefix, task_id, attribute, value))
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
        logger.warn("Method get_task_parameter() is deprecated,"
                    " use get_attribute() instead!")
        return getattr(self._objects[task_id], attribute)

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
        logger.warn("Method set_resource_parameter() is deprecated,"
                    " use set_attribute() instead!")
        resource = self._obj_from_id(resource_id, model.Resource)
        setattr(resource, attribute, value)
        logger.debug("{}set_resource_parameter({}, {}, {})"
                     .format(self.debug_prefix, resource_id, attribute, value))
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
        logger.warn("Method get_resource_parameter() is deprecated,"
                    " use get_attribute() instead!")
        return getattr(self._objects[resource_id], attribute)

    def xmlrpc_link_task(self, task_id, target_id):
        """ Make task with target_id dependent of the task with task_id.

        :param task_id: ID of the task that activates the target task
        :type task_id: string
        :param target_id: ID of the task that is activate by the task.
        :type target_id: string
        :returns: 0

        """
        task = self._obj_from_id(task_id, model.Task)
        target = self._obj_from_id(target_id, model.Task)
        task.link_dependent_task(target)
        logger.debug("{}link_task({}, {})"
                     .format(self.debug_prefix, task_id, target_id))
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
        system = self._obj_from_id(system_id, model.System)

        tasks = []
        for t_id in task_ids:
            t = self._obj_from_id(t_id, model.Task)
            tasks.append(t)

        p = model.Path(name, tasks)

        system.bind_path(p)
        pid = self._unique(p)
        self._objects[pid] = p
        logger.debug("{} = {}new_path({}, '{}', {})"
                     .format(pid, self.debug_prefix,
                             system_id, name, task_ids))
        return pid

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
        task = self._obj_from_id(task_id, model.Task)
        em = None
        try:
            em = model.PJdEventModel(int(period), int(jitter), int(min_dist))
        except ValueError:
            raise xmlrpc.Fault(INVALID_EVENT_MODEL_DESC,
                               "invalid event model parametrization")
        task.in_event_model = em

        # casting to int in debug output so that it matches what our code
        # actually does to the input
        logger.debug("{}assign_pjd_event_model({}, {}, {}, {})".
                     format(self.debug_prefix, task_id,
                            int(period), int(jitter), int(min_dist)))
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
        task = self._obj_from_id(task_id, model.Task)
        em = None
        try:
            em = model.CTEventModel(int(c), int(T), int(min_dist))
        except ValueError:
            raise xmlrpc.Fault(INVALID_EVENT_MODEL_DESC,
                               "invalid event model parametrization")
        task.in_event_model = em
        logger.debug("{}assign_ct_event_model({}, {}, {}, {})".
                     format(self.debug_prefix, task_id, c, T, min_dist))
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
        results = self._obj_from_id(results_id, dict)
        task = self._obj_from_id(task_id, model.Task)
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
        system = self._obj_from_id(system_id, model.System)
        results = None
        for r in system.resources:
            if r.scheduler is None:
                raise xmlrpc.Fault(ILLEGAL_SYSTEM,
                                   "component %s has no scheduler assigned"
                                   % r.name)

        logger.debug("analyzing...")
        try:
            results = analysis.analyze_system(system)
            rid = self._unique(results)
            self._objects[rid] = results
        except analysis.NotSchedulableException as e:
            raise xmlrpc.Fault(NOT_SCHEDULABLE, "not schedulable")
        except Exception as e:
            # Print the exception plus traceback to server
            traceback.print_exc()
            raise xmlrpc.Fault(GENERAL_ERROR, str(e))
        logger.debug("{} = {}analyze_system({})".
                     format(rid, self.debug_prefix, system_id))
        return rid

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

        path = self._obj_from_id(path_id, model.Path)
        results = self._obj_from_id(results_id, dict)
        latencies = path_analysis.end_to_end_latency(path, results, n)
        logger.debug("{} = {}end_to_end_latency({}, {}, {})"
                     .format(latencies, self.debug_prefix,
                             path_id, results_id, n))
        return latencies

    def xmlrpc_graph_system(self, system_id, filename):
        """ Generate a graph of the system (in server directory).
        It uses graphviz for plotting, so the 'dot' command must be in the PATH
        of the server environment.

        :param system_id: ID of the system to analyze
        :type system_id: string
        :param filename: File name (relative to server working directory) to which to store the graph.
        :type filename: string
        :returns: 0

        """
        try:
            import pygraphviz
        except ImportError:
            raise xmlrpc.Fault(GENERAL_ERROR, "graph not supported on this platform.")

        s = self._obj_from_id(system_id, model.System)

        graph.graph_system(s, filename)
        return 0


    def xmlrpc_graph_system_dot(self, system_id, filename):
        """ Generate a graph of the system in dot file format (in server directory).
        The resulting file can be converted using graphviz.
        E.g. to create a PDF, run:
           dot -Tpdf <filename> -o out.pdf

        :param system_id: ID of the system to analyze
        :type system_id: string
        :param filename: File name (relative to server working directory) to which to write to. If empty, return dot file as string only.
        :type filename: string
        :returns: string representation of graph in dot format
        :rtype: string
        """

        s = self._obj_from_id(system_id, model.System)

        if filename == '':
            filename = None

        g = graph.graph_system(s, dotout=filename)
        return g.string()

