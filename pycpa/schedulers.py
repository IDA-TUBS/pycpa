"""
| Copyright (C) 2017 Philip Axer, Jonas Diemer, Johannes Schlatow
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer
         - Johannes Schlatow

Description
-----------

Local analysis functions (schedulers)
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import itertools
import math
import logging

from . import analysis
from . import options
from . import model

logger = logging.getLogger("pycpa")

EPSILON = 1e-9

# priority orderings
prio_high_wins_equal_fifo = lambda a, b : a >= b
prio_low_wins_equal_fifo = lambda a, b : a <= b
prio_high_wins_equal_domination = lambda a, b : a > b
prio_low_wins_equal_domination = lambda a, b : a < b

class RoundRobinScheduler(analysis.Scheduler):
    """ Round-Robin Scheduler

    task.scheduling_parameter is the respective slot size
    """

    def b_plus(self, task, q, details=None, **kwargs):
        w = q * task.wcet
        # print "q=",q
        while True:
            s = 0
            for ti in task.get_resource_interferers():
                # print "sum+=min(",q,",",ti.in_event_model.eta_plus(w)
                # s += min(q, ti.eta_plus(w))
                if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                    s += min(int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)) * ti.scheduling_parameter,
                         ti.in_event_model.eta_plus(w) * ti.wcet)
                else:
                    # Assume cooperative round robin
                    s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))

            # print "w=",q,"+",sum, ", eta_plus(w)=", task.in_event_model.eta_plus(q+sum)
            w_new = q * task.wcet + s

            if w == w_new:
                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)

                    for ti in task.get_resource_interferers():
                        if hasattr(task, "scheduling_parameter") and task.scheduling_parameter is not None:
                            if int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)) * ti.scheduling_parameter < ti.in_event_model.eta_plus(w) * ti.wcet:
                                details[str(ti)] = '%d*%d' % \
                                    (int(math.ceil(float(q) * task.wcet / task.scheduling_parameter)),
                                     ti.scheduling_parameter)
                            else:
                                details[str(ti)] = '%d*%d' % (ti.in_event_model.eta_plus(w), ti.wcet)
                        else:
                            details[str(ti)] = "%d*min(%d,%d)=%d*%d" % \
                                (ti.wcet, q, ti.in_event_model.eta_plus(w),
                                 ti.wcet, min(q, ti.in_event_model.eta_plus(w)))
                return w
            w = w_new


class SPNPScheduler(analysis.Scheduler):
    """ Static-Priority-Non-Preemptive Scheduler

    Priority is stored in task.scheduling_parameter,
    by default numerically lower numbers have a higher priority

    Policy for equal priority is FCFS (i.e. max. interference).
    """

    def __init__(self, priority_cmp=prio_low_wins_equal_fifo, ctx_switch_overhead=0, cycle_time=EPSILON):
        """
        :param priority_cmp: function to evaluate priority comparison of the form foo(a,b). if foo(a,b) == True, then "a" is more important than "b"
        :param cycle_time: time granularity of the scheduler, see [Bate1998]_ E.q. 4.14
        :param ctx_switch_overhead: context switching overhead (or interframe space for transmission lines)
        """
        analysis.Scheduler.__init__(self)

        # # time granularity of the scheduler
        self.cycle_time = cycle_time

        # # Context-switch overhead
        self.ctx_switch_overhead = ctx_switch_overhead

        # # priority ordering
        self.priority_cmp = priority_cmp

    def _blocker(self, task):
        # find maximum lower priority blocker
        b = 0
        for ti in task.get_resource_interferers():
            if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter) == False:
                b = max(b, ti.wcet)
        return b

    def spnp_busy_period(self, task):
        """ Calculated the busy period of the current task
        """
        b = self._blocker(task) + self.ctx_switch_overhead
        w = b

        while True:
            w_new = b
            for ti in task.get_resource_interferers() | set([task]):
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter) or (ti == task):
                    w_new += (ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w)

            if w == w_new:
                break

            w = w_new

        return w

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


    def b_plus(self, task, q, details=None, **kwargs):
        """ Return the maximum time required to process q activations
        """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        b = self._blocker(task) + self.ctx_switch_overhead

        w = (q - 1) * (task.wcet + self.ctx_switch_overhead) + b

        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)
                    s += (ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w + self.cycle_time)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = (q - 1) * (task.wcet + self.ctx_switch_overhead) + b + s
            # print ("w_new: ", w_new)
            if w == w_new:

                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    details['blocker'] = str(b)
                    for ti in task.get_resource_interferers():
                        if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):
                            details[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w + self.cycle_time)) + '*'\
                                + str(ti.wcet) + '=' + str((ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w + self.cycle_time))
                w += task.wcet
                assert(w >= q * task.wcet)
                return w
            w = w_new


class SPPScheduler(analysis.Scheduler):
    """ Static-Priority-Preemptive Scheduler

    Priority is stored in task.scheduling_parameter,
    by default numerically lower numbers have a higher priority

    Policy for equal priority is FCFS (i.e. max. interference).
    """


    def __init__(self, priority_cmp=prio_low_wins_equal_fifo):
        analysis.Scheduler.__init__(self)

        # # priority ordering
        self.priority_cmp = priority_cmp

    def b_plus(self, task, q, details=None, **kwargs):
        """ This corresponds to Theorem 1 in [Lehoczky1990]_ or Equation 2.3 in [Richter2005]_. """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet

        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = q * task.wcet + s
            # print ("w_new: ", w_new)
            if w == w_new:
                assert(w >= q * task.wcet)
                if details is not None:
                    details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    for ti in task.get_resource_interferers():
                        if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):
                            details[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w)) + '*'\
                                + str(ti.wcet) + '=' + str(ti.wcet * ti.in_event_model.eta_plus(w))
                return w

            w = w_new

class CorrelatedDeltaMin(model.EventModel):
    """ Computes the correlated event model :math \delta^-_j: from Lemma 2 in [Rox2010]_.
    """
    def __init__(self, em, m, offset):
        model.EventModel.__init__(self, 'tmp')

        self.em = em
        self.m = m
        self.offset = offset

    def deltamin_func(self, n):
        if n <= self.m:
            return self.em.deltamin_func(n)
        elif n == self.m + 1:
            return max(self.em.deltamin_func(n), self.offset)
        else:
            return max(self.em.deltamin_func(n), self.offset + self.em.deltamin_func(n - self.m))

class SPPSchedulerCorrelatedRox(SPPScheduler):
    """ SPP scheduler with dmin correlation.
        Computes the approximate response time bound as presented in [Rox2010]_.
    """

    def b_plus_idle(self, task, q, details=None, task_results=None):
        """ Implements Case 2 in [Rox2010]_.
        """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet
        while True:
            details.clear()
            details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)

            idle_intrf = 0
            idle_details = dict()

            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)

                    idle_intrf += ti.wcet * ti.in_event_model.eta_plus(w-ti.in_event_model.correlated_dmin(task))
                    idle_details[str(ti)+':eta*WCET'] = str(ti.in_event_model.eta_plus(w-ti.in_event_model.correlated_dmin(task))) + '*' +\
                            str(ti.wcet) + '=' + str(ti.wcet * ti.in_event_model.eta_plus(w-ti.in_event_model.correlated_dmin(task)))

            w_new = q * task.wcet + idle_intrf
            for d in idle_details.keys():
                details[d] = idle_details[d]

            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w

    def b_plus_busy(self, task, q, details=None, task_results=None):
        """ Implements Case 1 in [Rox2010]_.
        """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet
        while True:
            details.clear()
            details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)

            busy_intrf = 0
            busy_details = dict()

            interferers = set()
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)
                    interferers.add(ti)

            for ti in interferers:

                # ti starts busy window -> iterate candidates of task's first arrival
                qmax = len(task_results[ti].busy_times)
                for q in range(1, qmax):
                    intrf = 0
                    intrf_details = dict()
                    a0 = ti.in_event_model.delta_min(q) + task.in_event_model.correlated_dmin(ti)

                    for tj in interferers:
                        if tj is ti:
                            mj = q
                        else:
                            mj = tj.in_event_model.eta_plus(a0 - task.in_event_model.correlated_dmin(ti))

                        em = CorrelatedDeltaMin(tj.in_event_model, mj, a0 + tj.in_event_model.correlated_dmin(task))
                        intrf += tj.wcet * em.eta_plus(w + a0)
                        intrf_details[str(tj)+':eta*WCET'] = str(em.eta_plus(w+a0)) + '+' + str(tj.wcet) +\
                                '=' + str(tj.wcet * em.eta_plus(w + a0))

                    intrf -= a0
                    intrf_details[str(ti)+':offset'] = str(a0)

                    if intrf > busy_intrf:
                        busy_intrf = intrf
                        busy_details = intrf_details

            w_new = q * task.wcet + busy_intrf
            for d in busy_details.keys():
                details[d] = busy_details[d]

            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w

    def b_plus(self, task, q, details=None, task_results=None):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        idle_details     = dict()
        idle_intrf = self.b_plus_idle(task, q, idle_details, task_results)

        busy_details     = dict()
        busy_intrf = self.b_plus_busy(task, q, busy_details, task_results)

        if idle_intrf > busy_intrf:
            w = idle_intrf
            if details is not None:
                for d in idle_details.keys():
                    details[d] = idle_details[d]
        else:
            w = busy_intrf
            if details is not None:
                for d in busy_details.keys():
                    details[d] = busy_details[d]

        return w

class SPPSchedulerCorrelatedRoxExact(SPPScheduler):
    """ SPP scheduler with dmin correlation based on [Rox2010]_.
        This is the exact version which performs an extensive search of busy window candidates.
    """

    def calculate_w(self, task, sequence, details=None):
        w = 0
        q_cur = 0
        a0 = 0
        for ti, a in sequence:
            w += ti.wcet

            if details is not None:
                details[str(ti)+':'+str(a)] = str(ti.wcet)

            if ti is task:
                q_cur += 1
                if q_cur == 1:
                    a0 = a

        return w, a0, q_cur

    def find_candidates_recursive(self, task, q, interferers, sequence):

        w, a0, q_cur = self.calculate_w(task, sequence)

        if q > q_cur:
            interferers.add(task)
        elif task in interferers:
            interferers.remove(task)

        worst_sequence = sequence
        if q > q_cur:
            worst_rt = 0
        else:
            worst_rt = w - a0

        # place further activations and find maximum w
        for ti in interferers:
            w_new = 0
            new_sequence = list(sequence)
            if len(new_sequence):
                last_t, last_a = new_sequence[-1]
                d_i = last_a + ti.in_event_model.correlated_dmin(last_t)
                dmin = last_a

                k = 0
                for (tj, a) in new_sequence:
                    if tj is ti:
                        if k == 0:
                            first_a = a

                        dmin = first_a + ti.in_event_model.delta_min(2 + k)
                        k += 1

                next_a = max(dmin, d_i)
                if next_a <= w:
                    new_sequence.append( (ti, next_a) )
                    new_sequence = self.find_candidates_recursive(task, q, set(interferers), new_sequence)
            else:
                new_sequence.append((ti, 0))
                new_sequence = self.find_candidates_recursive(task, q, set(interferers), new_sequence)

            w_new, a0, q_cur = self.calculate_w(task, new_sequence)
            if w_new - a0 >= worst_rt and q == q_cur:
                worst_rt = w_new - a0
                worst_sequence = new_sequence

        return worst_sequence

    def b_plus_exact(self, task, q, details=None, task_results=None):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        interferers = set()
        for ti in task.get_resource_interferers():
            assert(ti.scheduling_parameter != None)
            assert(ti.resource == task.resource)
            if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # equal priority also interferes (FCFS)
                interferers.add(ti)

        sequence = self.find_candidates_recursive(task, q, interferers, list())
        w, a0, q_cur = self.calculate_w(task, sequence, details)

        assert(q == q_cur)
        return w - a0

    def b_plus(self, task, q, details=None, task_results=None):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        busy_details     = dict()
        busy_intrf = self.b_plus_exact(task, q, busy_details, task_results)

        w = busy_intrf
        if details is not None:
            for d in busy_details.keys():
                details[d] = busy_details[d]

#        classic_details  = dict()
#        classic_intrf = SPPScheduler.b_plus(self, task, q, classic_details)
#        if classic_intrf < w:
#            w = classic_intrf
#            if details is not None:
#                for d in classic_details.keys():
#                    details[d] = classic_details[d]

        assert(w >= q * task.wcet)
        return w


class SPPSchedulerRoundRobin(SPPScheduler):
    """ SPP scheduler with non-preemptive round-robin policy for equal priorities
    """

    def b_plus(self, task, q, details=None, **kwargs):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        w = q * task.wcet
        while True:
            # logging.debug("w: %d", w)
            # logging.debug("e: %d", q * task.wcet)
            s = 0
            # logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if ti.scheduling_parameter == task.scheduling_parameter:  # equal priority -> round robin
                    # assume cooperative round-robin
                    s += ti.wcet * min(q, ti.in_event_model.eta_plus(w))
                elif self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):  # lower priority number -> block
                    s += ti.wcet * ti.in_event_model.eta_plus(w)
                    # logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))


            w_new = q * task.wcet + s
            # print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w


class TDMAScheduler(analysis.Scheduler):
    """ TDMA scheduler
        task.scheduling_parameter is the slot size of the respective task
    """

    def b_plus(self, task, q, details=None, **kwargs):
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        t_tdma = task.scheduling_parameter
        for tj in task.get_resource_interferers():
            t_tdma += tj.scheduling_parameter

        w = q * task.wcet + math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter)
        w = int(w)

        assert(w >= q * task.wcet)

        if details is not None:
            details['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
            for tj in task.get_resource_interferers():
                details["%s.TDMASlot" % (tj)] = str(tj.scheduling_parameter)
            details['I_TDMA'] = '%d*%d=%d' % (math.ceil(float(q * task.wcet) / task.scheduling_parameter),
                                      t_tdma - task.scheduling_parameter,
                                      math.ceil(float(q * task.wcet) / task.scheduling_parameter) * (t_tdma - task.scheduling_parameter))
        return w

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
