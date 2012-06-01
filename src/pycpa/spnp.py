"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Static Priority Non Preemptive Analysis functions (see [Davis2007]_).


"""


import logging
import analysis


def blocker(task):
    # find maximum lower priority blocker
    b = 0
    for ti in task.get_resource_interferers():
        if ti.scheduling_parameter > task.scheduling_parameter:
            b = max(b, ti.wcet)
    return b

#def blocker_task(task):
#    # find maximum lower priority blocker
#    b = 0
#    bt = None
#    for ti in task.get_resource_interferers():
#        if ti.scheduling_parameter > task.scheduling_parameter:
#            if ti.wcet > b:
#                b = ti.wcet
#                bt = ti
#    return bt

high_wins_equal_fifo = lambda a, b : a <= b
low_wins_equal_fifo = lambda a, b : a >= b
high_wins_equal_domination = lambda a, b : a < b
low_wins_equal_domination = lambda a, b : a > b


class SPNPScheduler(analysis.Scheduler):
    """ Static-Priority-Non-Preemptive Scheduler
        
    Priority is stored in task.scheduling_parameter,
    smaller priority number -> right of way
    
    Policy for equal priority is FCFS (i.e. max. interference).
    """

    def __init__(self, priority_cmp=high_wins_equal_fifo):
        analysis.Scheduler.__init__(self)

        ## priority ordering
        self.priority_cmp = priority_cmp

    def spnp_busy_period(self, task):
        """ Calculated the busy period of the current task
        """
        b = blocker(task)
        w = task.wcet + b

        while True:
            w_new = 0
            for ti in task.get_resource_interferers() | set(task):
                if ti.scheduling_parameter <= task.scheduling_parameter:
                    w_new += ti.wcet * ti.in_event_model.eta_plus(w)

            if w == w_new:
                break

    def stopping_condition(self, task, q, w):
        """ Check if we have looked far enough
            compute the time the resource is busy processing q activations of task
            and activations of all higher priority tasks during that time
            Returns True if stopping-condition is satisfied, False otherwise 
        """

        # if there are no new activations when the current busy period has been completed, we terminate
        if task.in_event_model.delta_min(q + 1) >= self.spnp_busy_period(task):
            return True
        return False


    def b_plus(self, task, q):
        """ Return the maximum time required to process q activations
        """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        b = blocker(task)

        w = (q - 1) * task.wcet + b

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

            w_new = (q - 1) * task.wcet + b + s
            #print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        w += task.wcet
        assert(w >= q * task.wcet)
        return w
