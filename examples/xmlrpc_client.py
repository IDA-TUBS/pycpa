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



import xmlrpc.client as xmlrpclib
import logging

try:
    proxy = xmlrpclib.ServerProxy("http://localhost:7080/")
    version = proxy.protocol()

    print("pyCPA XMLRPC Server Protocol Version:", version)

    print("Available schedulers:", proxy.get_valid_schedulers())

    proxy.set_id_type('name')

    s = proxy.new_system("system")
    print("System id:", s)

    r1 = proxy.new_resource(s, "r1")
    print("r1 id", r1)
    r2 = proxy.new_resource(s, "r2")

    proxy.assign_scheduler(r1, "spp")
    proxy.assign_scheduler(r2, "spp")

    t11 = proxy.new_task(r1, "t11")
    t12 = proxy.new_task(r1, "t12")
    t21 = proxy.new_task(r2, "t21")
    t22 = proxy.new_task(r2, "t22")

    proxy.set_attribute(t11, "wcet", 10)
    proxy.set_attribute(t11, "bcet", 5)
    proxy.set_attribute(t12, "wcet", 3)
    proxy.set_attribute(t12, "bcet", 1)
    proxy.set_attribute(t21, "wcet", 2)
    proxy.set_attribute(t21, "bcet", 2)
    proxy.set_attribute(t22, "wcet", 9)
    proxy.set_attribute(t22, "bcet", 4)

    proxy.set_attribute(t11, "scheduling_parameter", 1)
    proxy.set_attribute(t12, "scheduling_parameter", 2)
    proxy.set_attribute(t21, "scheduling_parameter", 1)
    proxy.set_attribute(t22, "scheduling_parameter", 2)

    proxy.link_task(t11, t21)
    proxy.link_task(t12, t22)

    proxy.assign_pjd_event_model(t11, 30, 5, 0)
    proxy.assign_pjd_event_model(t12, 15, 6, 0)

    proxy.graph_system_dot(s, 'xmlrpc_client_test.dot')

    results = proxy.analyze_system(s)
    print("Results id:", results)

    tasks = [t11, t12, t21, t22]
    for t in tasks:
        print("results for " + proxy.get_attribute(t, "name"))
        print(proxy.get_task_result(results, t))
except Exception as v:
    print(v)

