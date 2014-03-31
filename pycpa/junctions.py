"""
| Copyright (C) 2012 Philip Axer, Jonas Diemer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Johannes Schlatow

Description
-----------

Local model propagation functions (junctions)
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import itertools
import math
import logging

from . import analysis
from . import model
from . import options

logger = logging.getLogger("pycpa")

class ORJoin(analysis.JunctionStrategy):
    def __init__(self):
        self.name = "or"

    def calculate_out_event_model(self, junction):
        assert len(junction.in_event_models) > 0
        if len(junctions.in_event_models) > 1:
            return OREventModel(junction.in_event_models.values())
        else:
            for em in junction.in_event_models:
                return em
            

class ANDJoin(analysis.JunctionStrategy):
    """ Compute output event models for an AND junction.
    This corresponds to Lemma 4.2 in [Jersak2005]_.
    """

    def __init__(self):
        self.name = "and"

    def calculate_out_event_model(self, junction):
        assert len(junction.in_event_models) > 0
        em = model.EventModel()
        em.deltamin_func = lambda n: (
            min(emif.delta_min(n) for emif in junction.in_event_models.values()))
        em.deltaplus_func = lambda n: (
            max(emif.delta_plus(n) for emif in junction.in_event_models.values()))
        em.__description__ = "AND " + \
                "".join([emif.__description__
                         for emif in junction.in_event_models.values()])
        return em


class OREventModel(model.EventModel):
    """ Compute output event model for an OR junction.
    This corresponds to Section 4.2, Equations 4.11 and 4.12 in [Jersak2005]_.
    """
    def __init__(self, in_event_models):
        # set proper name
        name = "OR " + \
                "".join([emif.__description__
                         for emif in in_event_models])

        model.EventModel.__init__(self,name)
        self.in_event_models = in_event_models

        self.deltamin_func = model.EventModel.delta_min_from_eta_plus(self.eta_plus)
        self.deltaplus_func = model.EventModel.delta_plus_from_eta_min(self.eta_min)

    def eta_min(self, w):
        return sum([emif.eta_min(w) for emif in self.in_event_models])

    def eta_plus(self, w):
        return sum([emif.eta_plus(w) for emif in self.in_event_models])

    def eta_min_closed(self, w):
        return sum([emif.eta_min_closed(w) for emif in self.in_event_models])

    def eta_plus_closed(self, w):
        return sum([emif.eta_plus_closed(w) for emif in self.in_event_models])


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4