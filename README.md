#Welcome

pyCPA is a pragmatic Python implementation of Compositional Performance Analysis (aka the SymTA/S approach provided by [Symtavision](http://www.symtavision.com)) used for research in worst-case timing analysis. Unlike the commercial SymTA/S tool, pyCPA is not intended for commercial-grade use and does not guarantee correctness of the implementation.


##What does pyCPA do?

Given, you have a (distributed) real-time system and you want to know about worst-case (end-to-end) timing behavior, then you can use pyCPA to obtain these bounds.

You provide your architecture in the form of resources such as busses and CPUs and the corresponding scheduling policies. In a second step, you define your task-graph which is a specification of task-communication (precedence relations) and tasks' properties (best/worst-case execution times, activation patterns).

pyCPA will then calculate the following metrics:

   * worst-case response times (wcrt) of tasks
   * end-to-end timing of task chains
   * backlog of task activations (maximum buffer sizes)
   * output event models of dependent tasks


###Features:

   * schedulers: static priority (non-)preemtive, round-robin, TDMA, FIFO
   * task activation: periodic with jitter and minimum distance or generic events
   * system analysis: event model propagation
   * end to end analysis
   * gantt-charts (spnp, spp only)
   * graph of system topology
   * [SMFF](http://smff.sourceforge.net/) support (through xml interface)


##Why pyCPA?

Why not?
pyCPA is ideal for students who want to learn about real-time performance analysis research as well as researchers who want to extend existing algorithms.
pyCPA is -as the name suggests- written in Python and extremely easy to use and extend. If you want, you can easily plugin new schedulers or your own analyses.

pyCPA __should not__ be used in any commercial-grade, safety-critical designs. It does not provide analysis methods for commercial scheduling protocols like OSEK. Contact [Symtavision GmbH](http://www.symtavision.com) if you need any commercial support for such applications.


##What pyCPA is not

  * pyCPA cannot and will not obtain the worst-case execution time (WCET) of a task
  * there is and will be no support for any specific protocols (e.g. OSEK, Ethernet, CAN, ARINC, AUTOSAR, etc.). Contact [Symtavision GmbH](http://www.symtavision.com) if you need commercial support for any protocols.


##Installation

__Requirements__: matplotlib, argparse, pygraphviz

under debian-ish linuxes you can install these requirements via:

    sudo apt-get install python-matplotlib  python-argparse python-pygraphviz

Download the [latest version](https://bitbucket.org/pycpa/pycpa) of the package, extract and install through setup.py.

Run the examples and follow the documentation below.

##Documentation
The [documentation](http://readthedocs.org/docs/pycpa/en/latest/) is hosted on readthedocs.org.

##Other
You may also want to look at [SMFF](http://smff.sourceforge.net/).
