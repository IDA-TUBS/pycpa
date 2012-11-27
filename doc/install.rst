Installation
============

Before you can install pyCPA, you must set up Python first (>=2.6, <3.0).

Linux
-----
Install Python and the required prerequisites.
If you use Ubuntu/Debian this can be done using the following commands:

.. code-block:: bash

   $ sudo apt-get install python-matplotlib python-pygraphviz python-simpy python-setuptools
   
Other linux distributions provide similar functionality, RTFM.

Windows
-------
We recommend to use `Python(x,y) <http://code.google.com/p/pythonxy/>`_ a prepackaged Python release
targeted towards scientific and engineering development software.
Most of the required Python modules such as matplotlib are already included,
but some (SimPy and pygraphviz) have to be installed by hand if required.

Please consider the Python(x,y) manual on how to do so. In case packages are
not available (pygraphviz has to be compiled by hand) you still can use pyCPA.
E.g. if  pygraphviz is not installed, the analysis works but you can't graph your system.

Setting up pyCPA
----------------
Download and extract the latest pyCPA release from `google code <http://code.google.com/p/pycpa/>`_.
Alternatively and currently recommended, you can also clone the mercurial repository.
Given, that you have a mercurial installation you can clone the repository as follows:

.. code-block:: bash

   $ hg clone https://code.google.com/p/pycpa/ 
 
Now, there are three different ways to install pyCPA,
depending on how you want to use pyCPA.
Note, that you only have to do ONE of these steps!
     
1. Install/copy pyCPA into your Python installation.
   This is for people who just want to use pyCPA as it comes.

   .. code-block:: bash
   
     $ python setup.py install

2. Leave pyCPA where it is and tell Python to use the module in-place.
   Add the pycpa/src directory to your PYTHONPATH:

   .. code-block:: bash
   
     $ export PYTHONPATH="/path/to/pycpa"

3. Also you can import pyCPA as an eclipse project, given you use `PyDev <http://pydev.org/>`_.
   Start eclipse and import pyCPA as a new PyDev project.
   In the project settings under PYTHONPATH settings, add pycpa/examples and pycpa/src to your project source folders.
   Also you might want to install `MercurialEclipse <http://javaforge.com/project/HGE>`_ 


If you uncertain how to proceed, we recommend using Eclipse since it provides a nice GUI and
you always have the pyCPA sources at hand, in case you want know more.

     
Congratulations, you have installed pyCPA!
To test pyCPA you may want to run the examples which are provided with the distribution. 

   .. code-block:: bash
   
     $ python /path/to/pycpa/examples/spp-test.py

Or, if you decided to use Eclipse just run spp-test.py as a Python application from Eclipse.
If you want to know what this examples does and how it works checkout the :doc:`spp_example`.
