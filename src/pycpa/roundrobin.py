"""
| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

Round robin busy window function
"""

import math
import analysis

def rr_multi_activation_stopping_condition(task, q, w):
    """ Check if we have looked far enough
        Returns True if stopping-condition is satisfied, False otherwise     
    """

    # if there are no new activations when the current busy period has been completed, we terminate
    if task.in_event_model.delta_min(q + 1) >= w:
        return True
    return False

def w_roundrobin(task, q, **kwargs):
    """ Return the maximum time required to process q activations
        (1 cycle WCET each) 
        under round-robin scheduling under presence of interfering tasks.
        task.scheduling_parameter is the respective slot size
    """
    w = q * task.wcet
    #print "q=",q
    while True:
        s = 0
        for ti in task.get_resource_interferers():
            #print "sum+=min(",q,",",ti.in_event_model.eta_plus(w)
            #s += min(q, ti.eta_plus(w))
            if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                s += min(math.ceil(float(q) * task.wcet / task.scheduling_parameter) * ti.scheduling_parameter,
                     ti.in_event_model.eta_plus(w) * ti.wcet)
            else:
                # Assume cooperative round robin
                s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))

        #print "w=",q,"+",sum, ", eta_plus(w)=", task.in_event_model.eta_plus(q+sum)
        w_new = q * task.wcet + s

        if w == w_new:
            break
        w = w_new

    return w
