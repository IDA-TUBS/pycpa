"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

TDMA busy window function
"""

import math
import warnings

def tdma_multi_activation_stopping_condition(task, q, w):
    """ Check if we have looked far enough
        compute the time the resource is busy processing q activations of task 
    """
    # if there are no new activations when the current busy period has been completed, we terminate
    if task.in_event_model.delta_min(q + 1) >= w:
        return True
    return False


def w_tdma(task, q, **kwargs):
    """ Return the maximum time required to process q activations
        for TDMA
        task.scheduling_parameter is the slot size of the respective task
    """
    assert(task.scheduling_parameter != None)
    assert(task.wcet >= 0)

    t_tdma = task.scheduling_parameter
    for tj in task.get_resource_interferers():
        t_tdma += tj.scheduling_parameter

    w = q * task.wcet + math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter)

    assert(w >= q * task.wcet)
    return w
