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
import analysis

# time bases
ps = 1000000000000
ns = 1000000000
us = 1000000
ms = 1000
s = 1

def str_to_time_base(s):
    """ Return the time base for the string """
    conversion = {'s':s, 'ms':ms, 'us':us, 'ns':ns, 'ps':ps}
    if s in conversion:
        return conversion[s]
    else:
        raise AssertionError

def time_base_to_str(t):
    """ Return the time base for the string """
    conversion = {s:'s', ms:'ms', us:'us', ns:'ns', ps:'ps'}
    if t in conversion:
        return conversion[t]
    else:
        raise AssertionError

def calculate_base_time(frequencies):
    lcm = LCM(frequencies)
    if lcm > ps:
        analysis.logger.error("high base-time value! consider using ps instead")
    return lcm

def cycles_to_time(value, freq, base_time, rounding="ceil"):
    """ Converts the cycle/bittimes to an absolute time in base_time
    """
    scaler = fractions.Fraction (base_time, freq)
    value = fractions.Fraction(value)
    if rounding == "ceil":
        return int(fractions.math.ceil(value * scaler))
    elif rounding == "floor":
        return int(fractions.math.floor(value * scaler))
    else:
        raise NotImplementedError("roudning %s not supported" % rounding)

def time_to_time(value, base_in, base_out, rounding="ceil"):
    """ Convert an absolute time given in base_in to another absolute time given in base_out 
    """
    scaler = fractions.Fraction (base_out) / fractions.Fraction (base_in)
    if rounding == "ceil":
        return int(fractions.math.ceil(value * scaler))
    elif rounding == "floor":
        return int(fractions.math.floor(value * scaler))
    else:
        raise NotImplementedError("roudning %s not supported" % rounding)

def time_to_cycles(value, freq, base_time, rounding="ceil"):
    """ Converts an absolute time given in the base_time domain into cycles
    """
    scaler = fractions.Fraction (base_time, freq)
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
