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


class RoundRobinScheduler(analysis.Scheduler):
    """ Round-Robin Scheduler

    task.scheduling_parameter is the respective slot size
    """

    def b_plus(self, task, q, details=False):
        w = q * task.wcet
        #print "q=",q
        while True:
            s = 0
            for ti in task.get_resource_interferers():
                #print "sum+=min(",q,",",ti.in_event_model.eta_plus(w)
                #s += min(q, ti.eta_plus(w))
                if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                    s += min(int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)) * ti.scheduling_parameter,
                         ti.in_event_model.eta_plus(w) * ti.wcet)
                else:
                    # Assume cooperative round robin
                    s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))

            #print "w=",q,"+",sum, ", eta_plus(w)=", task.in_event_model.eta_plus(q+sum)
            w_new = q * task.wcet + s

            if w == w_new:
                if details:
                    d = dict()
                    d['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)

                    for ti in task.get_resource_interferers():
                        if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                            if int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)) * ti.scheduling_parameter < ti.in_event_model.eta_plus(w) * ti.wcet:
                                d[str(ti)] = '%d*%d' % \
                                    (int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)),
                                     ti.scheduling_parameter)
                            else:
                                d[str(ti)] = '%d*%d' % (ti.in_event_model.eta_plus(w), ti.wcet)
                        else:
                            d[str(ti)] = "%d*min(%d,%d)=%d*%d" % \
                                (ti.wcet, q, ti.in_event_model.eta_plus(w),
                                 ti.wcet, min(q, ti.in_event_model.eta_plus(w)))
                    return d
                else:
                    return w
            w = w_new

