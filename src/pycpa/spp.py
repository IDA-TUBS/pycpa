"""
| Copyright (C) 2007-2012 Philip Axer, Jonas DIemer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer
         - Jonas Diemer

Description
-----------

Static Priority Preemptive (SPP) busy window in various flavours 
"""

import logging
import analysis

high_wins_equal_fifo = lambda a, b : a <= b
low_wins_equal_fifo = lambda a, b : a >= b
high_wins_equal_domination = lambda a, b : a < b
low_wins_equal_domination = lambda a, b : a > b

class SPPScheduler(analysis.Scheduler):
    """ Static-Priority-Preemptive Scheduler
    
    Priority is stored in task.scheduling_parameter,
    smaller priority number -> right of way
    
    Policy for equal priority is FCFS (i.e. max. interference).
    """


    def __init__(self, priority_cmp=high_wins_equal_fifo):
        analysis.Scheduler.__init__(self)

        ## priority ordering
        self.priority_cmp = priority_cmp

    def b_plus(self, task, q):
        """ This corresponds to Theorem 1 in [Lehoczky1990]_ or Equation 2.3 in [Richter2005]_. """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet

        while True:
            #logging.debug("w: %d", w)
            #logging.debug("e: %d", q * task.wcet)
            s = 0
            #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter): # equal priority also interferes (FCFS)
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    #logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = q * task.wcet + s
            #print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w

class SPPSchedulerRoundRobin(SPPScheduler):
    """ SPP scheduler with non-preemptive round-robin policy for equal priorities
    """

    def b_plus(self, task, q):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet
        while True:
            #logging.debug("w: %d", w)
            #logging.debug("e: %d", q * task.wcet)
            s = 0
            #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if ti.scheduling_parameter == task.scheduling_parameter: # equal priority -> round robin
                    # assume cooperative round-robin                
                    s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))
                elif self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter): # lower priority number -> block
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    #logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))


            w_new = q * task.wcet + s
            #print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w

