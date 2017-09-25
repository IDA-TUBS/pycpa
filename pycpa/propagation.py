""" Event model propagation algorithms.

| Copyright (C) 2007-2017 Jonas Diemer, Philip Axer, Johannes Schlatow
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer
         - Johannes Schlatow

Description
-----------
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from . import options
from . import model

def default_propagation_method():
    method = options.get_opt('propagation')

    if method == 'jitter_offset':
        return JitterOffsetPropagationEventModel
    elif method == 'busy_window':
        return BusyWindowPropagationEventModel
    elif  method == 'jitter_dmin' or method == 'jitter':
        return JitterPropagationEventModel
    elif method == 'jitter_bmin':
        return JitterBminPropagationEventModel
    elif method == 'optimal':
        return OptimalPropagationEventModel
    else:
        raise NotImplementedError

class JitterPropagationEventModel(model.EventModel):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).

    This corresponds to Equations 1 (non-recursive) and
    2 (recursive from [Schliecker2009]_
    This is equivalent to Equation 5 in [Henia2005]_
    or Equation 4.6 in [Richter2005]_.

    Uses a reference to task.deltamin_func
    """
    def __init__(self, task, task_results, nonrecursive=True):
        self.task = task
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.dmin = task_results[task].bcrt
        self.nonrecursive = nonrecursive

        name = task.in_event_model.__description__ + "+J=" + \
            str(self.resp_jitter) + ",dmin=" + str(self.dmin)

        model.EventModel.__init__(self,name,task.in_event_model.container)

        if options.get_opt('propagation') == 'jitter':
            # ignore dmin if propagation is jitter only
            self.dmin = 0

        assert self.resp_jitter >= 0, 'response time jitter must be positive'


    def deltamin_func(self, n):
        if self.nonrecursive:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                    (n - 1) * self.dmin)
        else:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                        self.delta_min(n - 1) + self.dmin)

    def deltaplus_func(self, n):
        return self.task.in_event_model.delta_plus(n) + self.resp_jitter


class JitterOffsetPropagationEventModel(model.EventModel):
    """ Derive an output event model from response time jitter
     and in_event_model (used as reference).
     Also calculates the offset attribute.

    This corresponds to Equations 1 (non-recursive) and
    2 (recursive from [Schliecker2009]_
    This is equivalent to Equation 5 in [Henia2005]_
    or Equation 4.6 in [Richter2005]_.

    Uses a reference to task.deltamin_func
    """
    def __init__(self, task, task_results,nonrecursive=True):
        assert nonrecursive, "nonrecursive=False is not implemented"

        self.phi = task.in_event_model.phi + task.bcet
        self.task = task
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.J = task.in_event_model.J + self.resp_jitter
        self.P = task.in_event_model.P
        self.dmin = task_results[task].bcrt

        name = task.in_event_model.__description__ + "+J=" + \
        str(self.resp_jitter) + ",O=" + str(self.phi)

        model.EventModel.__init__(self,name,task.in_event_model.container)


        assert self.resp_jitter >= 0, 'response time jitter must be positive'

    def deltamin_func(self, n):
        return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                    (n - 1) * self.dmin)

    def deltaplus_func(self, n):
        return self.task.in_event_model.delta_plus(n) + self.resp_jitter

class JitterBminPropagationEventModel(model.EventModel):
    """ Derive an output event model from response time jitter,
    the b_min as well as the in_event_model (used as reference).

    Uses a reference to task.deltamin_func
    """

    def __init__(self, task, task_results,nonrecursive=True):

        self.task = task
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.nonrecursive = nonrecursive
        self.dmin = task_results[task].bcrt

       # set proper name
        name = task.in_event_model.__description__ + "+J=" + \
        str(self.resp_jitter) + ",dmin=" + str(self.dmin)

        model.EventModel.__init__(self,name,task.in_event_model.container)
        assert self.resp_jitter >= 0, 'response time jitter must be positive'


    def bmin(self, n):
        """ minimum production time for n events at the output"""
        return max(self.task.resource.scheduler.b_min(self.task, n-1),
                         (n-1)*self.dmin)

    def deltamin_func(self, n):
        if self.nonrecursive:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                    self.bmin(n))
        else:
            return max(self.task.in_event_model.delta_min(n) - self.resp_jitter,
                        self.delta_min(n - 1) + self.dmin, self.bmin(n))

    def deltaplus_func(self, n):
        return self.task.in_event_model.delta_plus(n) + self.resp_jitter

class BusyWindowPropagationEventModel(model.EventModel):
    """ Derive an output event model from busy window
    and in_event_model (used as reference).
    Typically provides better results than JitterPropagationEventModel.

    This results from Theorems 1, 2 and 3 from [Schliecker2008]_.
    """

    def __init__(self, task, task_results, nonrecursive=True):
        # set proper name
        name = task.in_event_model.__description__ + "++"

        model.EventModel.__init__(self,name,task.in_event_model.container)

        self.task = task
        self.dmin = task_results[task].bcrt
        self.bcrt = task_results[task].bcrt
        self.busy_times = task_results[task].busy_times

    def deltamin_func(self, n):
        max_k = len(self.busy_times)
        min_k = 1  # k \elem N+
        bcrt = self.bcrt

        if max_k <= 1:
            # if this task has not been analysed, propagate input event model
            return self.task.in_event_model.delta_min(n)

        assert max_k > min_k

        return max((n - 1) * self.dmin,
            min([self.task.in_event_model.delta_min(n + k - 1) - self.busy_times[k]
                 for k in range(min_k, max_k)])
            + bcrt)

    def deltaplus_func(self, n):
        max_k = len(self.busy_times)
        min_k = 1  # k \elem N+
        bcrt = self.bcrt

        if max_k <= 1:
            # if this task has not been analysed, propagate input event model
            return self.task.in_event_model.delta_plus(n)

        assert max_k > min_k

        return max([self.task.in_event_model.delta_plus(n - k + 1) + self.busy_times[k]
             for k in range(min_k, max_k)]) - bcrt

class SPNPBusyWindowPropagationEventModel(BusyWindowPropagationEventModel):
    """ 
    Performs standard busy window propagation but additionally calculates the
    minimum distance to any preceding event of a given task.

    This corresponds to Def. 2 from [Rox2010]_.
    """
    def __init__(self, task, task_results, nonrecursive=True):
        BusyWindowPropagationEventModel.__init__(self, task, task_results, nonrecursive)

    def correlated_dmin(self, task):
        return self.dmin

class OptimalPropagationEventModel(JitterBminPropagationEventModel,
                                   BusyWindowPropagationEventModel):
    """ Optimal event model based on jitter and busy_window
    propagation.
    For some schedulers, such as FIFO and EDF neither busy_window
    nor jitter propagation is optimal. This will
    try both and chooses the best result.
    """
    def __init__(self, task, task_results, nonrecursive=True):
        self.task = task
        self.task_result = task_results[task]
        self.dmin = task_results[task].bcrt
        self.resp_jitter = task_results[task].wcrt - task_results[task].bcrt
        self.busy_times = task_results[task].busy_times
        self.bcrt = task_results[task].bcrt
        self.nonrecursive = nonrecursive

        name = task.in_event_model.__description__ + "++"
        model.EventModel.__init__(self,name,task.in_event_model.container)

    def deltamin_func(self, n):
        return max(JitterBminPropagationEventModel.deltamin_func(self, n),
                BusyWindowPropagationEventModel.deltamin_func(self, n))

    def deltaplus_func(self, n):
        return min(JitterBminPropagationEventModel.deltaplus_func(self, n),
                BusyWindowPropagationEventModel.deltaplus_func(self, n))

