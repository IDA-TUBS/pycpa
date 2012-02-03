"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Symta 1.4 loader
"""


try:
    import xml.dom.minidom
except ImportError:
    print "Sorry, you don't have the minidom module installed."
    print "Please install or reconfigure minidom"
    print "and try again."
    exit(1)

import model
import fifo
import spp
import spnp
import roundrobin

import logging

logger = logging.getLogger("symta_loader")

class InvalidSymtaXMLException (Exception):
    def __init__(self, value, dom_node):
        self.value = value
        self.dom_node = dom_node
    def __str__(self):
        return repr(self.value + " in node " % self.dom_node.nodeName)

class SymtaLoader14:
    """ a simple SymTA/S xml loader
        reverse engineered sources, implements only a functional subset
    """
    def __init__(self):
        self.system = model.System()

        ## tasks in the system
        self.tasks = set()

        ## name -> task map
        self.task_map = dict()

        ## resources in the system
        self.resources = set()

        ## name -> resource map
        self.resources_map = dict()

        ## we will just store the EventModel as a source
        self.sources = set()

        ## name -> sources map
        self.sources_map = dict()

    def parse(self, filename):
        self.system.dom_node = xml.dom.minidom.parse(filename)
        self._handle_symta_system(self.system.dom_node)
        return self.system

    def _handle_symta_system(self, symtasystem_node):

        application_node = symtasystem_node.getElementsByTagName("application")[0]
        self._handle_application(application_node)

        architecture_node = symtasystem_node.getElementsByTagName("architecture")[0]
        self._handle_architecture(architecture_node)

        mapping_node = symtasystem_node.getElementsByTagName("mapping")[0]
        self._handle_mapping(mapping_node)

        observedpaths_node = symtasystem_node.getElementsByTagName("observedpaths")[0]

    def _handle_mapping(self, mapping_node):
        mappings = mapping_node.getElementsByTagName("map:task")
        for map in mappings:
            task_name = map.attributes['name'].nodeValue
            task = self.task_map[task_name]

            actual_mapping_node = map.getElementsByTagName("actualMapping")[0]
            schedparam_node = actual_mapping_node.getElementsByTagName("schedparam")[0]

            task.scheduling_parameter = int(schedparam_node.attributes['priority'].nodeValue)

            resource_name = actual_mapping_node.attributes['name'].nodeValue

            resource = self.resources_map[resource_name]

            assert resource in self.system.resources

            resource.bind_task(task)

            assert task in resource.tasks
            task.bcet *= resource.speedup
            task.wcet *= resource.speedup

            logger.info("task %s, sched_param %d is mapped to %s", task.name, task.scheduling_parameter, resource_name)

    def _handle_architecture(self, architecture_node):
        cpu_nodes = architecture_node.getElementsByTagName("cpu")
        for cpu_node in cpu_nodes:
            resource = self._handle_cpu(cpu_node)


    def _handle_cpu(self, cpu_node):
        resource_name = cpu_node.attributes['name'].nodeValue
        resource = self.system.add_resource(resource_name)

        scheduler_string = cpu_node.attributes['scheduler'].nodeValue
        if scheduler_string == "(IDA)spp" or  scheduler_string == "spp":
            resource.w_function = spp.w_spp
        elif scheduler_string == "(IDA)roundrobin" or scheduler_string == "roundrobin":
            resource.w_function = roundrobin.w_roundrobin
        elif scheduler_string == "fifo": # not sure if symta actually has a fifo scheduler
            resource.w_function = fifo.w_fifo
        elif scheduler_string == "(IDA)spp" or scheduler_string == "spnp":
            resource.w_function = spnp.w_spnp
        else:
            raise InvalidSymtaXMLException("Scheduler %s is not compatible with pycpa" % scheduler_string)

        speedup_node = cpu_node.getElementsByTagName("speedup")[0]
        speedup = self._handle_speedup(speedup_node)
        resource.speedup = speedup

        self.resources.add(resource)
        self.resources_map[resource.name] = resource


        logger.info("new resource %s, speedup %f" % (str(resource.name), speedup))
        return resource

    def _handle_application(self, application_node):
        tasks = application_node.getElementsByTagName("task")
        for taskNode in tasks:
            self._handle_task(taskNode)

        sources = application_node.getElementsByTagName("source")
        for sourceNode in sources:
            self._handle_source(sourceNode)

        eventstream_nodes = application_node.getElementsByTagName("eventstream")
        for eventstream_node in eventstream_nodes:
            self._handle_eventstream(eventstream_node)

    def _handle_eventstream(self, eventstream_node):
        name = eventstream_node.attributes['name'].nodeValue

        src_node = eventstream_node.getElementsByTagName('src')[0];
        src_name = src_node.attributes['process'].nodeValue
        src_type_name = src_node.attributes['type'].nodeValue

        target_node = eventstream_node.getElementsByTagName('target')[0]
        target_name = target_node.attributes['process'].nodeValue
        target_type_name = target_node.attributes['type'].nodeValue

        target = None
        if target_type_name == "task":
            target = self.task_map[target_name]
        elif target_type_name == "sink":
            logging.info("skipping event stream %s with sink target %s" % (name, target_name))

        if src_type_name == "source":
            assert target is not None
            src_em = self.sources_map[src_name]
            target.in_event_model = src_em
            logging.info("%s: assinged event model %s to task %s" % (name, str(src_em), target.name))
        elif src_type_name == "task":
            src = self.task_map[src_name]
            if target is not None:
                src.link_dependent_task(target)
                logging.info("%s: linked %s -> %s" % (name, src.name, target.name))

    def _handle_task(self, task_node):
        assert task_node.nodeName == "task"
        name = task_node.attributes["name"].nodeValue
        ports = task_node.getElementsByTagName("ports")[0] #take first
        speedup = self._handle_speedup(task_node.getElementsByTagName("speedup")[0]) #take first
        bcet, wcet = self._handle_tcore(task_node.getElementsByTagName("tCore")[0]) #take first
        bcet *= speedup
        wcet *= speedup
        #inport_list, outport_list = self._handle_ports(ports)
        logger.info("new task %s, tcore: [%f, %f] speedfactor %f" % (name, bcet, wcet, speedup))
        task = model.Task(name = name, bcet = bcet, wcet = wcet, sched_param = None)
        task.dom_node = task_node
        task.ports = ports # used later to connect the event streams
        self.tasks.add(task)
        self.task_map[name] = task

    def _handle_tcore(self, tCoreNode):
        return self._handle_time_interval(tCoreNode.getElementsByTagName("timeinterval")[0])

    def _handle_time_interval(self, timeIntervalNode):
        assert timeIntervalNode.nodeName == "timeinterval"
        timevalues = timeIntervalNode.getElementsByTagName("timevalue")
        lower = self._handle_time_value(timevalues[0])
        upper = self._handle_time_value(timevalues[1])
        return (lower, upper)

    def _handle_time_value(self, timeNode):
        # loss of precison due to hard coded devision
        assert timeNode.nodeName == "timevalue"
        numerator = float(timeNode.attributes["numerator"].nodeValue)
        denominator = float(timeNode.attributes["denominator"].nodeValue)
        return numerator / denominator

    def _handle_source(self, sourceNode):
        assert sourceNode.nodeName == "source"
        name = sourceNode.attributes['name'].nodeValue
        ports = sourceNode.getElementsByTagName("ports")[0]
        inport_list, outport_list = self._handle_ports(ports)
        port_name, em = outport_list[0]
        em.name = name
        self.sources.add(em)
        self.sources_map[name] = em
        #graph_extension_container = sourceNode.getElementsByTagName("GraphElementExtensionContainer")[0]

        logger.info("new source %s %s" % (name, str(em)))

    def _handle_ports(self, portsNode):
        inport_list = list()
        outport_list = list()
        # we assume there is only one port
        outports = portsNode.getElementsByTagName("outputport")
        for outportNode in outports:
            propagation_container = outportNode.getElementsByTagName("PropagationContainer")[0]
            event_model = self._handle_propagation_container(propagation_container)
            name = outportNode.attributes["name"].nodeValue
            outport_list.append((name, event_model))

        inports = portsNode.getElementsByTagName("inputport")
        for inportNode in inports:
            name = inportNode.attributes["name"].nodeValue
            event_model = self._handle_propagation_container(inportNode.getElementsByTagName("PropagationContainer")[0])
            inport_list.append((name, event_model))
        return inport_list, outport_list

    def _handle_propagation_container(self, propagationContainerNode):

        #just grab the event model
        print propagationContainerNode.nodeName
        print propagationContainerNode.nodeValue
        propagationElement = propagationContainerNode.getElementsByTagName("PropagationElements")[0]
        event_model_propagation_element = propagationElement.getElementsByTagName("EventModelPropagationElement")[0]
        myEventModel = event_model_propagation_element.getElementsByTagName("myEventModel")[0]
        standardeventmodel = myEventModel.getElementsByTagName("standardeventmodel")[0]
        return self._handle_standardeventmodel(standardeventmodel)

    def _handle_standardeventmodel(self, standardeventmodel_node):
        assert standardeventmodel_node.nodeName == "standardeventmodel"
        eventmodeltype = standardeventmodel_node.getElementsByTagName("eventmodeltype")[0]

        period_node = standardeventmodel_node.getElementsByTagName("period")[0]
        period = self._handle_time_value(period_node.childNodes[1])

        jitter_node = standardeventmodel_node.getElementsByTagName("jitter")[0]
        jitter = self._handle_time_value(jitter_node.childNodes[1])

        mindist_node = standardeventmodel_node.getElementsByTagName("minDist")[0]
        mindist = self._handle_time_value(mindist_node.childNodes[1])

        em = model.EventModel()
        em.set_PJd(period, jitter, mindist)
        em.dom_node = standardeventmodel_node

        return em

    def _handle_speedup(self, speedup):
        factor = speedup.attributes['factor']
        return float(factor.nodeValue)

class SymtaWriter:
    """ not implemented """
    pass
