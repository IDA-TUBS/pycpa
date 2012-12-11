"""
| Copyright (C) 2010 Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer

Description
-----------

Plot an event model.
"""

import matplotlib
matplotlib.use('Agg')

from pycpa import model
from pycpa import plot

# only type 1 fonts
matplotlib.rcParams['ps.useafm'] = True
matplotlib.rcParams['pdf.use14corefonts'] = True
matplotlib.rcParams['text.usetex'] = True

P = 30
J = 60#5
d = 0#1
em = model.EventModel(P=P, J=J, dmin=d)


print "delta_min(0) =", em.delta_min(0)
print "eta_plus(0) =", em.eta_plus(0)
print "eta_plus(eps) =", em.eta_plus(1e-12)

plot.plot_event_model(em, 7, separate_plots=False, file_format='pdf', file_prefix='event-model-', ticks_at_steps=True)
