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

    def test_delta_min_PJd(self):
        delta_reference = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 11, 21, 31, 41, 51, 61, 71, 81, 91, 101, 111, 121, 131, 141, 151, 161, 171, 181, 191, 201, 211, 221, 231, 241, 251, 261, 271, 281, 291, 301, 311, 321, 331, 341, 351, 361, 371, 381, 391, 401, 411, 421, 431, 441, 451, 461, 471, 481, 491, 501, 511, 521, 531, 541, 551, 561, 571, 581, 591, 601, 611, 621, 631, 641, 651, 661, 671, 681, 691, 701, 711, 721, 731, 741, 751, 761, 771, 781, 791, 801, 811, 821, 831, 841, 851, 861, 871, 881]
        em = model.PJdEventModel(P=10,J=99)
        self.assertEqual(delta_reference, [em.delta_min(n) for n in range(0,100,1)])


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
