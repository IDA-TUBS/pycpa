"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

FIFO scheduler
"""

import logging
import analysis

logger = logging.getLogger("fifo")

def fifo_multi_activation_stopping_condition(task, q, w):
    """ Check if we have looked far enough
        Returns True if stopping-condition is satisfied, False otherwise 
    """

    # if there are no new activations when the current busy period has been completed, we terminate
    if task.in_event_model.delta_min(q + 1) > w:
        return True
    return False

def w_fifo(task, q, MAX_WINDOW=10000):
    """ Return the maximum time required to process q activations
        simple fifo assumption: all other activations have been queued before mine
    """
    assert(task.wcet >= 0)

    w = q * task.wcet

    while True:
        s = 0
        for ti in (task.get_resource_interferers() - set([task])):
                s += ti.wcet * ti.in_event_model.eta_plus(w)
        w_new = q * task.wcet + s
        #print ("w_new: ", w_new)
        if w == w_new:
            break
        w = w_new

        if w > MAX_WINDOW:
            raise analysis.NotSchedulableException("MAX_WINDOW exceeded, likely not schedulable")

    assert(w >= q * task.wcet)
    return w
