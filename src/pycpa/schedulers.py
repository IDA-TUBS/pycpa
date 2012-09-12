"""
| Copyright (C) 2012 Philip Axer, Jonas Diemer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer, Philip Axer

Description
-----------

Local analysis functions (schedulers)
"""

import itertools
import analysis
import options
import math
import logging

logger = logging.getLogger("pycpa")

EPSILON = 1e-9

# priority orderings
prio_high_wins_equal_fifo = lambda a, b : a >= b
prio_low_wins_equal_fifo = lambda a, b : a <= b
prio_high_wins_equal_domination = lambda a, b : a > b
prio_low_wins_equal_domination = lambda a, b : a < b


class EDFPScheduler(analysis.Scheduler):
    """ Earliest-Deadline-First-Preemptive Scheduler
    
    local deadlines must be stored in task.deadline
    
    Policy for coinciding deadlines is max. interference.
            
    .. warning::
        experimental, use with caution
        
    """

    def edf_busy_period(self, task):
        """ Returns the max. time, the resource is busy

        :param task: the analyzed task
        :type task: model.Task
        :rtype: integer (max. time)
        """

        w = task.wcet

        while True:
            w_new = 0
            for ti in (task.get_resource_interferers() | set([task])):
                    w_new += ti.wcet * ti.in_event_model.eta_plus(w)

            if w == w_new:
                break
            w = w_new
        return w


    def _activation_time_candidates(self, task, q):
        """ Returns a set of activation times which must be evaluated.
        
        similar to [Palencia2003]_ Equation 10 and 15
        
        :param task: the analyzed task
        :type task: model.Task
        :param q: the index of the activation for which candidates are evaluated
        :type q: integer
        :rtype: set of integers 
        """
        busy_period = self.edf_busy_period(task)
        #print "busy_period", busy_period

        # will contain all deadlines of all resource interferers in the busy period
        candidate_deadlines = list([task.deadline])

        for ti in task.get_resource_interferers():

            n = ti.in_event_model.eta_plus(busy_period) # amount of activations of ti in the busy period
            #print "name:", ti.name, "n:", "range:", range(1, n + 1)
            ti_deadlines = [ti.in_event_model.delta_min(p) + ti.deadline for p in range(1, n + 1)] # instances of deadlines for ti
            #print "ti_deadlines", ti_deadlines
            candidate_deadlines.extend(ti_deadlines)
        #print "deadlines", candidate_deadlines
        # calculate the activation instances so that the deadlines of task and the tis match

        candidate_activations = set()
        for di in candidate_deadlines:
            ac = max(0, di - task.deadline)
            #if ((ac - task.in_event_model.delta_min(q) >= 0) and
            #   (ac <= busy_period - task.wcet)): # the arrival of the first event must be in the busy window
            if ((ac >= task.in_event_model.delta_min(q)) and
               (ac < task.in_event_model.delta_min(q + 1))): # the arrival of the first event must be in the busy window
                candidate_activations.add(ac)

        return candidate_activations

    def _eta_activation_time(self, task, q, ti, w, activation_time):
        """ Returns the number of interference activations orginating from task ti
        which is seen during the execution of q activations of task,
        assuming the q-th activation was released at activation_time.
        
        similar to [Palencia2003]_ Equation 9
        
        :param task: the analyzed task
        :type task: model.Task
        :param q: the amount of activations for task
        :type q: integer
        :param ti: interference task
        :type ti: model.Task
        :param w: busy window length
        :type w: integer
        :param activation_time: activation time (relative to the busy window start!) 
        :type activation_time: integer
        :rtype: amount of activations as integer 
        """

        # all activations in the current window
        n_ti = ti.in_event_model.eta_plus(w)

        deadline_task = activation_time + task.deadline

        # all activations which have a deadline before tasks's deadline (and thus have a higher priority)
        n_before_deadline = ti.in_event_model.eta_plus_closed(deadline_task - ti.deadline)
        #print "ti: ", ti.name, "n_ti", n_ti, "n_before_deadline", n_before_deadline, "w_deadline", deadline_task - ti.deadline + EPSILON
        eta = min(n_ti, n_before_deadline)
        return max(0, eta)

    def _window_candidate(self, task, q, activation_time):
        w = q * task.wcet
        #print "candidate activation_time:", activation_time
        while True:
            #print " - w:", w
            #logging.debug("e: %d", q * task.wcet)
            s = 0
            #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                eta = self._eta_activation_time(task, q, ti, w, activation_time)
                #print " - ti", ti.name, "eta", eta
                s += ti.wcet * eta

            w_new = q * task.wcet + s
            #print ("w_new: ", w_new)
            if w == w_new:
                break
            w = w_new

        assert(w >= q * task.wcet)
        return w


    def b_plus(self, task, q, details=False):
        """ time required to process q subsequent activations of task
         
        :param task: the analyzed task
        :type task: model.Task
        :param q: the amount of activations for task
        :type q: integer
        :rtype: integer
        """
        assert(task.deadline != None)
        assert(task.wcet >= 0)

        activation_candidates = self._activation_time_candidates(task, q)
        #print "amount of candidates:", activation_candidates
        w = 0
        a = 0
        for ac in activation_candidates:
            w_new = self._window_candidate(task, q, ac) - ac + task.in_event_model.delta_min(q)
            #print "  -> window_candidate:", w_new
            w_new = w_new
            if w_new > w:
                w = w_new
                a = ac

        #print "  -----> w_max:", w, "ac:", a
        if details:
            # TODO: implement details==True
            return dict()
        else:
            return w


    def stopping_condition(self, task, q, w):
        """ Return true if a sufficient number of activations q have been evaluated
        for a task during the busy-time w under EDF scheduling.

        :param task: the analyzed task
        :type task: model.Task
        :param q: the number of activations
        :type q: integer        
        :param w: the current busy-time
        :type w: integer
        :rtype: integer (max. busy-time for q activations) 
        """

        if task.in_event_model.delta_min(q + 1) >= self.edf_busy_period(task):
            return True
        return False


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


class SPNPScheduler(analysis.Scheduler):
    """ Static-Priority-Non-Preemptive Scheduler
        
    Priority is stored in task.scheduling_parameter,
    smaller priority number -> right of way
    
    Policy for equal priority is FCFS (i.e. max. interference).
    """

    def __init__(self, priority_cmp=prio_high_wins_equal_fifo, ctx_switch_overhead=0, cycle_time=EPSILON):
        """        
        :param priority_cmp: function to evaluate priority comparison of the form foo(a,b). if foo(a,b) == True, then "a" is more important than "b"
        :param cycle_time: time granularity of the scheduler, see [Bate1998]_ E.q. 4.14
        :param ctx_switch_overhead: context switching overhead (or interframe space for transmission lines)
        """
        analysis.Scheduler.__init__(self)

        ## time granularity of the scheduler
        self.cycle_time = cycle_time

        ## Context-switch overhead
        self.ctx_switch_overhead = ctx_switch_overhead

        ## priority ordering
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


    def b_plus(self, task, q, details=False):
        """ Return the maximum time required to process q activations
        """
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        b = self._blocker(task) + self.ctx_switch_overhead

        w = (q - 1) * (task.wcet + self.ctx_switch_overhead) + b

        while True:
            #logging.debug("w: %d", w)
            #logging.debug("e: %d", q * task.wcet)
            s = 0
            #logging.debug(task.name+" interferers "+ str([i.name for i in task.get_resource_interferers()]))
            for ti in task.get_resource_interferers():
                assert(ti.scheduling_parameter != None)
                assert(ti.resource == task.resource)
                if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter): # equal priority also interferes (FCFS)
                    s += (ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w + self.cycle_time)
                    #logging.debug("e: %s %d x %d", ti.name, ti.wcet, ti.in_event_model.eta_plus(w))

            w_new = (q - 1) * (task.wcet + self.ctx_switch_overhead) + b + s
            #print ("w_new: ", w_new)
            if w == w_new:

                if details:
                    d = dict()
                    d['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    d['blocker'] = str(b)
                    for ti in task.get_resource_interferers():
                        if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):
                            d[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w + self.cycle_time)) + '*'\
                                + str(ti.wcet) + '=' + str((ti.wcet + self.ctx_switch_overhead) * ti.in_event_model.eta_plus(w + self.cycle_time))
                    return d
                else:
                    w += task.wcet
                    assert(w >= q * task.wcet)
                    return w
                break
            w = w_new


class SPPOffsetScheduler(analysis.Scheduler):


    def stopping_condition(self, task, q, w):
        # TODO: Check!!!        
        return analysis.Scheduler.stopping_condition(self, task, q, w)


    def calculate_candidates(self, task):
        """
            Identifies the transactions on the local component, by looking at the event streams.
            Then it itentifies possible candidate tasks per stream and calculates the
            cartesian product which is used for determining the worst case
        """
        logger.debug("calculate_candidates %s", task.name)
        tasks_in_transaction = dict()
        transactions = set()

        tasks_in_transaction[task.path] = [i for i in task.path.tasks if i.resource == task.resource and  i.scheduling_parameter < task.scheduling_parameter]
        tasks_in_transaction[task.path].append(task)
        transactions.add(task.path)

        for ti in task.get_resource_interferers():
            if ti.scheduling_parameter < task.scheduling_parameter:
                tasks = [i for i in ti.path.tasks if i.resource == task.resource]
                if len(tasks) > 0:
                    tasks_in_transaction[ti.path] = tasks
                    transactions.add(ti.path)

        for trans in transactions:
            logger.debug("identified the following transaction %s ntasks: %d ", trans, len(tasks_in_transaction[trans]))


        candidates = list()
        for element in itertools.product(*(tasks_in_transaction.values())):
            candidates.append(element)

        logger.debug("transactions: %d", len(transactions))
        logger.debug("num cands: %d", len(candidates))

        return tasks_in_transaction, candidates

    def phi_ijk(self, task_ij, task_ik):
        """ Phase between task task_ij and the critical instant initiated with task_ik
            Eq. 17 Palencia2002
        """

        #T_i= task_ij.min_average_between_two_events()
        T_i = task_ij.in_event_model.P
        print task_ij, task_ij.in_event_model.P
        assert T_i > 0

        phi_ik = task_ik.in_event_model.phi
        phi_ij = task_ij.in_event_model.phi
        J_ik = task_ik.in_event_model.J

        return T_i - (phi_ik + J_ik - phi_ij) % T_i

    def transaction_contribution(self, tasks_in_transaction, task_ik, task, t):
        w = 0
        T_i = task_ik.in_event_model.P
        assert(T_i > 0)
        for ti in tasks_in_transaction:
            # The period (T_i) for all tasks in the transaction is the same 
            assert task_ik.in_event_model.P == ti.in_event_model.P
            J_ij = ti.in_event_model.J
            phi = self.phi_ijk(ti, task_ik)
            #print "phi", phi
            #print "T_i", T_i
            #print "t", t
            n = math.floor((float(J_ij + phi)) / T_i) + math.ceil((float(t - phi) / float(T_i)))
            #print "n", n
            w += n * ti.wcet
        return w

    def w_spp_candidate(self, tasks_in_transaction, task, candidate, q):

        #initiator of the critical instant for the transaction of task
        va = [x for x in candidate if task.path == x.path][0]
        T = task.in_event_model.P

        w = float(task.wcet)

        while True:
            #print "---------------------"
            #print "phi_ijk(task, va)", phi_ijk(task, va)
            w_new = (q + math.floor((task.in_event_model.J + self.phi_ijk(task, va)) / float(T))) * task.wcet
            logger.debug("   w_new: %f", w_new)
            #print "w_new", w_new
            for i in candidate:
                if i == task:
                    continue
                w_trans = self.transaction_contribution(tasks_in_transaction[i.path], i, task, w)
                logger.debug("   w_trans: %f", w_trans)
                #print "w_trans", w_trans
                w_new += w_trans
            if w_new == w:
                break
            w = w_new

        #w += task.in_event_model.phi - phi_ijk(task, va) + task.in_event_model.P
        w += -1 * self.phi_ijk(task, va) + task.in_event_model.P - task.in_event_model.J

        assert w >= task.wcet

        return w



    def b_plus(self, task, q, details=False):
        """ Return the maximum time required to process q activations
            smaller priority number -> right of way
        """

        if options.get_opt('propagation') != "jitter_offset":
            raise options.argparse.ArgumentError("propagation must be set to \"jitter_offset\"")

        assert(q > 0)
        assert(task.scheduling_parameter != None)
        assert(task.wcet >= 0)

        logger.debug("w_spp_offset for " + task.name + " " + str(q) + " P:" + str(task.in_event_model.P) + " J:" + str(task.in_event_model.J))

        tasks_in_transaction, candidates = self.calculate_candidates(task)
        w = 0
        for candidate in candidates:
            w = max(w, self.w_spp_candidate(tasks_in_transaction, task, candidate, q - 1))
        logger.debug("window for %s is %f", task.name, w)
        assert(w >= q * task.wcet)
        if details:
            # TODO: Implement details
            return dict()
        else:
            return w


class SPPScheduler(analysis.Scheduler):
    """ Static-Priority-Preemptive Scheduler
    
    Priority is stored in task.scheduling_parameter,
    smaller priority number -> right of way
    
    Policy for equal priority is FCFS (i.e. max. interference).
    """


    def __init__(self, priority_cmp=prio_low_wins_equal_fifo):
        analysis.Scheduler.__init__(self)

        ## priority ordering
        self.priority_cmp = priority_cmp

    def b_plus(self, task, q, details=False):
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
                assert(w >= q * task.wcet)
                if details:
                    d = dict()
                    d['q*WCET'] = str(q) + '*' + str(task.wcet) + '=' + str(q * task.wcet)
                    for ti in task.get_resource_interferers():
                        if self.priority_cmp(ti.scheduling_parameter, task.scheduling_parameter):
                            d[str(ti) + ':eta*WCET'] = str(ti.in_event_model.eta_plus(w)) + '*'\
                                + str(ti.wcet) + '=' + str(ti.wcet * ti.in_event_model.eta_plus(w))
                    return d
                else:
                    return w

            w = w_new


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
