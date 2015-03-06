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
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division



from . import model

def get_junction_name(j):
    name = 'Junction ' + j.name + ":"
    for p in j.prev_tasks:
        name += p.name + ","
    return name

class dotgraph(object):
    """ Minimalistic implementation of the pygraphviz API.
    With this, you can write graphs to a file. """

    def __init__(self, **kwargs):
        self.dot_str = 'strict digraph {\n'
        self.dot_str += 'graph' + self._str_attr(kwargs)

        #[conpound=true, ordering=out, rankdir=LR, remincross=true\n'
        self.dot_str += ';\n'
        self.node_strs = dict()

    def _str_attr(self, attr):
        first = True
        node_str = '['
        for k,v in attr.items():
            if first:
                first = False
            else:
                node_str += ',\n'
            node_str += '{k}=\"{v}\"'.format(k=k,v=v)
        node_str += ']'
        return node_str

    def add_subnode(self, name, **kwargs):
        node_str = '"{name}"'.format(name=name)
        node_str += self._str_attr(kwargs) + ';\n'
        self.node_strs [name] = node_str

    def add_node(self, name, **kwargs):
        self.add_subnode(name, **kwargs)
        self.dot_str += self.node_strs[name]

    def add_subgraph(self, nodes, name):
        subgraph_str = 'subgraph "{name}"'.format(name=name)
        subgraph_str += '{\n'
        for n in nodes:
            subgraph_str += '  ' + self.node_strs[n] + '\n'

        subgraph_str += '}\n'
        self.dot_str += subgraph_str

    def add_edge(self, n1, n2, **kwargs):
        edge_str = '"{n1}" -> "{n2}"'.format(n1=n1, n2=n2)
        edge_str += self._str_attr(kwargs) + ';\n'
        self.dot_str += edge_str

    def write(self, filename):
        f = open(filename, 'w')
        dot_str = self.dot_str + '}\n' # close graph
        f.write(dot_str)

    def has_node(self, name):
        return name in self.node_strs

    def layout(self, l):
        pass

    def draw(self, path=None, format=None, prog='dot'):

        import os
        from subprocess import Popen, PIPE

        # try to guess format from extension
        if format is None and path is not None:
            format=os.path.splitext(path)[-1].lower()[1:]

        dot_str = self.dot_str + '}\n' # close graph
        cmd = '{prog} -T{fmt} -o {path}'.format(prog=prog, fmt=format, path=path)

        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE)
        p.communicate(input=dot_str)


    def string(self):
        return self.dot_str


def graph_system(s, filename=None, layout='dot',
                 empty_resources=False, short_tasks=False,
                 exec_times=False,
                 sched_param=False,
                 rankdir='LR',
                 show=False,
                 dotout=None,
                 use_pygraphviz=False
                 ):
    """
    Return a graph of the system

    :param s: the system
    :type s: model.System
    :param filename:  if not None, the graph is plotted to this file
    :param layout: graphviz layout algorithm (default l'dot' works best with hierarchical graphs)
    :param empty_resources:  Plot resources that have no tasks assigned
    :param short_tasks: Label tasks using "T_nn" instead of their potentially long name
    :param exec_times: Show execution times for each tasks
    :param sched_param: Show scheduling parameter for each task
    :param rankdir: Layout option for graphviz
    :param show: Show plot
    :type show: boolean
    :param dotout: If set, write a dot file to this filename
    :rtype: None
    """


    if use_pygraphviz:
        import pygraphviz
        g = pygraphviz.AGraph(directed='true', compound='true',
                          rankdir=rankdir,
                          remincross='true',
                          ordering='out'
                          )
    else:
        g = dotgraph(directed='true', compound='true',
                    rankdir=rankdir,
                    remincross='true',
                    ordering='out'
                    )
    # first, create all nodes
    task_num = 0
    elen = 10

    for r in s.resources:
        if len(r.tasks) == 0 and not empty_resources:
            continue  # dont plot resources without tasks

        if g.has_node(r.name):
            print("graph_system warning: duplicate resource %s", r.name)
        g.add_subnode(r.name, color='#aaaacc', shape='none')
        res_tasks = [r.name]
        for t in r.tasks:
            if g.has_node(t.name):
                print("graph_system warning: duplicate task %s", t.name)
            if short_tasks:
                lab = "T_" + str(task_num)
                task_num += 1
            else:
                lab = t.name
            if exec_times:
                lab += '(%g,%g)' % (t.bcet, t.wcet)
            if sched_param:
                lab += ' param: %s' % (str(t.scheduling_parameter))
            g.add_subnode(t.name, label=str(lab))
            res_tasks.append(t.name)
            if t.mutex is not None:
                g.add_node(t.mutex.name, color='#aaccaa', shape='hexagon')
            for nt in t.next_tasks:
                if isinstance(nt, model.Junction):
                    g.add_node(get_junction_name(nt), label=nt.mode, shape='diamond')


        g.add_subgraph(res_tasks, str("cluster_" + r.name))

    # now come the connections

    for r in s.resources:
        for t in r.tasks:
            for nt in t.next_tasks:
                if isinstance(nt, model.Junction):
                    g.add_edge(t.name, get_junction_name(nt), len=elen)  # edge to junction
                    for jnt in nt.next_tasks:  # edges from junction
                        g.add_edge(get_junction_name(nt), jnt.name, len=elen, constraint='True')
                else:
                    g.add_edge(t.name, nt.name, len=elen, constraint='True')

            if t.mutex is not None:
                g.add_edge(t.name, t.mutex.name, color='#aaccaa', len=1)

            if t.prev_task is None:
                g.add_node(str(t.in_event_model), len=10 * elen,
                           style='dashed')
                g.add_edge(str(t.in_event_model), t.name, constraint='True',
                           style='dashed')


    if filename is not None:
        g.draw(filename, prog=layout)

    if show:
        try:
            g.draw(prog='dot', format='xlib')
        except IOError:
            pass

    if dotout is not None:
        g.write(dotout)

    return g

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
