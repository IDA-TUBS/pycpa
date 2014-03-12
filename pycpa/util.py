"""
| Copyright (C) 2011, 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer
         - Jonas Diemer

Description
-----------

Various utility functions
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


import fractions
import logging
import random
import math
import itertools
import functools
from collections import deque

logger = logging.getLogger("pycpa")

# time bases
ps = 1000000000000
ns = 1000000000
us = 1000000
ms = 1000
s = 1

def window(seq, n=2):
    """Returns a sliding window (of width n) over data from the iterable
    s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ..."""
    it = iter(seq)
    result = tuple(itertools.islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result

def uunifast(num_tasks, utilization):
    """ Returns a list of random utilizations, one per task
    [0.1, 0.23, ...]
    WCET and event model (i.e. PJd) must be calculated in a second step)
    """
    sum_u = utilization
    util = list()
    for i in range(1, num_tasks):
        next_sum_u = sum_u * math.pow(random.random(), 1.0 / float(num_tasks - i))
        util.append(sum_u - next_sum_u)
        sum_u = next_sum_u
    util.append(sum_u)
    return util

def get_next_tasks(task):
    """ return the list of next tasks for task object.
    required for _breadth_first_search """
    return task.next_tasks


def breadth_first_search(task, func=None, get_reachable_tasks=get_next_tasks):
    """ returns a set of nodes (tasks) which is reachable
    starting from the starting task.
    calls func on the first discover of a task.

    get_reachable_tasks(task) specifies a function which returns all tasks
    considered immediately reachable for a given task.
    """
    marked = set()
    queue = deque()

    queue.append(task)
    marked.add(task)

    if func is not None:
        func(task)

    while len(queue) > 0:
        v = queue.popleft()
        for e in get_reachable_tasks(v):
            if e not in marked:
                if func is not None:
                    func(task)
                marked.add(e)
                queue.append(e)
    return marked


def generate_distance_map(system):
    """ Precomputes a distance-map for all tasks in the system.
    """
    dist = dict()
    for r in system.resources:
        for t in r.tasks:
            dist[t] = dijkstra(t)
    return dist

def dijkstra(source):
    """ Calculates a distance-map from the source node
    based on the dijkstra algorithm
    The edge weight is 1 for all linked tasks
    """
    dist = dict()
    previous = dict()

    # since we don't have a global view on the graph, we aquire a set of all
    # nodes using BFS
    nodes = breadth_first_search(source)

    for v in nodes:
        dist[v] = float('inf')
        previous[v] = None

    # init source
    dist[source] = 0

    # working set of nodes to revisit
    Q = nodes.copy()

    while len(Q) > 0:
        # get node with minimum distance
        u = min(Q, key=lambda x: dist[x])

        if dist[u] == float('inf'):
            break  # all remaining vertices are inaccessible from source

        Q.remove(u)

        for v in u.next_tasks:  # where v has not yet been removed from Q.
            alt = dist[u] + 1
            if alt < dist[v]:
                dist[v] = alt
                previous[v] = u
                Q.add(v)
    return dist

def additive_extension(additive_func, q, q_max, cache=None, cache_offset=1):
    """ Additive extension for event models.
    Any sub- or super- additive function additive_func valid in the domain q \in [0, q_max]
    is extended and the approximited value f(q) is returned.
    NOTE: this cannot be directly used with delta curves, since they are "1-off",
    thus if you supply a delta function to additive_func, note to add 1 and supply q-1.
    e.g. util.additive_extension(lambda x: self.delta_min(x + 1), n - 1, q_max)
    """
    if cache is None:
        cache = dict()
    assert q_max > 0
    d  = cache.get(q + cache_offset, None)  # cache is in delta domain (thus +1)
    if d is None:
        if q <= q_max:
            d = additive_func(q)

        elif q == float('inf'):
            d = float('inf')
        else:
            div = q // q_max
            rem = q % q_max
            d = div * additive_func(q_max) + additive_func(rem)

    cache[q] = d
    return d

def recursive_max_additive(additive_func, q, q_max, cache=None, cache_offset=1):
    """ Sub-additive extension for event models.
    Any sub-additive function additive_func valid in the domain q \in [0, q_max]
    is extended and the value f(q) is returned.
    It is optional to supply a cache dictionary for speedup.

    NOTE: this cannot be directly used with delta curves, since they are "1-off",
    thus if you supply a delta function to additive_func, note to add 1 and supply q-1.
    e.g. ret = util.recursive_max_additive(lambda x: self.delta_min(x + 1), n - 1, q_max, self.delta_min_cache)

    By default, the cache is filled according to the delta domain notion, so it can be used with delta-based event models.
    To override this behavior, change the cache_offset parameter to zero
    """
    if cache is None:
        cache = dict()
    if q <= q_max:
        return additive_func(q)
    else:
        ret = 0
        for a in range(1, q_max + 1):
            b = cache.get(q - a + cache_offset, None)  # cache is in delta domain (thus +1)
            if b is None:
                b = recursive_max_additive(additive_func, q - a, q_max, cache, cache_offset)
                cache[q - a + cache_offset] = b
            # print a, q - a, additive_func(a), b, additive_func(a) + b
            ret = max(ret, additive_func(a) + b)
        # print ret
        return ret


def recursive_min_additive(additive_func, q, q_max, cache=None, cache_offset=1):
    """ Super-additive extension for event models.
    Any additive function additive_func valid in the domain q \in [0, q_max]
    is extended and the value f(q) is returned.
    It is optional to supply a cache dictionary for speedup.

    NOTE: this cannot be directly used with delta curves, since they are "1-off",
    thus if you supply a delta function to additive_func, note to add 1 and supply q-1.
    e.g. ret = util.recursive_min_additive(lambda x: self.delta_plus(x + 1), n - 1, q_max, self.delta_plus_cache)

    By default, the cache is filled according to the delta domain notion, so it can be used with delta-based event models.
    To override this behavior, change the cache_offset parameter to zero
    """
    if cache is None:
        cache = dict()
    if q <= q_max:
        return additive_func(q)
    else:
        ret = float('inf')
        for a in range(1, q_max + 1):
            b = cache.get(q - a + cache_offset, None)  # cache is in delta domain (thus +1)
            if b is None:
                b = recursive_min_additive(additive_func, q - a, q_max, cache, cache_offset)
                cache[q - a + cache_offset] = b
            # print a, q - a, additive_func(a), b, additive_func(a) + b
            ret = min(ret, additive_func(a) + b)
        return ret


def str_to_time_base(unit):
    """ Return the time base for the string """
    conversion = {'s': s, 'ms': ms, 'us': us, 'ns': ns, 'ps': ps}
    if unit in conversion:
        return conversion[unit]
    else:
        raise ValueError


def time_base_to_str(t):
    """ Return the time base for the string """
    conversion = {s: 's', ms: 'ms', us: 'us', ns: 'ns', ps: 'ps'}
    if t in conversion:
        return conversion[t]
    else:
        raise ValueError


def calculate_base_time(frequencies):
    common_timebase = LCM(frequencies)
    if common_timebase > ps:
        error_msg = "high base-time value! consider using ps instead"
        logger.error(error_msg)
    return int(common_timebase)


def cycles_to_time(value, freq, base_time, rounding="ceil"):
    """ Converts the cycle/bittimes to an absolute time in base_time
    """
    scaler = fractions.Fraction(base_time, freq)
    value = fractions.Fraction(value)
    if rounding == "ceil":
        return int(fractions.math.ceil(value * scaler))
    elif rounding == "floor":
        return int(fractions.math.floor(value * scaler))
    else:
        raise NotImplementedError("rounding %s not supported" % rounding)


def time_to_time(value, base_in, base_out, rounding="ceil"):
    """ Convert an absolute time given in base_in
    to another absolute time given in base_out
    """
    scaler = fractions.Fraction(base_out) / fractions.Fraction(base_in)
    if rounding == "ceil":
        return int(fractions.math.ceil(value * scaler))
    elif rounding == "floor":
        return int(fractions.math.floor(value * scaler))
    else:
        raise NotImplementedError("rounding %s not supported" % rounding)


def time_to_cycles(value, freq, base_time, rounding="ceil"):
    """ Converts an absolute time given in
    the base_time domain into cycles
    """
    scaler = fractions.Fraction(base_time, freq)
    value = fractions.Fraction(value)
    if rounding == "ceil":
        return int(fractions.math.ceil(value / scaler))
    elif rounding == "floor":
        return int(fractions.math.floor(value / scaler))
    else:
        raise NotImplementedError("rounding %s not supported" % rounding)


def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    return fractions.gcd(a, b)

def lcm(a, b):
    """ Return lowest common multiple."""
    return (a * b) / gcd(a, b)


def GCD(terms):
    """ Return gcd of a list of numbers."""
    return functools.reduce(fractions.gcd, terms)


def LCM(terms):
    """Return lcm of a list of numbers."""
    return functools.reduce(lcm, terms)


def combinations_with_replacement(iterable, r):
    """combinations_with_replacement('ABC', 2) --> AA AB AC BB BC CC """
    # number items returned:  (n+r-1)! / r! / (n-1)!
    pool = tuple(iterable)
    n = len(pool)
    if not n and r:
        return
    indices = [0] * r
    yield tuple(pool[i] for i in indices)
    while True:
        for i in reversed(list(range(r))):
            if indices[i] != n - 1:
                break
        else:
            return
        indices[i:] = [indices[i] + 1] * (r - i)
        yield tuple(pool[i] for i in indices)


def get_path(t_src, t_dst):
    """ Find path between tasks t_src and t_dst.
        Returns a path as list() or None if no path was found.
        NOTE: There is no protection against cycles!
    """

    def _get_path_recursive(t_src, t_dst):
        if t_src == t_dst:
            return (True, [t_src]) 

        for t in t_src.next_tasks:    
            (found_dst, v) = _get_path_recursive(t, t_dst)
            if found_dst:
                return (True, [t_src] + v)
        return (False, None)

    (path_found, path) = _get_path_recursive(t_src, t_dst)
    return path


def time_str_to_time(time_str, base_out, rounding="ceil"):
    """ Convert strings like "100us" or "10 ns" to an integer
        representation in base_out.
    """
    import re

    m = re.match(r"([0-9]+)(\ *)([a-zA-Z]+)", time_str) 
    assert len(m.groups()) == 3
    value_str = m.group(1)
    space_str = m.group(2)
    time_base_str = m.group(3)
    assert len(time_str) == len(value_str) + len(space_str) + len(time_base_str)

    value_int = int(value_str)

    return time_to_time(value_int, str_to_time_base(time_base_str), base_out, rounding)


def bitrate_str_to_bits_per_second(bitrate_str):
    """ Convert bitrate strings like "100MBit/s" or "1 Gbit/s"
        to an integer representation in Bit/s.
    """
    import re

    m = re.match(r"([0-9\.]+)(\ *)([a-zA-Z])([bB]it/s)", bitrate_str)
    assert len(m.groups()) == 4

    value_str = m.group(1)
    space_str = m.group(2)
    scale = m.group(3)
    bits_str = m.group(4)
    assert len(bitrate_str) == len(value_str) + len(space_str) + len(scale) + len(bits_str)
    assert len(scale) == 1
    assert re.match(r"[kKmMgG]", scale) != None

    bits_per_second_int = int(value_str)
    if re.match(r"[kK]", scale):
        bits_per_second_int *= 1000
    elif re.match(r"[mM]", scale):
        bits_per_second_int *= 1000000
    elif re.match(r"[gG]", scale):
        bits_per_second_int *= 1000000000
    else:
        assert False
   
    return bits_per_second_int 




# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
