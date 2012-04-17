Command line switches
=====================

These are the default cmd switches, available in each pyCPA application.
The example pyCPA applications and you own application will potentially add some more options.

.. cmdoption:: --max_iterations <int>

   Maximum number of iterations in a local analysis
   
.. cmdoption:: --max_window <int>

   Maximum busy window length in a local analysis
   
.. cmdoption:: --backlog 

   Compute the worst-case backlog.
   
.. cmdoption:: --e2e_improved

   enable improved end to end analysis (experimental)
   
.. cmdoption:: --nocaching

   disable event-model caching.

.. cmdoption:: --show

   Show plots (interactive).  
   
.. cmdoption:: --propagation <method>

   Event model propagation method (jitter, jitter_dmin, jitter_offset, busy_window).
   default is busy_window
   
.. cmdoption:: --verbose

   be more talkative.   
  