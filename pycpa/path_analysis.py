""" Compositional Performance Analysis Algorithms for Path Latencies

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

This module contains methods for the ananlysis of path latencies.
It should be imported in scripts that do the analysis.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from . import options
from . import model
from . import util

import math


def end_to_end_latency(path, task_results, n=1 , task_overhead=0,
                       path_overhead=0, **kwargs):
    """ Computes the worst-/best-case e2e latency for n tokens to pass the path.
    The constant path.overhead is added to the best- and worst-case latencies.

    :param path: the path
    :type path: model.Path
    :param n:  amount of events
    :type n: integer
    :param task_overhead: A constant task_overhead is added once per task to both min and max latency
    :type task_overhead: integer
    :param path_overhead:  A constant path_overhead is added once per path to both min and max latency
    :type path_overhead: integer
    :rtype: tuple (best-case latency, worst-case latency)
    """

    if options.get_opt('e2e_improved') == True:
        (lmin, lmax) = end_to_end_latency_improved(path, task_results,
                                                   n, **kwargs)
    else:
        (lmin, lmax) = end_to_end_latency_classic(path, task_results,
                                                  n, **kwargs)

    for t in path.tasks:
        # implcitly check if t is a junction
        if t in task_results:
            # add per-task overheads
            lmin += task_overhead
            lmax += task_overhead

    # add per-path overhead
    lmin += path_overhead + path.overhead
    lmax += path_overhead + path.overhead

    return (lmin, lmax)

def end_to_end_latency_classic(path, task_results, n=1, injection_rate='max', **kwargs):
    """ Computes the worst-/best-case end-to-end latency
    Assumes that all tasks in the system have successfully been analyzed.
    Assumes that events enter the path at maximum/minumum rate.
    The end-to-end latency is the sum of the individual task's
    worst-case response times.

    This corresponds to Definition 7.3 in [Richter2005]_.

    :param path: the path
    :type path: model.Path
    :param n:  amount of events
    :type n: integer
    :param injection_rate: assumed injection rate is maximum or minimum
    :type injection_rate: string 'max' or 'min'
    :rtype: tuple (best case latency, worst case latency)
    """

    lmax = 0
    lmin = 0

    # check if path is a list of Tasks or a Path object
    tasks = path
    if isinstance(path, model.Path):
        tasks = path.tasks

    for t in tasks:
        # implcitly check if t is a junction
        if t in task_results:
            # sum up best- and worst-case response times
            lmax += task_results[t].wcrt
            lmin += task_results[t].bcrt
        elif isinstance(t, model.Junction):
            # add sampling delay induced by the junction (if available)
            prev_task = tasks[tasks.index(t)-1]
            if prev_task in t.analysis_results:
                lmin += t.analysis_results[prev_task].bcrt
                lmax += t.analysis_results[prev_task].wcrt
        else:
            print("Warning: no task_results for task %s" % t.name)

    if injection_rate == 'max':
        # add the eastliest possible release of event n
        lmax += tasks[0].in_event_model.delta_min(n)

    elif injection_rate == 'min':
        # add the latest possible release of event n
        lmax += tasks[0].in_event_model.delta_plus(n)

    # add the earliest possible release of event n
    lmin += tasks[0].in_event_model.delta_min(n)

    return lmin, lmax


def _event_arrival_path(path, n, e_0=0):
    """ Returns the latest arrival time of the n-th event
    with respect to an event 0 of task 0 (first task in path)

    This is :math:`e_0(n)` from Lemma 1 in [Schliecker2009recursive]_.
    """
    # if e_0 is None:
        # the entry time of the first event

    if n > 0:
        e = e_0 + path.tasks[0].in_event_model.delta_plus(n + 1)
    elif n < 0:
        e = e_0 - path.tasks[0].in_event_model.delta_min(-n + 1)
    else:
        e = 0  # same event, so the difference is 0

    return e


def _event_exit_path(path, task_results, i, n, e_0=0):
    """ Returns the latest exit time of the n-th event
    relative to the arrival of an event 0
    (cf. Lemma 2 in [Schliecker2009recursive]_)
    In contrast to Lemma 2, k_max is set so that all busy times
    are taken into account.
    """

    # logger.debug("calculating exit for task %d, n=%d" % (i, n))

    if i == -1:
        # The exit of task -1 is the arrival of task 0.
        e = _event_arrival_path(path, n, e_0)
    elif path.tasks[i] not in task_results:
        # skip task if there are no results for this
        # (this may happen if, e.g., a chain analysis has been performed)
        return _event_exit_path(path, task_results, i-1, n, e_0)
    else:
        e = float('-inf')
        k_max = len(task_results[path.tasks[i]].busy_times)
        # print("k_max:",k_max)
        for k in range(1, k_max):
            e_k = _event_exit_path(path, task_results, i - 1, n - k + 1, e_0) + \
                    task_results[path.tasks[i]].busy_times[k]

            # print("e_k:",e_k)
            if e_k > e:
                # print("task %d, n=%d k=%d, new e=%d" % (i, n, k, e_k))
                e = e_k

    # print("exit for task %d, n=%d is %d" % (i, n, e))
    return e


def end_to_end_latency_improved(path, task_results, n=1, e_0=0, **kwargs):
    """ Performs the path analysis presented in [Schliecker2009recursive]_,
    which improves results compared to end_to_end_latency() for
    n>1 and bursty event models.
    lat(n)
    """
    lmax = 0
    lmin = 0
    lmax = _event_exit_path(path, task_results, len(path.tasks) - 1, n - 1, e_0) - e_0

    for t in path.tasks:
        if isinstance(t, model.Task) and t in task_results:
            # sum up best-case response times
            lmin += task_results[t].bcrt
        elif isinstance(t, model.Junction):
            print("Error: path contains junctions")
        else:
            print("Warning: no task_results for task %s" % t.name)

    # add the earliest possible release of event n
    # TODO: Can lmin be improved?
    lmin += path.tasks[0].in_event_model.delta_min(n)

    return lmin, lmax

def cause_effect_chain_data_age(chain, task_results, details=None):
    """ computes the data age of the given cause effect chain
    :param chain: model.EffectChain
    :param task_results: dict of analysis.TaskResult
    """
    return cause_effect_chain(chain, task_results, details, 'data-age')

def cause_effect_chain_reaction_time(chain, task_results, details=None):
    """ computes the data age of the given cause effect chain
    :param chain: model.EffectChain
    :param task_results: dict of analysis.TaskResult
    """
    return cause_effect_chain(chain, task_results, details, 'reaction-time')

def cause_effect_chain(chain, task_results, details=None, semantics='data-age'):
    """ computes the data age of the given cause effect chain
    :param chain: model.EffectChain
    :param task_results: dict of analysis.TaskResult
    """

    sequence = chain.task_sequence(writers_only=True)

    if details is None:
        details = dict()

    periods = [_period(t) for t in sequence]
    if util.GCD(periods) != min(periods):
        print("Error: cause-effect chain analysis requires harmonic periods")

    l_max = _phi(sequence[0]) + _jitter(sequence[0])
    details[sequence[0].name+'-PHI+J'] = l_max
    for i in range(len(sequence)):
        # add write-to-read delay for all but the last task
        if i < len(sequence)-1:
            if semantics == 'data-age':
                # add write to read delay
                delay = _calculate_backward_distance(sequence[i], sequence[i+1], task_results, 
                        details=details)
            elif semantics == 'reaction-time':
                delay = _calculate_forward_distance(sequence[i], sequence[i+1], task_results, 
                        details=details)
            else:
                raise NotImplementedException()

            l_max += delay

        # add read-to-write delay (response time) for all tasks
        delay = task_results[sequence[i]].wcrt
        details[sequence[i].name+'-WCRT'] = delay
        l_max += delay

    return l_max

def _phi(task):
    if hasattr(task.in_event_model, 'phi'):
        return task.in_event_model.phi
    else:
        return 0

def _period(task):
    return task.in_event_model.P

def _jitter(task):
    if hasattr(task.in_event_model, 'J'):
        return task.in_event_model.J
    else:
        return 0

def _calculate_backward_distance(writer, reader, task_results, details):
    """ computes backward distance (for data age)
    """

    if _period(reader) < _period(writer): # oversampling 

        candidates = set()

        if _period(writer) % _period(reader) != 0:
            candidates.add(_period(writer) + task_results[writer].wcrt - task_results[writer].bcrt)
        else:

            for n in range(int(math.ceil(_period(writer)/_period(reader)))):
                candidates.add(_rplus(reader, task_results, n) - _wmin(writer, task_results, 0))

                # include previous cycle?
                if _wplus(writer, task_results) > _rmin(reader, task_results, n):
                    candidates.add(_rplus(reader, task_results, n) - _wmin(writer, task_results, -1))

        result = max(candidates)

    else: # undersampling or same period

        candidates = set()
        candidates.add(_period(writer) + task_results[writer].wcrt - task_results[writer].bcrt)

        if _period(reader) % _period(writer) == 0:

            # include previous cycle?
            if _wplus(writer, task_results) > _rmin(reader, task_results):
                candidates.add(_rplus(reader, task_results) - _wmin(writer, task_results, -1))

            # include all other possible writers
            for n in range(int(math.ceil(_period(reader)/_period(writer)))):
                if _wplus(writer, task_results, n) <= _rplus(reader, task_results):
                    candidates.add(_rplus(reader, task_results) - _wmin(writer, task_results, n))

        result = min([c for c in candidates if c >= 0])

    details[writer.name+'-'+reader.name+'-delay'] = result
    return result

def _calculate_forward_distance(writer, reader, task_results, details):
    """ computes forward distance (for reaction time)
    """

    if _period(reader) < _period(writer): # oversampling 

        candidates = set()
        candidates.add(_period(reader))

        if _period(writer) % _period(reader) == 0:

            for n in range(int(math.ceil(_period(writer)/_period(reader)))):
                if _rmin(reader, task_results, n) >= _wplus(writer, task_results, 0):
                    candidates.add(_rplus(reader, task_results, n) - _wmin(writer, task_results, 0))

                # include previous cycle?
                if _wplus(writer, task_results) > _rmin(reader, task_results, n):
                    candidates.add(_rplus(reader, task_results, n) - _wmin(writer, task_results, -1))

        result = min([c for c in candidates if c >= 0])

    else: # undersampling or same period

        candidates = set()

        if _period(reader) % _period(writer) != 0:
            candidates.add(_period(reader))
        else:

            # include all possible writers
            for n in range(int(math.ceil(_period(reader)/_period(writer)))):
                candidates.add(_rplus(reader, task_results) - _wmin(writer, task_results, n))

                # if write time can be earlier than read time, add distance to next reader
                if _wplus(writer, task_results, n) > _rmin(reader, task_results):
                    candidates.add(_rplus(reader, task_results, 1) - _wmin(writer, task_results, n))

        result = max(candidates)

    details[writer.name+'-'+reader.name+'-delay'] = result
    return result

def _wplus(writer, task_results, n=0):
    return n*_period(writer) + _phi(writer) + task_results[writer].wcrt + _jitter(writer)

def _wmin(writer, task_results, n=0):
    return n*_period(writer) + _phi(writer) + task_results[writer].bcrt - _jitter(writer)

def _rplus(reader, task_results, n=0):
    return _wplus(reader, task_results, n) - task_results[reader].bcrt

def _rmin(reader, task_results, n=0):
    return n*_period(reader) + _phi(reader) - _jitter(reader)

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
