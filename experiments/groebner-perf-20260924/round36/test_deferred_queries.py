"""Complete public-point queries, independent roots and wider CPU comparisons."""
from contextlib import ExitStack
import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

from deferred import HERE
from deferred_query import DeferredQuery
import sys
sys.path.insert(0,str(HERE.parent/'round35'))
from symmetry_query import SymmetryQuery
from multiplier_query import MultiplierQuery
from expanded_query import ExpandedQuery
sys.path.insert(0,str(HERE.parent/'round33'))
from narrow_query import NarrowQuery
from native_descent import PackedANF
from wide_descent import PackedANF as WidePacked
from descend import make_instance
from sparse_checker import Curve,GF2n,Point
from quadratic_reference import verify_basis
from affine_reference import certify_roots

_spec=importlib.util.spec_from_file_location('multiplier_full_truth',HERE.parent/'round32/reference.py')
_truth=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_truth)


class QueryTests(unittest.TestCase):
    def test_frozen_queries_and_twenty_seven_variable_frontier(self):
        small=[(31,6,s) for s in range(101,107)]+[(31,5,101),(11,3,101),(83,2,101)]
        wide=[(31,ell,seed) for ell in (7,8,9) for seed in (201,202,203)]
        for n,ell,seed in small+wide:
            f=make_instance(n,3,ell,seed=seed)
            curve=Curve(GF2n(n,f.mod),f.b)
            target=curve.sum(f.points)
            items=tuple(sorted(f.anf.items()))
            expected=_truth.chunked_roots(3*ell,n,items) if ell<=8 else None
            baseline=SymmetryQuery
            backends=['cpu']
            if os.environ.get('QUADRATIC_TEST_METAL')=='1' and (ell<=6 or (ell<=8 and seed==201)):
                backends.append('metal')
            for backend in backends:
                with baseline(n,f.mod,f.b,3,ell,backend=backend) as old, \
                     DeferredQuery(n,f.mod,f.b,3,ell,backend=backend) as new:
                    with patch.object(PackedANF,'items',side_effect=AssertionError('expanded ANF')), \
                         patch.object(PackedANF,'to_dict',side_effect=AssertionError('copied ANF')), \
                         patch.object(WidePacked,'items',side_effect=AssertionError('expanded wide ANF')), \
                         patch.object(WidePacked,'to_dict',side_effect=AssertionError('copied wide ANF')):
                        a,b=old.solve(target),new.solve(target)
                    self.assertTrue(a['verified'],a)
                    self.assertTrue(b['verified'],b)
                    for key in ('basis_terms','basis_sha256','assignment','curve_witness'):
                        self.assertEqual(a[key],b[key],(n,ell,seed,backend,key))
                    self.assertEqual(a['proof_bytes'],b['proof_bytes'])
                    roots,_,extended,assignments=certify_roots(2*ell,ell,n,items,b['proof_bytes'],sys.byteorder)
                    self.assertEqual(list(roots),b['basis_certificate']['solutions'])
                    if expected is not None:self.assertEqual(list(roots),expected)
                    self.assertTrue(verify_basis(3*ell,items,list(roots),b['basis_terms'],len(roots)))
                    self.assertEqual(assignments,b['basis_certificate']['stats']['assignments'])
                    self.assertEqual(len(extended),b['multiplier_stats']['certified_branches']+b['symmetry_stats']['affine_copies'])
                    self.assertEqual(b['symmetry_stats']['enabled'],1)
                    self.assertEqual(b['symmetry_stats']['representatives'],(1<<ell)*((1<<ell)+1)//2)
                    self.assertEqual(b['complete_query_ns'],sum(b['phases_ns'].values()))
                    points=[Point(**p) for p in b['curve_witness']['points']]
                    self.assertTrue(all(curve.on_curve(p) for p in points))
                    self.assertEqual(curve.sum(points),target)
                    self.assertEqual(f.evaluate(b['assignment']),0)


if __name__=='__main__':unittest.main()
