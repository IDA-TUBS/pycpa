#!/usr/bin/env python

"""
| Copyright (C) 2012 Philip Axer
| TU Braunschweig, Germany
| All rights reserved

:Authors:
         - Philip Axer

Description
-----------

Setup
"""


from setuptools import setup

setup(name='pycpa',
      version='1.0',
      description='pyCPA - a python implementation of compositional performance analysis',
      author='Jonas Diemer, Philip Axer',
      author_email='{axer, diemer}@ida.ing.tu-bs,de',
      url='http://code.google.com/p/pycpa',
      license="MIT",
      packages=['pycpa'],
      install_requires=[ 'argparse'],
      extras_require={'plot': 'matplotlib',
                      'trace': 'numpy',
                      'topology_plot' : 'pygraphviz',
                      'gantt_charts' : 'simpy',
                      'xls' : 'xlrd',
                      'doc' : 'sphinx'}
     )
