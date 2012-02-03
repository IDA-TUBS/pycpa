"""
| Copyright (C) 2007-2012 Jonas Diemer
| TU Braunschweig, Germany
| All rights reserved

:Authors:
         - Jonas Diemer

Description
-----------

Router model
"""

import copy
import model
import slip

class Router:
    """ Router containing input, output resources 
    This class provides easy generation of a "router" for analysis.
    To the analysis function, a "router" does not exist - 
    it is just a set of tasks, resources and mutexes. 
    """

    def __init__(self, n=3, w_func=slip.w_slip, name="R?", flit_time=1):
        self.input = []
        self.output = []
        self.tasks = []
        self.flit_time = flit_time
        self.name = name
        for i in range(0, n):
            self.input.append(model.Mutex(name + ".IN" + str(i)))
            self.output.append(model.Resource(name + ".OUT" + str(i), w_func))
        #logging.debug(self.input + self.output)


    def add_task(self, i, o):
        # generate a unique name
        name = self.name + "-T%i%i" % (i, o)
        cnt = 0
        for t in self.tasks:
            if t.name.startswith(name): cnt += 1
        if cnt > 0:
            name += "_" + str(cnt)

        task = model.Task(name)
        task.bcet = self.flit_time
        task.wcet = self.flit_time
        task.bind_mutex(self.input[i])
        task.bind_resource(self.output[o])
        self.tasks.append(task)
        return task

    def add_task_cT(self, i, o, c, T):
        task = self.add_task(i, o)
        task.in_event_model = model.EventModel(c=c, T=T)
        return task

    def print_task_set(self):
        for t in self.tasks:
            print t.name, t.in_event_model


def generate_gopalakrishnan_router(r):
    ''' make event model infinite for all tasks that have nonzero event models
    Takes an event model and creates the corresponding model with infinite streams.
    When this altered model is analyzed wit w_slip_symmetric, 
    It produces a result equivalent to the equation on page 6 in gropalakrishnan2006real-time
    However, a WCRT can not be determined, as all tasks request infinite service.
    '''
    r_new = copy.deepcopy(r)
    for t in r_new.tasks:
        if t.in_event_model.eta_plus(1) != 0:
            t.in_event_model = model.EventModel(1, 1)
    return r_new

def copy_router(r, w_func):
    ''' copy router and change w-function for all resources '''
    r_new = copy.deepcopy(r)
    for r in r_new.output:
        r.w_function = w_func
    return r_new
