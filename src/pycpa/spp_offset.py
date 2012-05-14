"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

SPP Offset analysis functions Palencia,Harbour 2002
"""

import logging
import itertools
import math

import pprint
import analysis
import options

logger = logging.getLogger("spp_offset")

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



    def b_plus(self, task, q):
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
            logger.debug("evaluating candidate: %s", pprint.pformat(candidate))
            w = max(w, self.w_spp_candidate(tasks_in_transaction, task, candidate, q - 1))
        logger.debug("window for %s is %f", task.name, w)
        assert(w >= q * task.wcet)
        return w
