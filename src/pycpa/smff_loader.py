"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

SMFF import/annotate
"""


import xml.dom.minidom

import options

import model
import fifo
import spp
import spnp
import roundrobin

import logging

logger = logging.getLogger("smff_loader")

def _calc_in_out_jitter(task_model):
    in_jitter = 0
    source_task = task_model
    while source_task.prev_task is not None:
        source_task = source_task.prev_task
        in_jitter += source_task.wcrt - source_task.bcrt
    in_jitter += source_task.in_event_model.J
    out_jitter = in_jitter + task_model.wcrt - task_model.bcrt
    return in_jitter, out_jitter


class InvalidSMFFXMLException (Exception):
    def __init__(self, value, dom_node):
        self.value = value
        self.dom_node = dom_node
    def __str__(self):
        return repr(self.value + " in node " % self.dom_node.nodeName)


class SMFFApplication:
    def __init__(self, xml_node=None):

        ## corresponding dom node
        self.xml_node = xml_node

        ## application name
        self.name = "none"

        ## application id
        self.id = -1

        ## set of tasks and tasklinks in the application (if they are mapped to a comm resource)
        self.tasks_pycpa = set()

        ## set of tasklinks in the application
        self.links_pycpa = set()

        ## resolve name mappings
        self.id_to_link_pycpa = dict()
        self.id_to_task_pycpa = dict()

        # task to resource mapping, TaskID -> ResourceID
        self.task_mapping = dict()
        self.task_link_mapping = dict()

class SMFFLoader:
    """ a simple SMFF xml loader
    reverse engineered sources, implements only a functional subset
    """
    def __init__(self):
        self.system = model.System()

        ## the root dom node
        self.xml_root = None

        ## the smff applications
        self.smff_applications = set()

        ## all cpu resources in the system
        self.resources_pycpa = set()

        ## all communication resources in the system
        self.comm_resources_pycpa = set()

        ## resolve name mappings
        self.id_to_resource_pycpa = dict()
        self.id_to_comm_resource_pycpa = dict()
        self.id_to_smff_applications = dict()

    def parse(self, filename):

        self.xml_root = xml.dom.minidom.parse(filename)

        #  save xml_root node in the system model 
        self.system.xml_node = self.xml_root

        self._handle_system_model(self.xml_root)
        return self.system

    def _handle_system_model(self, system_model_node):
        #  skip the configuration node
        #---

        #  parse the platform node
        platform_node = system_model_node.getElementsByTagName("Platform")[0]
        self._handle_platform(platform_node)

        #  parse the applications node
        applications_node = system_model_node.getElementsByTagName("Applications")[0]
        self._handle_applications(applications_node)

    def _handle_platform(self, platform_node):
        for resource_node in platform_node.getElementsByTagName("Resource"):
            self._handle_resource(resource_node)

        for comm_resource_node in platform_node.getElementsByTagName("CommResource"):
            self._handle_comm_resource(comm_resource_node)

    def _w_func_from_scheduler_string(self, scheduler):
        """ parse the scheduling string and return a window function
        """
        if scheduler == "SPPScheduler":
            return spp.w_spp
        if scheduler == "SPNPScheduler":
            return spnp.w_spnp

        return None

    def _handle_resource(self, resource_node):
        """
        <Resource shortName="ResId:2" resID="2">
        <attachedTo ID="1"/>
        <ResourceType name="GenericResourceType"/>
        <ResourceGroup name="GenericResourceGroup"/>
        <Scheduler name="SPPScheduler"/>
        </Resource>
        """
        # ResourceType and ResourceGroup are skipped
        # parse names
        short_name = resource_node.attributes["shortName"].nodeValue
        resource_id = int(resource_node.attributes["resID"].nodeValue)

        # get scheduler node
        scheduler_node = resource_node.getElementsByTagName("Scheduler")[0]
        scheduler_string = scheduler_node.attributes["name"].nodeValue

        w_func = self._w_func_from_scheduler_string(scheduler_string)

        if w_func == None:
            raise InvalidSMFFXMLException("Scheduler not recognized", scheduler_node)

        # add a resource to pycpa
        resource_model = self.system.add_resource(short_name, w_func)
        resource_model.xml_node = resource_node
        resource_model.smff_id = resource_id

        # map id to pycpa model
        self.id_to_resource_pycpa[resource_id] = resource_model

    def _handle_comm_resource(self, comm_resource_node):
        # ResourceType and ResourceGroup are skipped
        # parse names
        short_name = comm_resource_node.attributes["shortName"].nodeValue
        resource_id = int(comm_resource_node.attributes["resID"].nodeValue)

        # get scheduler node
        scheduler_node = comm_resource_node.getElementsByTagName("Scheduler")[0]
        scheduler_string = scheduler_node.attributes["name"].nodeValue

        w_func = self._w_func_from_scheduler_string(scheduler_string)

        if w_func == None:
            raise InvalidSMFFXMLException("Scheduler not recognized", scheduler_node)

        # add a resource to pycpa
        resource_model = self.system.add_resource(short_name, w_func)
        resource_model.xml_node = comm_resource_node
        resource_model.smff_id = resource_id

        # map id to pycpa model
        self.id_to_comm_resource_pycpa[resource_id] = resource_model

    def _handle_applications(self, applications_node):
        for application_node in applications_node.getElementsByTagName("Application"):
           self._handle_application(application_node)

        # check mapping sanity
        for resource_model in self.system.resources:
            if len(resource_model.tasks) == 0:
                logger.warn("no tasks on %s. that's odd" % resource_model.name)

    def _handle_application(self, application_node):
        smff_application = SMFFApplication(application_node)
        self.smff_applications.add(smff_application)

        smff_application.name = application_node.attributes["appID"].nodeValue
        smff_application.id = int(application_node.attributes["appV"].nodeValue)

        mapping_node = application_node.getElementsByTagName("Mapping")[0]
        self._handle_mapping(mapping_node, smff_application)

        for task_node in application_node.getElementsByTagName("Task"):
            self._handle_task(task_node, smff_application)

        for task_link_node in application_node.getElementsByTagName("TaskLink"):
            self._handle_task_link(task_link_node, smff_application)

        for (lid, task_model) in smff_application.id_to_link_pycpa.items():

            rid = smff_application.task_link_mapping[lid]

            resource_model = self.id_to_comm_resource_pycpa[rid]
            task_model.bind_resource(resource_model)

        for (tid, task_model) in smff_application.id_to_task_pycpa.items():

            rid = smff_application.task_mapping[tid]
            resource_model = self.id_to_resource_pycpa[rid]
            task_model.bind_resource(resource_model)

    def _handle_scheduling_parameter(self, scheduling_parameter_node, task_pycpa):
        # <SchedulingParameter name="SchedulingPriority" priority="5"/>
        name = scheduling_parameter_node.attributes["name"].nodeValue
        if name == "SchedulingPriority":
            priority = int(scheduling_parameter_node.attributes["priority"].nodeValue)
            task_pycpa.scheduling_parameter = priority
        else:
            raise InvalidSMFFXMLException("scheduling policy not recognized", scheduling_parameter_node)

    def _handle_activation_pattern(self, activation_pattern_node, task_model):
        # parse event model

        name = activation_pattern_node.attributes["name"].nodeValue
        if name == "PJActivation":
            ## source
            jitter = int(activation_pattern_node.attributes["activationJitter"].nodeValue)
            period = int(activation_pattern_node.attributes["activationPeriod"].nodeValue)
            em = model.EventModel(P=period, J=jitter)
            task_model.in_event_model = em
            return

        if name == "EventActivation":
            return None

        raise InvalidSMFFXMLException("activation pattern not recognized", activation_pattern_node)

    def _handle_profile(self, profile_node, task_model):
        active = bool(profile_node.attributes["active"].nodeValue)
        if not active:
            return

        activation_pattern_node = profile_node.getElementsByTagName("ActivationPattern")[0]
        self._handle_activation_pattern(activation_pattern_node, task_model)

        wcet = int(profile_node.attributes["wcet"].nodeValue)
        bcet = int(profile_node.attributes["bcet"].nodeValue)

        task_model.wcet = wcet
        task_model.bcet = bcet

    def _handle_task(self, task_node, smff_application):

        # parse names
        short_name = task_node.attributes["shortName"].nodeValue
        task_id = int(task_node.attributes["ID"].nodeValue)

        # create the task
        task_model = model.Task(name=short_name)
        task_model.xml_node = task_node
        task_model.smff_id = task_id

        # parse scheduling parameter

        scheduling_parameter_node = task_node.getElementsByTagName("SchedulingParameter")[0]
        self._handle_scheduling_parameter(scheduling_parameter_node, task_model)

        for profile_node in task_node.getElementsByTagName("Profile"):
            self._handle_profile(profile_node, task_model)

        # register the id
        smff_application.id_to_task_pycpa[task_id] = task_model

        # add task to application pool
        smff_application.tasks_pycpa.add(task_model)


    def _handle_task_link(self, task_link_node, smff_application):
        """<TaskLink shortName="A4TL0-1" ID="0" wcet="2147483647" bcet="0" msgCount="1" msgSize="1" trgt="1" src="0">
        <SchedulingParameter name="SchedulingPriority" priority="-1"/>
        </TaskLink>
        """
        short_name = task_link_node.attributes["shortName"].nodeValue
        link_id = int(task_link_node.attributes["ID"].nodeValue)

        trgt_id = int(task_link_node.attributes["trgt"].nodeValue)
        src_id = int(task_link_node.attributes["src"].nodeValue)

        trgt_pycpa = smff_application.id_to_task_pycpa[trgt_id]
        src_pycpa = smff_application.id_to_task_pycpa[src_id]

        # get mapping of this link

        if link_id in smff_application.task_link_mapping:

            # create pycpa object
            task_model = model.Task(name=short_name)
            task_model.smff_id = link_id
            task_model.xml_node = task_link_node

            # parse scheduling parameter
            scheduling_parameter_node = task_link_node.getElementsByTagName("SchedulingParameter")[0]
            self._handle_scheduling_parameter(scheduling_parameter_node, task_model)

            for profile_node in task_link_node.getElementsByTagName("Profile"):
                self._handle_profile(profile_node, task_model)

            # register id -> pycpa model mapping
            smff_application.id_to_link_pycpa[link_id] = task_model

            # link all tasks: src -> link -> trgt
            src_pycpa.link_dependent_task(task_model)
            task_model.link_dependent_task(trgt_pycpa)

        else:
            #no task just link src and trgt
            src_pycpa.link_dependent_task(trgt_pycpa)

    def _handle_mapping(self, mapping_node, smff_application):
        """-<Mapping>
        <mapTask rid="0" tid="2"/>
        <mapTask rid="0" tid="1"/>
        <mapTask rid="0" tid="0"/>
        <mapLink rid="0" lid="1"/>
        <mapLink rid="0" lid="0"/>
        </Mapping>"""

        for maptask_node in mapping_node.getElementsByTagName("mapTask"):
            rid = int(maptask_node.attributes["rid"].nodeValue)
            tid = int(maptask_node.attributes["tid"].nodeValue)
            smff_application.task_mapping[tid] = rid

        for maptasklink_node in mapping_node.getElementsByTagName("mapLink"):
            ## tricky: when task_link is mapped to a comm_resource (a crid attribute exists)
            ## we map the link as a pycpa task 
            crid_attr = maptasklink_node.getAttributeNode("crid")
            lid = int(maptasklink_node.attributes["lid"].nodeValue)
            if crid_attr is not None:
                crid = int(maptasklink_node.attributes["crid"].nodeValue)
                smff_application.task_link_mapping[lid] = crid
            else:
                rid = int(maptasklink_node.attributes["rid"].nodeValue)
                logger.info("decided to skip link id %d, because it is mapped to computing resource %d" % (lid, rid))


    def _annotate_task(self, task_result_node, task_model, smff_application):

        in_jitter, out_jitter = _calc_in_out_jitter(task_model)

        task_result_node.setAttribute("name", str(task_model.name))
        task_result_node.setAttribute("id", str(task_model.smff_id))
        task_result_node.setAttribute("wcrt", str(task_model.wcrt))
        task_result_node.setAttribute("bcrt", str(task_model.bcrt))
        task_result_node.setAttribute("input_jitter", str(in_jitter))
        task_result_node.setAttribute("output_jitter", str(out_jitter))

    def _annotate_resource(self, resources_result_node, resource_model):
        resource_result_node = None

        if resource_model.xml_node.tagName == "Resource":
            resource_result_node = self.xml_root.createElement("Resource")
        elif resource_model.xml_node.tagName == "CommResource":
            resource_result_node = self.xml_root.createElement("CommResource")
        else:
            raise InvalidSMFFXMLException("Invalid resource xml description", resource_model.xml_node)

        resources_result_node.appendChild(resource_result_node)

        resource_result_node.setAttribute("name", str(resource_model.name))
        resource_result_node.setAttribute("ID", str(resource_model.smff_id))
        resource_result_node.setAttribute("load", str(resource_model.load()))

    def _annotate_resources(self, analysis_node):
        resources_result_node = self.xml_root.createElement("Resources")
        analysis_node.appendChild(resources_result_node)

        for resource_model in self.system.resources:
            self._annotate_resource(resources_result_node, resource_model)

    def _annotate_tasks(self, application_node, smff_application):
        for task_model in smff_application.tasks_pycpa:
            task_result_node = None
            if task_model.xml_node.tagName == "Task":
                task_result_node = self.xml_root.createElement("Task")
                application_node.appendChild(task_result_node)
            elif task_model.xml_node.tagName == "TaskLink":
                task_result_node = self.xml_root.createElement("TaskLink")
                application_node.appendChild(task_result_node)
            else:
                raise InvalidSMFFXMLException("Invalid task xml description", task_model.xml_node)
            self._annotate_task(task_result_node, task_model, smff_application)

    def _annotate_applications(self, analysis_node):
        applications_result_node = self.xml_root.createElement("Applications")
        analysis_node.appendChild(applications_result_node)

        for smff_application in self.smff_applications:
            self._annotate_application(applications_result_node, smff_application)

    def _annotate_application(self, applications_result_node, smff_application):
        application_result_node = self.xml_root.createElement("Application")
        applications_result_node.appendChild(application_result_node)

        application_result_node.setAttribute("appV", str(smff_application.name))
        application_result_node.setAttribute("appID", str(smff_application.id))

        self._annotate_tasks(application_result_node, smff_application)

    def annotate_results(self):
        analysis_node = None

        ## remove old analysis results
        while len(self.xml_root.childNodes[0].getElementsByTagName("Analysis")) > 0:
            analysis_node = self.xml_root.childNodes[0].getElementsByTagName("Analysis")[0]
            self.xml_root.childNodes[0].removeChild(analysis_node)

        analysis_node = self.xml_root.createElement("Analysis")
        self.xml_root.childNodes[-1].appendChild(analysis_node)

        for option, attr in options.opts_dict.items():
            analysis_node.setAttribute(option, attr)

        self._annotate_resources(analysis_node)
        self._annotate_applications(analysis_node)


    def write(self, filename):
        f = open(filename, 'w')
        self.xml_root.writexml(f)
        f.close()
