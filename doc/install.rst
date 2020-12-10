Installation
============

Before you can install pyCPA, you must set up Python (`Prerequisites`_).
If you already have a Python installation, you may directly proceed with `Quickstart`_.
Alternatively, if you want to modify the pyCPA code, please consult `For Developers`_.

A brief introduction in how to test your installation is provided in `Using pyCPA`_.


.. _Prerequisites:

Prerequisites
-------------

First of all, you need a basic Python (2.7 or 3.x) environment.
As a Linux user, you most probably have Python already installed.
On Windows, we recommend to use `Python(x,y) <https://python-xy.github.io/>`_, which includes a comprehensive set of scientific Python libraries and tools as well as related documentation.
Python(x,y) comes with several interactive consoles (based on IPython), editors and applications.
For your first hands-on experience, we recommend using ``Spyder`` as an IDE.
You can also run a command prompt via the Python(x,y) icon on the Desktop and choosing ``IPython (sh)`` as an interactive console.


.. _Quickstart:

Quickstart
----------

The easiest way to install pyCPA is by using `pip <https://pypi.org/project/pip/>`_.
For a system-wide installation of the current pyCPA version, you simply run the following command:

.. code-block:: bash

   $ pip install https://github.com/IDA-TUBS/pycpa/archive/master.zip

Alternatively, e.g. if you do not have admin privileges, you can install pyCPA for the current user:

.. code-block:: bash

   $ pip install --user https://github.com/IDA-TUBS/pycpa/archive/master.zip


.. _For Developers:

For Developers
--------------

pyCPA has the following dependencies:

* Required Python packages: setuptools, argparse, pygraphviz, matplotlib
* Optional Python packages: numpy, simpy, xlrd

Before proceeding, you might want to check the status of your Python installation, i.e. what version is installed (if
at all) and what Python packages are already available, using the following commands:

.. code-block:: bash
   
   $ python --version
   $ pydoc modules

For downloading the pyCPA source code, you simply create a clone from the git `git <https://git-scm.com/>`_ repository, e.g. by running the following command:

.. code-block:: bash

   $ git clone https://github.com/IDA-TUBS/pycpa/


From within the pyCPA repository, execute the following command to install pyCPA in editable mode (i.e. changes to the
source code do not require re-installation to be effective):

.. code-block:: bash

   $ pip install --user -e .



.. _Using pyCPA:

Testing and using pyCPA
-----------------------

Congratulations, you have installed pyCPA!

In order to test pyCPA, you may want to run the examples which are provided with the distribution.
The quickest way to do this is to run the following on the command prompt (e.g. ``IPython (sh)`` on Windows):

   .. code-block:: bash
   
     $ python /path/to/pycpa/examples/spp_test.py

If you want to know what this examples does and how it works checkout the :doc:`spp_example`.

Depending on your personal preferences, you may also use an IDE of which we give a more detailed account in the
following sections.


Using an IDE: Spyder (Windows)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Spyder is installed with Python(x,y).
Simply open one of the example files (e.g. spp_test.py) and click the ``Run`` button.

Using an IDE: PyDev
^^^^^^^^^^^^^^^^^^^

You may also use Eclipse with PyDev as IDE, which can be installed by the following steps:

1. Make sure that you have installed Python *BEFORE* you install Eclipse.
2. Download from `<http://www.eclipse.org/downloads/eclipse-packages/>`_ the current Eclipse release for Windows 32 bit (!). Extract the zip-file, execute ``eclipse.exe`` and follow the installation instructions.
3. Open Eclipse and specify a workspace. If you open a workspace for the first time, you will have to close the Welcome tab, before proceeding to your workspace.
4. Select the menu item ``Help –> Install New Software``, search for the site `<http://pydev.org/updates>`_. Select and install the item “PyDev” which will be displayed in the list of available software. 

Now, you can set up a pyCPA project as follows:

1. Open the PyDev-Perspective by selecting in the main menu ``Window -> Open Perspective -> Other -> PyDev``
2. Select in the main menu ``File -> New -> PyDev Project``.
3. In the PyDev-Project Window specify a project name; the project will be saved to your workspace unless specified otherwise.
4. Choose the project type “Python” and select the 2.7 interpreter version.
5. Click on “Please configure an interpreter before proceeding”. 

   i. Select ``Manual Config`` in the pop-up window. 
   ii. In the settings for the Python interpreter click ``New…`` and specify an interpreter name, e.g. Python27, and the path to the interpreter executable (e.g. ``C:\myPathToPython\python.exe``). In the appearing pop-up window select all options. 
   iii. In the tab ``Libraries``, select ``New Folder`` and specify the path to the pyCPA-folder (e.g. ``C:\MyPathTo\pycpa``).
   iv. Close the preferences window by clicking ok.

6. Back in the PyDev-Project Window, click ``add project directory to PYTHONPATH`` and then the button ``Finish``.
7. You may now add a Python file to your project (right-click on your project in the PyDev Package Explorer -> New… -> File) and write a Python program (e.g. test.py) which uses pyCPA. 
8. To run test.py, right-click on ``test.py`` and select ``Run as -> Python Run``. If you want to modify your run settings in order to e.g. specify arguments, select ``Run as -> Run Configurations`` and adapt the settings as needed before clicking ``Run`` in the Run Configurations Window. 
9. You may also try out the examples which are provided with pyCPA such as the :doc:`spp_example`.
