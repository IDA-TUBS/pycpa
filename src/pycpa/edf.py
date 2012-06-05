"""
| Copyright (C) 2012 Philip Axer, Jonas Diemer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Earliest Deadline First (EDF) scheduler 
"""

import analysis
import options

#HACK: our eta_plus is based on half-open intervals. closed intervals are simulated as eta(w + EPSILON)
EPSILON = 1e-6

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
        n_before_deadline = ti.in_event_model.eta_plus(deadline_task - ti.deadline + EPSILON)
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

