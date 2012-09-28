"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

Simple SPP example
"""

from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import graph





def trace_example():
    # this is a rather extreme trace with just two datapoints
    # pycpa will use additive extension which is a periodic extension in this case 
    periodic_trace = [0, 10]
    em = model.EventModel()
    em.set_limited_trace(periodic_trace, 1)
    print "input trace:", periodic_trace
    print "output delta(n): ", [em.delta_min(p) for p in range (1, 10)]

    # this a more realistic event model. periodic in nature with
    # a burst at time 32
    em = model.EventModel()
    bursty_trace = [0, 10 , 20 , 30, 32, 40, 50]
    em.set_limited_trace(bursty_trace, 1)
    print "input trace:", bursty_trace
    print "output delta(n): ", [em.delta_min(p) for p in range (1, 10)]

if __name__ == "__main__":
    trace_example()

