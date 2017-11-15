import xml.etree.ElementTree as ET
import networkx as nx
from . import util
from . import model
from . import schedulers

import csv

xsi='{http://www.w3.org/2001/XMLSchema-instance}'
XSI_TYPE='{http://www.w3.org/2001/XMLSchema-instance}type'

MAPPING = 'mapping'
ACCESS = 'ACCESS'
READ = 'read'
WRITE = 'write'
TASK = 'task'
RUNNABLE = 'runnable'
LABEL = 'label'
RESSOURCE = 'ressource'
TYPE = 'TYPE'
PRIO = 'scheduling_parameter'


class NxAmaltheaParser(object):
    def __init__(self, xml_file, scale=1.0):

        root = ET.parse(xml_file).getroot()
        self.mappingModel= root.find('mappingModel')
        self.sw_model = root.find('swModel')
        self.hw_model = root.find('hwModel')
        self.stim_model = root.find('stimuliModel')
        self.constr_model = root.find('constraintsModel')
        self.os_model = root.find('osModel')

        self.time_base = util.ns
        self.scale = scale
        self.time_per_instruction = self._set_time_per_instruction() 

        self.G = nx.MultiDiGraph()

    def clean_xml_string(self, s=None):
        #remove type substring from xml strings
        return s[:s.index('?')]

    def parse_runnables_and_labels_to_nx(self):
        for r in self.sw_model.iter('runnables'):
            r_name = r.get('name')
            bcet = int(float(r.find('runnableItems/default/deviation/lowerBound').get('value')) * float(self.time_per_instruction) * self.scale)
            wcet = int(float(r.find('runnableItems/default/deviation/upperBound').get('value')) * float(self.time_per_instruction) * self.scale)

            #self.G.add_node(r_name, **{ 'bcet' : bcet , 'wcet' : wcet , TYPE : RUNNABLE })
            self.G.add_node(r_name, bcet= bcet , wcet=wcet, TYPE = RUNNABLE )
            #Adding a label/runnable multiple times doesn't matter.
            #Every "node" is a hashable object, i.e. the string identfying the node
            for ri in r.iter('runnableItems'):
                value = ri.get(XSI_TYPE)
                if value:
                    prefix, tag = value.split(":")
                    if tag == 'LabelAccess':
                        label = self.clean_xml_string(ri.get('data'))
                        self.G.add_node(label, TYPE = LABEL)
                        
                        access = ri.get('access')
                        if access == "read":
                            self.G.add_edge(label,r_name,TYPE = ACCESS, ACCESS = READ)
                        else:
                            self.G.add_edge(r_name,label,TYPE = ACCESS, ACCESS = WRITE)
        return self.G

    def _number_of_labels_in_xml(self):
        n = 0 
        for label in self.sw_model.iter('labels'):
            n = n + 1
            if not self.G.has_node(label.get('name')):
                print("%s not in the Graph" % label.get('name'))
        return n



    def _get_stimulus_params(self, stimulus):
        _,stim_type = stimulus.get(XSI_TYPE).split(':')
        s_param = dict()
        if stim_type == "Periodic":
            #returns a dict vwith value and unit as keys
            s_param = stimulus.find('recurrence').attrib
        elif stim_type == "Sporadic":
            s_param['lowerBound'] = stimulus.find('stimulusDeviation').find('lowerBound').attrib
            s_param['upperBound'] = stimulus.find('stimulusDeviation').find('upperBound').attrib
        else:
            raise ValueError
        s_param['EMType'] = stim_type
        return s_param
    

    def parse_tasks_and_cores_to_nx(self):
        for t in self.sw_model.iter('tasks'):
            t_name = t.get('name')
            t_prio = t.get('priority')
            # find event model
            stimulus_name = self.clean_xml_string(t.get('stimuli'))
            for  stimulus in self.stim_model.iter('stimuli'):
                if stimulus.get('name') == stimulus_name:
                    stim_params = self._get_stimulus_params(stimulus)
            
            self.G.add_node(t_name, TYPE=TASK, event_model=stim_params, scheduling_parameter=t_prio)

            #Map task to runnables
            graphEntries = t.find('callGraph/graphEntries')
            prefix,tag =  graphEntries.get(XSI_TYPE).split(":")
            if tag == 'CallSequence':
                for call in graphEntries.iter('calls'):
                    #each runnable is linked to a task
                    r = self.clean_xml_string(call.get('runnable'))
                    self.G.add_edge(r,t_name, TYPE=MAPPING)
                    self.G.add_edge(t_name,r, TYPE=MAPPING)

        #TODO: In principle this is right but we omit the indirection and assume the Scheduler to be the
        #core
        #for core in self.hw_model.find('system/ecus/microcontrollers').iter('cores'):
        #    c_name = core.get('name')
        #    self.G.add_node(c_name)

        #Get all the schedulers in the Model - typically one per core; shortcut for task allocation
        for sched in self.os_model.find('operatingSystems').iter('taskSchedulers'):
            s_name = sched.get('name')
            _,sched_algo = sched.find('schedulingAlgorithm').get(XSI_TYPE).split(':')
            self.G.add_node(s_name, TYPE = RESSOURCE, schedulingAlgorithm = sched_algo)

        for ta in self.mappingModel.iter('taskAllocation'):
            task = self.clean_xml_string(ta.get('task'))
            sched = self.clean_xml_string(ta.get('scheduler'))
            self.G.add_edge(task,sched, TYPE=MAPPING)
            self.G.add_edge(sched,task, TYPE=MAPPING)

        return self.G

    def parse_runnable_sequence(self):
        # adds edges to the graph G that specify the sequence of runnables in a task
        # assumes that runnables and tasks are already parsed
        for t in self.sw_model.iter('tasks'):
            t_name = t.get('name')

            graphEntries = t.find('callGraph/graphEntries')
            prefix,tag =  graphEntries.get(XSI_TYPE).split(":")
            if tag == 'CallSequence':
                first_runnable = True
                for call in graphEntries.iter('calls'):
                    # Get the runnable 
                    cur_r = self.clean_xml_string(call.get('runnable'))
                    # Link the runnables in order
                    if not first_runnable:
                        self.G.add_edge(prev_r, cur_r, TYPE=RUNNABLE_CALL)
                    first_runnable = False # The first runnable has no predecessor in the task
                    prev_r = cur_r

        return self.G

    def _set_time_per_instruction(self):
        assert ( int(self.hw_model.find('coreTypes').get('instructionsPerCycle')) == 1 )
        #Supports only models with one microcontroller element!
        pll_freq = int(float(self.hw_model.find('system/ecus/microcontrollers/quartzes/frequency').get('value')))
        #Assumption: pll_freq is the CPU clock, i.e. prescaler clockRation=1 for each core)
        self.time_per_instruction = util.cycles_to_time(value=1,freq=pll_freq, base_time=self.time_base)
        return self.time_per_instruction

    def get_cpa_sys(self,G):
        pass

    def parse_all(self):
        self.parse_runnables_and_labels_to_nx()
        self.parse_tasks_and_cores_to_nx()
        self.parse_runnable_sequence()

        return self.G
    
class NxConverter(object):
    def __init__(self,G):
        """ This class manages the conversion of a networkx task/runnable system to a pyCPA system
        """
        self.G = G
        self.cpa_base = util.ns

    def get_cpa_sys(self, reverse_prios=True):
       """ returns a pyCPA system based on the stored networkx graph
            reversing prios ensures that Amalthea Models parsed to nx are compatible with pyCPA
       """
       s = model.System()
       for n,d in self.G.nodes(data=True):
           if d['TYPE'] == RESSOURCE:
               #for the time being we only support SPP
               #r = s.bind_resource(model.Resource(self.G.node[n], schedulers.SPPScheduler()))
               r = s.bind_resource(model.Resource(n, schedulers.SPPScheduler()))
               # get the neigbors of n that have a MAPPING to a task
               for u,v,d_edge in self.G.out_edges(n,data=True):
                   if d_edge[TYPE] == MAPPING:
                       #v is a task
                       assert (self.G.node[v][TYPE] == TASK )
                       task_params = self.get_task_params(v,reverse_prios)
                       t = r.bind_task(model.Task(name=v, **task_params))
                       t.in_event_model = self.construct_event_model(v)
       return s

    def get_task_params(self,t,reverse_prios=True):
        """ returns dict with wcet, bcet, scheduling_parameter
        """
        t_params = dict()
        t_params['wcet'] = 0
        t_params['bcet'] = 0
        # pyCPA starts with 1 as the highest one; amalthe does it the other way around (like OSEK)
        if reverse_prios == True:
            t_params['scheduling_parameter'] = self.get_reverse_prio(t)
        else:
            t_params['scheduling_parameter'] = self.G.node[t]['scheduling_parameter']

        #Filter out a subgraph that only contains runnables, tasks and mapping edges
        tasks_runnables = [ n for n,d in self.G.nodes(data=True) if (d[TYPE] ==
            RUNNABLE or d[TYPE] == TASK)]
        H = self.G.subgraph( tasks_runnables )
        #Iterate over the runnables and compute WCET/BCET as a sum over the neigbors!
        for u,v,d in H.out_edges(t,data=True):
            if (d[TYPE] == MAPPING and self.G.node[v][TYPE] == RUNNABLE):
                #print(u,v,d)
                t_params['wcet'] = int(self.G.node[v]['wcet']) + int(t_params['wcet'])
                t_params['bcet'] = int(self.G.node[v]['bcet']) + int(t_params['bcet'])

        #print(t_params)
        return t_params

    def construct_event_model(self, task=None):
        #TODO: In principle we would have to check whether the task in fact has an event model
        # or whether it is activated by another task; in that case the dict key event_model must not
        # exist
        if self.G.node[task]['event_model']['EMType'] == 'Periodic':
            s_param = self.G.node[task]['event_model']
            P = util.time_to_time( int(s_param['value']) , base_in=util.str_to_time_base(s_param['unit']), base_out=self.cpa_base)
            return model.PJdEventModel(P=P, J=0)

        elif self.G.node[task]['event_model']['EMType'] == 'Sporadic':
            s_param = self.G.node[task]['event_model']['lowerBound']
            P = util.time_to_time( int(s_param['value']) , base_in=util.str_to_time_base(s_param['unit']), base_out=self.cpa_base)
            return model.PJdEventModel(P=P, J=0)
        else:
            raise ValueError

    def get_reverse_prio(self, task):
        # in pyCPA 1 is the highest priority - Amalthea sorts the other way, i.e. 1 is the lowest
        # in principle this can be cached!
        prio_list = list()
        name_list = list()
        for n,d in self.G.nodes(data=True):
            if d[TYPE] == TASK:
                name_list.append(n)
                prio_list.append(d[PRIO])
        prio_list.reverse()
        prio_cache = dict()
        for i in range(len(name_list)):
            prio_cache[name_list[i]] = prio_list[i]

        return prio_cache[task]

    def _get_event_model_params(self, task=None):
        """ Instead of return a cpa event model just return the parameters
            WARNING: Only returns periods at the moment
        """
        if self.G.node[task]['event_model']['EMType'] == 'Periodic':
            s_param = self.G.node[task]['event_model']
            P = util.time_to_time( int(s_param['value']) , base_in=util.str_to_time_base(s_param['unit']), base_out=self.cpa_base)
            return (P,0)

        elif self.G.node[task]['event_model']['EMType'] == 'Sporadic':
            lB = self.G.node[task]['event_model']['lowerBound']
            uB = self.G.node[task]['event_model']['upperBound']
            #TODO!
            s_param = self.G.node[task]['event_model']['lowerBound']
            P = util.time_to_time( int(s_param['value']) , base_in=util.str_to_time_base(s_param['unit']), base_out=self.cpa_base)
            return (P,0)
        else:
            raise ValueError

    def write_to_csv(self,filename, reverse_prios=True):
        """ WARNING: Forces P,J as Event Model Parameters! """

        with open(filename, 'w') as csvfile:
           fieldnames = ['task_name', 'resource', 'bcet', 'wcet', 'scheduling_parameter', 'period' , 'jitter']
           writer = csv.DictWriter(csvfile, fieldnames = fieldnames)
           writer.writeheader()

           for n,d in self.G.nodes(data=True):
               if d['TYPE'] == RESSOURCE:
                   # get the neigbors of n that have a MAPPING to a task
                   for u,v,d_edge in self.G.out_edges(n,data=True):
                       if d_edge[TYPE] == MAPPING:
                           #v is a task (i.e. the name)
                           assert (self.G.node[v][TYPE] == TASK )
                           task_params = self.get_task_params(v,reverse_prios)
                           task_params['task_name'] = v
                           task_params['resource'] = n 
                           task_params['period'], task_params['jitter'] = self._get_event_model_params(v)
                           writer.writerow(task_params)




