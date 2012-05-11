"""
| Copyright (C) 2007-2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

This module contains classes to simulate the critical instant with the purpose of deriving
gantt charts.
"""


try:
    from SimPy.Simulation import *
except ImportError:
    Simulation = None # get rid of "compile-time" errors
    print "Sorry, you don't have the SimPy module installed."
    print "Please install or reconfigure SimPy"
    print "and try again."


import model
import spnp
import options

import logging
import sys
import plot

logger = logging.getLogger("sim")

## Model components -------------------------------

class SimTask  (Process):
    """ A task will produce the activations with a distance according to delta_minus
        It stops, when the resource is idle (end of busy window)
    """
    def __init__(self, task, sim):
        Process.__init__(self, name=task.name, sim=sim)
        # link to the pycpa model
        self.task = task

        # add a list to store the execution windows in the task
        self.task.q_exec_windows = list()

        # all activations that have been emitted
        self.activations = list()


    def run(self, scheduler):
        """ Main simulation routine
            create event -> put event into scheduler -> sleep for delta_min --> create event...
        """
        n = 1
        logger.info("Starting task %s" % self.name)

        if  self.task.in_event_model.delta_min(n) == float('inf'):
            return

        while True:
            a = SimActivation(name="Activation%s,%d" % (self.task.name, n,), sim=self.sim, task=self.task)
            a.q = n

            self.activations.append(a)

            self.sim.activate(a, a.execute(self.task, scheduler))

            scheduler.pending.append(a)
            scheduler.arrival_event.signal()
            self.interrupt(scheduler)

            n += 1
            yield hold, self, self.task.in_event_model.delta_min(n) - self.sim.now()

            # check if the resource is idle
            if scheduler.idle() == True:
                break

class SimActivation (Process):
    """ Representation of an activation
    """

    def __init__(self, name, sim, task):
        Process.__init__(self, name=name, sim=sim)

        # number of the action
        self.q = 0

        # corresonding pycpa task
        self.task = task

        # the signal used to wake up the activation event
        self.signal_event = SimEvent(sim=sim)

        # workload left to consume
        self.workload = task.wcet

        # active segments of the execution of the form: [(0,1), (3,9)]
        self.exec_windows = list()

        # last recent start of a execution segment
        self.recent_window_start = None

        # actual response time
        self.response_time = 0

        # start time
        self.start_time = 0

        # finishing time
        self.finish_time = 0

    def log_execution(self):
        """ Called by the scheduler to log executions
        """
        assert self.recent_window_start == None
        self.recent_window_start = self.sim.now()

    def log_preemtion(self):
        """
            Called by the scheduler to log preemtions
        """
        self.exec_windows.append((self.recent_window_start, self.sim.now()))
        self.recent_window_start = None

    def execute(self, task, scheduler):
        """
            This will actually just wait until signaled by the scheduler.
            The execution time is decreased by the scheduler (so the scheduler can actually increase
            execution time if that is necessary.
            
        """
        logger.info("Activated %s q=%d @t=%d" % (self.task.name, self.q, self.sim.now()))
        self.start_time = self.sim.now()

        while self.workload > 0:
            yield waitevent, self, self.signal_event

        logger.info("Finished %s q=%d @t=%d" % (self.task.name, self.q, self.sim.now()))
        self.finishing_time = self.sim.now()
        self.response_time = self.finishing_time - self.start_time

        # add the execution windows to the pycpa task
        self.task.q_exec_windows.append(self.exec_windows)

class SimSPP (Process):
    """ SPP Resource model
    """
    def __init__(self, sim, name="SPP", tasks=list()):

        assert sim != None
        Process.__init__(self, name=name, sim=sim)
        self.tasks = tasks
        self.pending = list()

        # list of simtasks
        self.simtasks = list()

        self.arrival_event = SimEvent('Arrival Event', sim=sim)
    def select(self):
        """ Select the next activation from the pending list
        """
        if len(self.pending) == 0:
            return None

        s = self.pending[-1]

        # we look 
        for a in reversed(self.pending):
            if a.task.scheduling_parameter <= s.task.scheduling_parameter:
                s = a
        return s

    def idle(self):
        """ Check if the resource is currently idle
        """
        return len(self.pending) == 0

    def execute(self, resource, task):

        for simtask in self.simtasks:
            if simtask.task.scheduling_parameter <= task.scheduling_parameter:
                self.sim.activate(simtask, simtask.run(self))

        activation = None
        while True:

            # passivate and wait for new events
            while self.idle() == True:
                yield waitevent, self, self.arrival_event

            logger.info("pendings: %d @t=%d" % (len(self.pending), self.sim.now()))
            #get event
            next_activation = self.select()
            if  next_activation != activation:
                activation = next_activation
                # store the beginning of the execution window
                activation.log_execution()

            yield hold, self, activation.workload
            activation.workload = 0

            logger.info("pendings: %d @t=%d" % (len(self.pending), self.sim.now()))
            if self.interrupted() == True:
                # a new activation is ready
                self.interruptReset()

                activation.workload = self.interruptLeft

                #log if this is a real preemtion:
                if self.select() != activation and  activation.workload > 0:
                    activation.log_preemtion()

            if activation.workload == 0:
                # done
                activation.log_preemtion()
                activation.signal_event.signal()
                self.pending.remove(activation)


class SimSPNP (Process):
    """ SPP Resource model
    """
    def __init__(self, sim, name="SPP", tasks=list()):

        assert sim != None
        Process.__init__(self, name=name, sim=sim)

        # list of pending activations
        self.pending = list()

        # list of blocker activations (usually one lower priority activation)
        self.blockers = list()

        # list of simtasks
        self.simtasks = list()

        # signals a new activation
        self.arrival_event = SimEvent('Arrival Event', sim=sim)

    def select(self):
        """ Select the next activation from the pending list
        """

        if len(self.blockers) > 0:
            return self.blockers[-1]

        if len(self.pending) == 0:
            return None

        s = self.pending[-1]
        for a in reversed(self.pending):
            if a.task.scheduling_parameter <= s.task.scheduling_parameter:
                s = a
        return s

    def idle(self):
        """ Check if the resource is currently idle
        """
        return len(self.pending) == 0 and len(self.blockers) == 0

    def execute(self, resource, task, additional_blocker_activations=None):
        # get the blocker task
        blocker = spnp.blocker_task(task)
        self.lowprio_simblocker = None

        #find the SimTask Object of the blocker
        for b in self.simtasks:
            if b.task == blocker:
                self.lowprio_simblocker = b
                break

        # if there is a blocker, create one activation and put it in the queue
        if blocker:
            blocker_activation = SimActivation(name="Blocker %s" % (self.lowprio_simblocker.name), sim=self.sim, task=blocker)
            self.blockers.append(blocker_activation)
            self.lowprio_simblocker.activations.append(blocker_activation)
            self.sim.activate(blocker_activation, blocker_activation.execute(blocker, self))

        for simtask in self.simtasks:
            if simtask.task.scheduling_parameter <= task.scheduling_parameter:
                self.sim.activate(simtask, simtask.run(self))

        activation = None
        while True:
            # passivate and wait for new events
            while self.idle() == True:
                yield waitevent, self, self.arrival_event

            #get event
            new_activation = self.select()
            if new_activation != activation:
            # store the beginning of the execution window
                activation = new_activation
                activation.log_execution()

            # eat up workload until the activation is done
            while activation.workload > 0:
                yield hold, self, activation.workload
                activation.workload = 0

                if self.interrupted() == True:
                    # we will be interrupted by new arrivals
                    self.interruptReset()
                    activation.workload = self.interruptLeft

            assert activation.workload == 0
            activation.log_preemtion()
            activation.signal_event.signal()

            # remove from whatever list
            if activation in self.pending: self.pending.remove(activation)
            if activation in self.blockers: self.blockers.remove(activation)

## Model ------------------------------------------

class ResourceModel(Simulation):

    def __init__(self, resource, name="Experiment"):
        Simulation.__init__(self)
        self.name = name
        self.resource = resource
        self.scheduler = None

    def runModel(self, task, scheduler, until=float('inf')):
        ## Initialize Simulation instance
        self.initialize()

        self.scheduler = scheduler

        for t in self.resource.tasks:
            simtask = SimTask(t, sim=self)
            self.scheduler.simtasks.append(simtask)

        self.activate(self.scheduler , self.scheduler.execute(self.resource, task))

        self.simulate(until=until)

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    s = model.System()

    # add spp as the fault-free scheduling policy
    r1 = s.add_resource("R1", spnp.w_spnp)

    t1 = model.Task("T1")
    t1.wcet = 1
    t1.bcet = 0
    t1.scheduling_parameter = 1
    #t1.wcet_pdf = s_model.generate_task_pdf(t1, options.get_opt('mpmath'))
    r1.bind_task(t1)


    t2 = model.Task("T2")
    t2.wcet = 2
    t2.bcet = 0
    t2.scheduling_parameter = 2
    #t2.wcet_pdf = s_model.generate_task_pdf(t2, options.get_opt('mpmath'))
    r1.bind_task(t2)

    t3 = model.Task("T3")
    t3.wcet = 3
    t3.bcet = 0
    t3.scheduling_parameter = 3
    #t3.wcet_pdf = s_model.generate_task_pdf(t3)
    r1.bind_task(t3)


    #Setting the event models
    t1.in_event_model = model.EventModel()
    t1.in_event_model.set_PJ(5, 3)

    t2.in_event_model = model.EventModel()
    t2.in_event_model.set_PJ(7, 12)

    t3.in_event_model = model.EventModel()
    t3.in_event_model.set_PJ(14, 10)


    model = ResourceModel(r1)
    model.runModel(task=t2, scheduler=SimSPNP(name="SPNP", sim=model))

    task = t2

    #plot
    hp_tasks = list()
    for t in sorted(r1.tasks, key=str):
        if t.scheduling_parameter <= task.scheduling_parameter:
            hp_tasks.append(t)
    print hp_tasks
    plot.plot_gantt(hp_tasks + [spnp.blocker_task(task)])


    #for st in sorted(model.scheduler.tasks, key = str):
    #    for a in st.activations:
    #        print a.name, a.q, a.exec_windows
