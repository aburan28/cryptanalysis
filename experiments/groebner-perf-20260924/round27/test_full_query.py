from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from full_query import BaselineQuery, ConditionalQuery
from sparse_checker import Curve, GF2n, Point, PackedANF
from descend import make_instance


class FullQueryTests(unittest.TestCase):
    def test_frozen_curve_queries_and_packed_views(self):
        for sanitizer in (False,True):
            for n,ell,seeds in ((31,10,range(201,204)),(63,10,range(201,204)),
                                 (11,3,range(3)),(83,2,range(2))):
                fixture=make_instance(n,2,ell,seed=seeds[0])
                shape=(n,fixture.mod,fixture.b,2,ell)
                oracle=Curve(GF2n(n,fixture.mod),fixture.b)
                with BaselineQuery(*shape,arm='sparse',sanitizer=sanitizer) as baseline, \
                     ConditionalQuery(*shape,sanitizer=sanitizer) as candidate:
                    for seed in seeds:
                        f=make_instance(n,2,ell,seed=seed)
                        target=oracle.sum(f.points)
                        with patch.object(PackedANF,'items',side_effect=AssertionError('ANF expanded')), \
                             patch.object(PackedANF,'to_dict',side_effect=AssertionError('ANF materialized')):
                            left,right=baseline.solve(target),candidate.solve(target)
                        for key in ('status','basis_terms','basis_sha256','assignment',
                                    'assignments_checked','curve_witness'):
                            self.assertEqual(left[key],right[key],(n,ell,seed,key))
                        self.assertTrue(right['verified'])
                        self.assertEqual(right['complete_query_ns'],sum(right['phases_ns'].values()))
                        roots=right['basis_certificate']['solutions']
                        self.assertEqual(left['basis_certificate']['solutions'],roots)
                        self.assertTrue(all(f.evaluate(r)==0 for r in roots))
                        points=[Point(**p) for p in right['curve_witness']['points']]
                        self.assertTrue(all(oracle.on_curve(p) for p in points))
                        self.assertEqual(oracle.sum(points),target)

    def test_unsupported_and_closed_query(self):
        f=make_instance(11,2,2,seed=5)
        with self.assertRaises(ValueError):
            ConditionalQuery(11,f.mod,f.b,3,2)
        with ConditionalQuery(11,f.mod,f.b,2,2) as query:
            with self.assertRaises(ValueError):
                query.solve(Point(0,0,True))
            query.close()
            with self.assertRaises(RuntimeError):
                query.solve(f.points[0])


if __name__=='__main__':
    unittest.main()
