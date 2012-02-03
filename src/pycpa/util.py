"""
| Copyright (C) 2011 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Various utility functions
"""




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
    return reduce(lambda a, b: gcd(a, b), terms)

def LCM(terms):
    """Return lcm of a list of numbers."""
    return reduce(lambda a, b: lcm(a, b), terms)


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
