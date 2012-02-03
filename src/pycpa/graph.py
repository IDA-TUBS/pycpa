"""
| Copyright (C) 2007-2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved. 
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

This module contains methods to plot task/architecture graphs of your system
"""

from . import model

try:
    import pygraphviz
except ImportError:
    print "Sorry, you don't have the pygraphviz module installed."
    print "Please install or reconfigure pygraphviz"
    print "and try again."



def get_junction_name(j):
    name = 'Junction ' + j.name + ":"
    for p in j.prev_tasks:
        name += p.name + ","
    return name


def graph_system(s, filename = None, layout = 'dot',
                 emptyResources = False, shortTasks = False,
                 execTimes = False,
                 rankdir = 'LR'):
    """ Return a graph of the system
    
    Keyword arguments:
    
    *s*
        the system
    *filename*
        if not None, the graph is plotted to this file        
    *layout*
        graphviz layout algorithm (default l'dot' works best with hierarchical graphs)
    *emptyResources*
        Plot resources that have no tasks assigned
    *shortTasks*
        Label tasks using "T_nn" instead of their potentially long name
    *execTimes*
        Show execution times for each tasks
    *rankdir*
        Layout option for graphviz
     
    """
    g = pygraphviz.AGraph(directed = 'true', compound = 'true',
                          rankdir = rankdir,
                          remincross = 'true',
                          ordering = 'out')

    # first, create all nodes
    task_num = 0
    elen = 10

    for r in s.resources:
        if len(r.tasks) == 0 and not emptyResources:
            continue # dont plot resources without tasks

        if g.has_node(r.name):
            print "graph_system warning: duplucate resource", r.name
        g.add_node(r.name, color = '#aaaacc', shape = 'none')
        res_tasks = [r.name]
        for t in r.tasks:
            if g.has_node(t.name):
                print "graph_system warning: duplucate task", t.name
            if shortTasks:
                lab = "T_" + str(task_num)
                task_num += 1
            else:
                lab = t.name
            if execTimes:
                lab += '(%g,%g)' % (t.bcet, t.wcet)
            g.add_node(t.name, label = lab)
            res_tasks.append(t.name)
            if t.mutex is not None:
                g.add_node(t.mutex.name, color = '#aaccaa', shape = 'hexagon')
            for nt in t.next_tasks:
                if isinstance(nt, model.Junction):
                    g.add_node(get_junction_name(nt), label = nt.mode, shape = 'diamond')


        g.add_subgraph(res_tasks, "cluster_" + r.name)

    # now come the connections

    for r in s.resources:
        for t in r.tasks:
            for nt in t.next_tasks:
                if isinstance(nt, model.Junction):
                    g.add_edge(t.name, get_junction_name(nt), len = elen) # edge to junction
                    for jnt in nt.next_tasks: #edges from junction
                        g.add_edge(get_junction_name(nt), jnt.name, len = elen) #, constraint = False
                else:
                    g.add_edge(t.name, nt.name, len = elen, headport = 'w', tailport = 'e') #, constraint = False

            if t.mutex is not None:
                g.add_edge(t.name, t.mutex.name, color = '#aaccaa', len = 1)

            if t.prev_task is None:
                g.add_node(str(t.in_event_model), len = 10 * elen)
                g.add_edge(str(t.in_event_model), t.name, constraint = False, style = 'dashed')


    g.layout(layout)


    if filename is not None:
        g.draw(filename)

    return g

