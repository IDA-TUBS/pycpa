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

def blocker_task(task):
    # find maximum lower priority blocker
    b = 0
    bt = None
    for ti in task.get_resource_interferers():
        if ti.scheduling_parameter > task.scheduling_parameter:
            if ti.wcet > b:
                b = ti.wcet
                bt = ti
    return bt

def spnp_multi_activation_stopping_condition(task, q, w):
    """ Check if we have looked far enough
        compute the time the resource is busy processing q activations of task
        and activations of all higher priority tasks during that time
        Returns True if stopping-condition is satisfied, False otherwise 
    """
    busy_period = q * task.wcet
    for t in task.get_resource_interferers(): # FIXME: what about my own activations??
        if t.scheduling_parameter <= task.scheduling_parameter:
            busy_period += t.in_event_model.eta_plus(w) * t.wcet
    # if there are no new activations when the current busy period has been completed, we terminate
    if q >= task.in_event_model.eta_plus(busy_period):
        return True
    return False

def w_spnp(task, q, MAX_WINDOW=10000, **kwargs):
    """ Return the maximum time required to process q activations
        Priority stored in task.scheduling_parameter
        smaller priority number -> right of way
        Policy for equal priority is FCFS (i.e. max. interference)
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
            if ti.scheduling_parameter <= task.scheduling_parameter: # equal priority also interferes (FCFS)
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
