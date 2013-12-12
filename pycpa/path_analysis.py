""" Compositional Performance Analysis Algorithms for Path Latencies

| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

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

def end_to_end_latency_classic(path, task_results, n=1, injection_rate='max'):
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
        else if isinstance(t, model.Junction):
            # add sampling delay induced by the junction (if available)
            if t.analysis_results is not None:
                lmin += t.analysis_results.bcrt
                lmax += t.analysis_results.wcrt

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


def _event_exit_path(path, i, n):
    """ Returns the latest exit time of the n-th event
    relative to the arrival of an event 0
    (cf. Lemma 2 in [Schliecker2009recursive]_)
    """

    # logger.debug("calculating exit for task %d, n=%d" % (i, n))

    if i == -1:
        # Task -1 is the input event model of task 0,
        # so compute the arrival of n events at task 0
        e = _event_arrival_path(path, n)
    else:
        e = float('-inf')
        k_max = len(path.tasks[i - 1].busy_times)
        # print("k_max:",k_max)
        for k in range(k_max + 1):
            e_k = _event_exit_path(path, i - 1, n - k) + \
                    path.tasks[i].busy_time(k + 1)

            # print("e_k:",e_k)
            if e_k > e:
                # logger.debug("task %d, n=%d k=%d, new e=%d" % (i, n, k, e_k))
                e = e_k

    # logger.debug("exit for task %d, n=%d is %d" % (i, n, e))
    return e


def end_to_end_latency_improved(path, task_results, n=1):
    """ Performs the path analysis presented in [Schliecker2009recursive]_,
    which improves results compared to end_to_end_latency() for
    n>1 and bursty event models.
    lat(n)
    FIXME: BROKEN
    """
    lmax = 0
    lmin = 0
    lmax = _event_exit_path(path, len(path.tasks) - 1, n - 1) - 0

    for t in path.tasks:
        if isinstance(t, model.Task):
            # sum up best-case response times
            lmin += t.bcrt

    # add the earliest possible release of event n
    # TODO: Can lmin be improved?
    lmin += path.tasks[0].in_event_model.delta_min(n)

    return lmin, lmax
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
