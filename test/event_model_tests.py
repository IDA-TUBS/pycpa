"""
| Copyright (C) 2012 Jonas Diemer, Philip Axer
| TU Braunschweig, Germany
| All rights reserved.
| See LICENSE file for copyright and license details.

:Authors:
         - Jonas Diemer
         - Philip Axer

Description
-----------

Regression tests
"""

import unittest
from pycpa import model

class Test(unittest.TestCase):

    def test_eta_to_delta_min(self):
        # create some standard event model
        em_a = model.PJdEventModel(P=10, J=99)
        em_b = model.EventModel()
        em_b.deltamin_func = model.EventModel.delta_min_from_eta_plus(em_a.eta_plus)
        em_b.deltaplus_func = model.EventModel.delta_plus_from_eta_min(em_a.eta_min)
        seq = range(0, 100, 1)
        self.assertEqual([em_b.delta_min(n) for n in seq], [em_a.delta_min(n) for n in seq])
        self.assertEqual([em_b.delta_plus(n) for n in seq], [em_a.delta_plus(n) for n in seq])

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
