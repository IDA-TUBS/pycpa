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

import fractions
import logging
from collections import deque

logger = logging.getLogger("pycpa")

# time bases
ps = 1000000000000
ns = 1000000000
us = 1000000
ms = 1000
s = 1


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

def additive_extension(additive_func, q, q_max):
    """ Additive extension for event models.
    Any sub- or super- additive function additive_func valid in the domain q \in [0, q_max]
    is extended and the approximited value f(q) is returned.
    NOTE: this cannot be directly used with delta curves, since they are "1-off",
    thus if you supply a delta function to additive_func, note to add 1 and supply q-1.
    e.g. util.additive_extension(lambda x: self.delta_min(x + 1), n - 1, q_max)
    """
    if q <= q_max:
        return additive_func(q)
    elif q == float('inf'):
        return float('inf')
    else:
        div = q / q_max
        rem = q % q_max
        return div * additive_func(q_max) + additive_func(rem)


def recursive_max_additive(additive_func, q, q_max, cache=dict()):
    """ Sub-additive extension for event models.
    Any sub-additive function additive_func valid in the domain q \in [0, q_max]
    is extended and the value f(q) is returned.
    It is optional to supply a cache dictionary for speedup.

    NOTE: this cannot be directly used with delta curves, since they are "1-off",
    thus if you supply a delta function to additive_func, note to add 1 and supply q-1.
    e.g. ret = util.recursive_max_additive(lambda x: self.delta_min(x + 1), n - 1, q_max, self.delta_min_cache)

    The cache is filled according to the delta domain notion, so it can be used with delta-based event models.
    """
    if q <= q_max:
        return additive_func(q)
    else:
        ret = 0
        for a in range(1, q_max + 1):
            b = cache.get(q - a + 1, None) # cache is in delta domain (thus +1)
            if b is None:
                b = recursive_max_additive(additive_func, q - a, q_max, cache)
                cache[q - a + 1] = b
            #print a, q - a, additive_func(a), b, additive_func(a) + b
            ret = max(ret, additive_func(a) + b)
        #print ret
        return ret


def recursive_min_additive(additive_func, q, q_max, cache=dict()):
    """ Super-additive extension for event models.
    Any additive function additive_func valid in the domain q \in [0, q_max]
    is extended and the value f(q) is returned.
    It is optional to supply a cache dictionary for speedup.

    NOTE: this cannot be directly used with delta curves, since they are "1-off",
    thus if you supply a delta function to additive_func, note to add 1 and supply q-1.
    e.g. ret = util.recursive_min_additive(lambda x: self.delta_plus(x + 1), n - 1, q_max, self.delta_plus_cache)

    The cache is filled according to the delta domain notion, so it can be used with delta-based event models.
    """
    if q <= q_max:
        return additive_func(q)
    else:
        ret = float('inf')
        for a in range(1, q_max + 1):
            b = cache.get(q - a + 1, None) # cache is in delta domain (thus +1)
            if b is None:
                b = recursive_min_additive(additive_func, q - a, q_max, cache)
                cache[q - a + 1] = b
            #print a, q - a, additive_func(a), b, additive_func(a) + b
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
    return common_timebase


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
        raise NotImplementedError("roudning %s not supported" % rounding)


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
        raise NotImplementedError("roudning %s not supported" % rounding)


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
        raise NotImplementedError("roudning %s not supported" % rounding)


def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    """ Return lowest common multiple."""
    return (a * b) / gcd(a, b)


def GCD(terms):
    """ Return gcd of a list of numbers."""
    return reduce(gcd, terms)


def LCM(terms):
    """Return lcm of a list of numbers."""
    return reduce(lcm, terms)


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
