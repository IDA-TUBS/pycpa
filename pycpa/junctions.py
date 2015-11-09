"""
| Copyright (C) 2013-2014 Johannes Schlatow
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

class SampledInput(analysis.JunctionStrategy):
    def __init__(self):
        self.name = "sampled"

    def set_trigger_event_model(self, trigger_em):
        assert isinstance(trigger_em, model.EventModel)
        self.trigger = trigger_em

    def calculate_out_event_model(self, junction):
        # calculate sampling delay
        sampling_delay = self.trigger.deltaplus_func(2)

        # set sampling delay for every task that is connected to this junction (used in path analysis)
        for t in junction.in_event_models:
            if t is not self.trigger:
                junction.analysis_results[t] = analysis.TaskResult()
                junction.analysis_results[t].bcrt = 0
                junction.analysis_results[t].wcrt = sampling_delay

        # ignore the in_event_models for output event model as the sampling is purely time triggered
        return self.trigger

class ORJoin(analysis.JunctionStrategy):
    def __init__(self):
        self.name = "or"

    def calculate_out_event_model(self, junction):
        assert len(junction.in_event_models) > 0
        if len(junction.in_event_models) > 1:
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

        # calculate waiting delay for every task connected to this junction (see issue #6)
        # FIXME: this is rather conservative but could be improved if the input event models have a
        #        common source
        for t in junction.in_event_models:
            waiting_delay = max(emif.delta_plus(2) for emif in junction.in_event_models.values() if emif is not t)

            junction.analysis_results[t] = analysis.TaskResult()
            junction.analysis_results[t].bcrt = 0
            junction.analysis_results[t].wcrt = waiting_delay

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
