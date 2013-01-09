#!/usr/bin/env python
"""
| Copyright (C) 2013 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------

XML-RPC client for pyCPA. Resembles a client-side version of the spp-test.
"""



import xmlrpclib
import logging

try:
    proxy = xmlrpclib.ServerProxy("http://localhost:7080/")
    version = proxy.protocol()

    print "pyCPA XMLRPC Server Protocol Version:", version

    s = proxy.new_system("system")
    r1 = proxy.new_resource("r1")
    r2 = proxy.new_resource("r2")

    proxy.assign_scheduler(r1, "spp")
    proxy.assign_scheduler(r2, "spp")

    t11 = proxy.new_task(r1, "t11")
    t12 = proxy.new_task(r1, "t12")
    t21 = proxy.new_task(r2, "t21")
    t22 = proxy.new_task(r2, "t22")

    proxy.set_task_parameter(t11, "wcet", 10)
    proxy.set_task_parameter(t11, "bcet", 5)
    proxy.set_task_parameter(t12, "wcet", 3)
    proxy.set_task_parameter(t12, "bcet", 1)
    proxy.set_task_parameter(t21, "wcet", 2)
    proxy.set_task_parameter(t21, "bcet", 2)
    proxy.set_task_parameter(t22, "wcet", 9)
    proxy.set_task_parameter(t22, "bcet", 4)

    proxy.set_task_parameter(t11, "scheduling_parameter", 1)
    proxy.set_task_parameter(t12, "scheduling_parameter", 2)
    proxy.set_task_parameter(t21, "scheduling_parameter", 1)
    proxy.set_task_parameter(t22, "scheduling_parameter", 2)

    proxy.link_task(t11, t21)
    proxy.link_task(t12, t22)

    proxy.assign_event_model(t11, "PJd", "30,5,0")
    proxy.assign_event_model(t12, "PJd", "15,6,0")

    proxy.analyze_system()

    tasks = [t11, t12, t21, t22]
    for t in tasks:
        print "results for " + proxy.get_task_parameter(t, "name")
        print proxy.get_task_result(t)
except Exception, v:
    print v
