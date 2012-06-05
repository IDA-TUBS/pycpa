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
import analysis

class TDMAScheduler(analysis.Scheduler):
    """ TDMA scheduler
        task.scheduling_parameter is the slot size of the respective task
    """

    def b_plus(self, task, q, details=False):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        t_tdma = task.scheduling_parameter
        for tj in task.get_resource_interferers():
            t_tdma += tj.scheduling_parameter

        w = q * task.wcet + math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter)

        assert(w >= q * task.wcet)

        if details:
            d = dict()
            d['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
            for tj in task.get_resource_interferers():
                d["%s.TDMASlot" % (tj)] = str(tj.scheduling_parameter)
            d['I_TDMA'] = '%d*%d=%d' % (math.ceil(float(q * task.wcet) / task.scheduling_parameter),
                                      t_tdma - task.scheduling_parameter,
                                      math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter))
            return d
        else:
            return w
