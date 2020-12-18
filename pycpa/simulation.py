"""
| Copyright (C) 2007-2017 Philip Axer
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

from __future__ import absolute_import

import logging
from simpy import Environment


logger = logging.getLogger("sim")

## Model components -------------------------------

class SimTask:
    """ A task will produce the activations with a distance according to delta_minus
        It stops, when the resource is idle (end of busy window)
    """
    def __init__(self, env, task):
        self.env = env
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
        logger.info("Starting task %s" % self.task.name)

        if self.task.in_event_model.delta_min(n) == float('inf'):
            return

        while True:
            name = "Activation%s,%d" % (self.task.name, n)
            a = SimActivation(env=self.env, name=name, task=self.task)
            a.q = n

            self.activations.append(a)
            self.env.process(a.execute())

            scheduler.pending.append(a)
            scheduler.arrival_event.succeed()
            scheduler.arrival_event = self.env.event()

            n += 1
            min_distance = self.task.in_event_model.delta_min(n)
            yield self.env.timeout(min_distance - self.env.now)

            # check if the resource is idle
            if scheduler.idle():
                break

class SimActivation:
    """ Representation of an activation
    """

    def __init__(self, env, name, task):
        self.env = env

        # number of the action
        self.q = 0

        # corresonding pycpa task
        self.task = task

        # the signal used to wake up the activation event
        self.signal_event = env.event()

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
        assert self.recent_window_start is None
        logger.info("Executing %s q=%d @t=%d", self.task.name, self.q, self.env.now)
        self.recent_window_start = self.env.now

    def log_preemtion(self):
        """
            Called by the scheduler to log preemtions
        """
        self.exec_windows.append((self.recent_window_start, self.env.now))
        self.recent_window_start = None

    def execute(self):
        """
            This will actually just wait until signaled by the scheduler.
            The execution time is decreased by the scheduler (so the scheduler can actually increase
            execution time if that is necessary.

        """
        logger.info("Activated %s q=%d @t=%d", self.task.name, self.q, self.env.now)
        self.start_time = self.env.now

        while self.workload > 0:
            yield self.signal_event

        logger.info("Finished %s q=%d @t=%d", self.task.name, self.q, self.env.now)
        self.finish_time = self.env.now
        self.response_time = self.finish_time - self.start_time

        # add the execution windows to the pycpa task
        self.task.q_exec_windows.append(self.exec_windows)

class SimSPP:
    """ SPP Resource model
    """
    def __init__(self, env, name="SPP", tasks=list()):

        assert env is not None
        self.env = env
        self.tasks = tasks
        self.pending = list()

        # list of simtasks
        self.simtasks = list()

        self.arrival_event = env.event()
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
                self.env.process(simtask.run(self))

        activation = None
        while True:

            # passivate and wait for new events
            while self.idle():
                yield self.arrival_event

            logger.info("pendings: %d @t=%d", len(self.pending), self.env.now)
            # get event
            next_activation = self.select()
            if next_activation != activation:
                activation = next_activation
                # store the beginning of the execution window
                activation.log_execution()

            service_start = self.env.now
            service_event = self.env.timeout(activation.workload)

            yield service_event | self.arrival_event
            logger.info("pendings: %d @t=%d", len(self.pending), self.env.now)
            activation.workload -= self.env.now - service_start

            if not service_event.processed:
                # a new activation is ready
                # log if this is a real preemtion:
                if self.select() != activation and activation.workload > 0:
                    activation.log_preemtion()

            if activation.workload == 0:
                # done
                activation.log_preemtion()
                activation.signal_event.succeed()
                self.pending.remove(activation)


class SimSPNP:
    """ SPP Resource model
    """
    def __init__(self, env, name="SPNP", tasks=list()):

        assert env is not None
        self.env = env

        # list of pending activations
        self.pending = list()

        # list of blocker activations (usually one lower priority activation)
        self.blockers = list()

        # list of simtasks
        self.simtasks = list()

        # signals a new activation
        self.arrival_event = env.event()

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

    def execute(self, resource, task):
        # get the blocker task
        blocker = resource.scheduler._blocker(task)
        self.lowprio_simblocker = None

        # find the SimTask Object of the blocker
        for b in self.simtasks:
            if b.task == blocker:
                self.lowprio_simblocker = b
                break

        # if there is a blocker, create one activation and put it in the queue
        if blocker:
            name = "Blocker %s" % self.lowprio_simblocker.name
            blocker_activation = SimActivation(env=self.env, name=name, task=blocker)
            self.blockers.append(blocker_activation)
            self.lowprio_simblocker.activations.append(blocker_activation)
            self.env.process(blocker_activation.execute())

        for simtask in self.simtasks:
            if simtask.task.scheduling_parameter <= task.scheduling_parameter:
                self.env.process(simtask.run(self))

        activation = None
        while True:
            # passivate and wait for new events
            while self.idle():
                yield self.arrival_event

            # get event
            new_activation = self.select()
            if new_activation != activation:
            # store the beginning of the execution window
                activation = new_activation
                activation.log_execution()

            # eat up workload until the activation is done
            service_event = self.env.timeout(activation.workload)

            yield service_event
            activation.workload = 0
            activation.log_preemtion()
            activation.signal_event.succeed()

            # remove from whatever list
            if activation in self.pending:
                self.pending.remove(activation)
            if activation in self.blockers:
                self.blockers.remove(activation)


class ResourceModel:

    def __init__(self, resource, name="Experiment"):
        self.env = Environment()
        self.name = name
        self.resource = resource
        self.scheduler = None

    def runModel(self, task, scheduler, until=float('inf')):
        self.scheduler = scheduler

        for t in self.resource.tasks:
            simtask = SimTask(self.env, t)
            self.scheduler.simtasks.append(simtask)

        self.env.scheduler_proc = self.env.process(self.scheduler.execute(self.resource, task))
        self.env.run(until=until)
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
