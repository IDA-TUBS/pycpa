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


from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import util

import random
import datetime
import argparse

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
                    default=["schedulers.SPPScheduler()"])
args = parser.parse_args()

def generate_golden_model(test_id = 0,max_load=0.85, max_tasks=50, max_period=10000, max_jitter = 100000, scheduler_string="schedulers.SPPScheduler()"):
    ntasks = int(random.random()*max_tasks)
    total_util = random.random()*max_load
    task_names = [str(i) for i in range(ntasks)]
    task_utilizations = util.uunifast(ntasks, total_util)
    task_jitters = [int(random.random()*max_jitter) for i in range(ntasks)]
    task_periods = [int(random.random()*max_period+1)  for i in range(ntasks)]
    task_wcets = [int(u*p) for u,p in zip(task_utilizations, task_periods)]

    code_string = "# tasks: %d total_utilization %f\n" %(ntasks, total_util)
    code_string += "s = model.System()\n"

    code_string += """r = s.bind_resource(model.Resource("R", %s))\n""" % (scheduler_string)
    for name, J,P,C in zip(task_names, task_jitters, task_periods, task_wcets):
        code_string += """task_%s = model.Task(name="T_%s", wcet=%d, scheduling_parameter=%d)\n""" %(name,name, C, int(name))
        code_string += """task_%s.in_event_model = model.PJdEventModel(P=%d, J=%d)\n""" %(name, P, J)
        code_string += """task_%s.deadline = %d\n""" % (name, P) #set a deadline for EDF
        code_string += """r.bind_task(task_%s)\n""" % (name)

    exec_locals = dict()
    exec(code_string, globals(), exec_locals)
    system = exec_locals['s']
    task_results = analysis.analyze_system(system)
    code_string += """task_results = analysis.analyze_system(s)\n"""
    code_string += """\n###########################################\n"""
    for name in task_names:
        obj_name = "task_%s"%(name)
        busy_times = str((task_results[exec_locals[obj_name]].busy_times))
        code_string += """assert task_results[task_%s].busy_times == %s\n""" % (name, busy_times)
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


from pycpa import model
from pycpa import analysis
from pycpa import schedulers
from pycpa import util\n\n\n""")
    for idx, scheduler in enumerate(args.schedulers):
        for i in range(args.tests):
            test_id = idx*args.tests + i
            generate_golden_model(test_id, args.max_load, args.max_tasks, args.max_period, args.max_jitter, scheduler)
