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

Generates a crude golden model from the current version.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from pycpa import options
from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import util

import random
import datetime
import argparse

import sys
import inspect
import time

all_schedulers = list()
for name, obj in inspect.getmembers(schedulers):
    if inspect.isclass(obj) and issubclass(obj, analysis.Scheduler):
        all_schedulers.append("schedulers.%s()" % (name))

parser = argparse.ArgumentParser(description="Golden model generator for single resource schedulers")

parser.add_argument('--max_tasks', type=int,
                    help='maximum tasks per testcase, actual number in the range [1, max_tasks]',
                    default=50)
parser.add_argument('--max_period', type=int,
                    help='maximum period, actual number in the range[1, max_period]',
                    default=10000)
parser.add_argument('--max_jitter', type=int,
                    help='maximum jitter, actual number in the range[1, max_jitter]',
                    default=50000)
parser.add_argument('--max_load', type=float,
                    help='maximum load, actual load in [0, max_load]',
                    default=0.85)
parser.add_argument('--tests', type=int,
                    help='amount of testcases to generate',
                    default=10)
parser.add_argument('schedulers',metavar='S', type=str, nargs='*',
                    help='instantiation string of the scheduler object',
                    default=all_schedulers)
args = parser.parse_args()

def generate_golden_model(test_id = 0,max_load=0.85, max_tasks=50, max_period=10000, max_jitter = 100000, scheduler_string="schedulers.SPPScheduler()"):
    ntasks = int(random.random()*max_tasks)
    total_util = random.random()*max_load
    task_ids = [str(i+1) for i in range(ntasks)]
    task_utilizations = util.uunifast(ntasks, total_util)
    task_jitters = [int(random.random()*max_jitter) for i in range(ntasks)]
    task_periods = [int(random.random()*max_period+1)  for i in range(ntasks)]
    task_wcets = [int(u*p) for u,p in zip(task_utilizations, task_periods)]

    code_string = "# tasks: %d total_utilization %f\n" %(ntasks, total_util)
    code_string += "s = model.System()\n"

    code_string += """r1 = s.bind_resource(model.Resource("R1", %s))\n""" % (scheduler_string)
    code_string += """r2 = s.bind_resource(model.Resource("R2", %s))\n""" % (scheduler_string)
    for name, J,P,C in zip(task_ids, task_jitters, task_periods, task_wcets):
        #create a task on resource 1
        code_string += """task1_%s = model.Task(name="task1_%s", wcet=%d, scheduling_parameter=%d)\n""" %(name,name, C, int(name))
        code_string += """task1_%s.in_event_model = model.PJdEventModel(P=%d, J=%d)\n""" %(name, P, J)
        code_string += """task1_%s.deadline = %d\n""" % (name, P) #set a deadline for EDF
        code_string += """r1.bind_task(task1_%s)\n""" % (name)
        #create a task on resource 2
        code_string += """task2_%s = model.Task(name="task2_%s", wcet=%d, scheduling_parameter=%d)\n""" %(name,name, C, int(name))
        code_string += """task2_%s.deadline = %d\n""" % (name, P) #set a deadline for EDF
        code_string += """task1_%s.link_dependent_task(task2_%s)\n""" % (name, name)
        code_string += """r2.bind_task(task2_%s)\n""" % (name)

    exec_locals = dict()
    exec(code_string, globals(), exec_locals)
    system = exec_locals['s']

    task_names = list()
    for r in system.resources:
        for t in r.tasks:
            task_names.append(t.name)

    # override event model propagation
    for propagation in options.propagation_methods:
        max_iterations_code = "options.set_opt('max_iterations', float('inf'))\n"
        propagation_code = "options.set_opt('propagation', '%s')\n" % (propagation)
        exec(propagation_code, globals(), exec_locals)
        exec(max_iterations_code, globals(), exec_locals)
        print("### DEBUG: evaluating for %s / %s" % (propagation, scheduler_string))
        task_results = analysis.analyze_system(system)
        code_string += """# setting options\n"""
        code_string += max_iterations_code
        code_string += propagation_code
        code_string += """##########################################\n"""
        code_string += """task_results = analysis.analyze_system(s)\n"""
        code_string += """\n###########################################\n"""
        for obj_name in task_names:
            busy_times = str((task_results[exec_locals[obj_name]].busy_times))
            wcrt_code = "task_results[%s].wcrt" % obj_name
            bcrt_code = "task_results[%s].bcrt" % obj_name
            code_string += """#check busy times\n"""
            code_string += """assert task_results[%s].busy_times == %s\n""" % (obj_name, busy_times)

            code_string += """#check type wcrt\n"""
            code_string += """assert type(%s) == int\n""" % (wcrt_code)

            code_string += """#check type bcrt\n"""
            code_string += """assert type(%s) == int\n""" % (bcrt_code)

            code_string += """#check busy times\n"""
            code_string += """assert %s == %d\n""" % (wcrt_code, task_results[exec_locals[obj_name]].wcrt)

    code_string += """return s\n\n"""

    #indent
    code_string = "\n".join( ["    %s" %(line) for line in code_string.splitlines()])
    function_string = "def testcase_%d():\n%s" % (test_id, code_string)
    print(function_string)


if __name__ == "__main__":

    print("""\"\"\"
| Copyright (C) 2013 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Philip Axer

Description
-----------
This golden model was automatically generated on %s
          tests:      %d
          max_load :  %f
          max_tasks:  %d
          max_period: %d
          max_jitter: %d
          schedulers: %s
\"\"\"\n\n
""" % (datetime.datetime.now(), args.tests, args.max_load, args.max_tasks, args.max_period, args.max_jitter, str(args.schedulers)))
    print("""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from pycpa import options
from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import util\n\n\n""")

    start_time = time.time()

    for idx, scheduler in enumerate(args.schedulers):
        for i in range(args.tests):
            test_id = idx*args.tests + i
            generate_golden_model(test_id, args.max_load, args.max_tasks, args.max_period, args.max_jitter, scheduler)

    end_time = time.time()
    print("\n\n# time to generate: %.1f seconds" % (end_time - start_time))

