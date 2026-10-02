"""Integrated coefficient replay, exact fallback, lifecycle and real queries."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import gzip
import json
from pathlib import Path
import random
import unittest

from adapter import TransformQuery, producer
from independent_checker import Checker, TRANSFORM_MODES
from public_replay import Point
from transform_accounting import reconcile_transform

HERE = Path(__file__).resolve().parent


def symmetric_terms(x, y, equations):
    rng = random.Random(202610014700 + x*1000 + y*100 + equations)
    half, fixed_mask = x//2, (1 << x)-1
    residual = [v for v in range(1 << y) if v.bit_count() <= 2]
    terms = [(0, 1)] # An independently valid constant certificate on every branch.
    for _ in range(80):
        fixed = rng.randrange(1 << x)
        exchanged = ((fixed & ((1 << half)-1)) << half) | (fixed >> half)
        tail = rng.choice(residual) << x
        coefficient = rng.getrandbits(equations) & ~1
        for m in {fixed, exchanged}:
            assert m <= fixed_mask
            terms.append((tail | m, coefficient))
    return terms


def constant_proof(x, equations):
    limbs = (equations+63)//64
    proof = (producer.U64*((1 << x)*limbs))()
    for branch in range(1 << x):
        proof[branch*limbs] = 1
    return proof


class TransformTests(unittest.TestCase):
    def test_every_coefficient_in_actual_checker_large_tables(self):
        # The explicit audit build repeats the accepted full transform from
        # the scattered original coefficients and compares EVERY table word.
        for x,y,e in ((10,3,31),(12,3,65),(14,4,128),(18,9,31),(20,1,128)):
            terms = symmetric_terms(x,y,e)
            proof = constant_proof(x,e)
            with Checker(x,y,e,transform_audit_test=True) as checker:
                for changed,symmetric in ((terms,True),(terms+[(1,2)],False),(terms,True)):
                    anf = producer.Packed(x+y,e,changed)
                    for mode in TRANSFORM_MODES:
                        with self.subTest(shape=(x,y,e),mode=mode,symmetric=symmetric):
                            checker.configure_transform(mode)
                            check = checker.certify(anf,[],[[0]],proof)
                            self.assertTrue(check['verified'],check)
                            self.assertEqual(check['symmetry_check_stats']['enabled'],int(symmetric))
                            reconcile_transform(check,x,y,e,audit=True)

    def test_axes_and_tiled_fallbacks_are_independent(self):
        for x in (3,10):
            terms = [(0,1),(1,2),(1 << x,4)]
            anf = producer.Packed(x+2,3,terms)
            proof = constant_proof(x,3)
            for flag in ({},{'symmetry_budget_test':True},{'symmetry_workspace_test':True},
                         {'symmetry_late_budget_test':True},{'sanitizer':True}):
                with Checker(x,2,3,**flag) as checker:
                    for symmetry in (False,True):
                        checker.configure_symmetry(symmetry)
                        for mode in TRANSFORM_MODES:
                            checker.configure_transform(mode)
                            check = checker.certify(anf,[],[[0]],proof)
                            self.assertTrue(check['verified'])
                            reconcile_transform(check,x,2,3,audit=False)
                            expected = 1 if mode=='axes' and x%2==0 else 0
                            self.assertEqual(check['transform_check_stats']['selected_mode'],expected)

    def test_configuration_rejection_concurrency_and_stale_stats(self):
        terms = symmetric_terms(10,2,3)
        anf, proof = producer.Packed(12,3,terms),constant_proof(10,3)
        with Checker(10,2,3) as checker:
            for bad in (None,True,0,[],{},'automatic','TILE16'):
                with self.assertRaises(ValueError):checker.configure_transform(bad)
                with self.assertRaises(ValueError):Checker(10,2,3,transform=bad)
            self.assertEqual(checker.lib.check_transform_configure(checker._handle,6),-1)
            for mode in TRANSFORM_MODES:
                checker.configure_transform(mode)
                expected = checker.certify(anf,[],[[0]],proof)
                def call(_):return checker.certify(anf,[],[[0]],proof)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(call,range(12)))
                for result in results:
                    self.assertTrue(result['verified'])
                    reconcile_transform(result,10,2,3)
                    self.assertEqual({k:v for k,v in result['transform_check_stats'].items() if type(v) is int},
                                     {k:v for k,v in expected['transform_check_stats'].items() if type(v) is int})
                damaged = bytes(proof)[:-8]
                with self.assertRaises(ValueError):checker.certify(anf,[],[[0]],damaged)
                self.assertTrue(checker.certify(anf,[],[[0]],proof)['verified'])
        with self.assertRaises(RuntimeError):checker.configure_transform('full')
        with self.assertRaises(RuntimeError):checker.certify(anf,[],[[0]],proof)
        with self.assertRaises(ValueError):Checker(20,10,31,transform='tile16')

    def test_actual_query_coefficients_replayed_independently(self):
        fixtures = json.loads(gzip.decompress((HERE.parent/'round40/fixtures/inputs.json.gz').read_bytes()))
        selected = [next(i for i in fixtures if i['nvars']==n and i['n']==31) for n in (18,21,24,27)]
        selected.append(next(i for i in fixtures if i['n']==83))
        for item in selected:
            shape = tuple(item[k] for k in ('n','mod','b','m','ell'))
            with TransformQuery(*shape,transform_audit_test=True) as query:
                baseline = None
                for mode in TRANSFORM_MODES:
                    query.checker.configure_transform(mode)
                    answer = query.solve(Point(**item['target']))
                    self.assertEqual(answer['status'],'solved')
                    self.assertTrue(answer['verified'])
                    reconcile_transform(answer['basis_certificate'],2*item['ell'],item['ell'],item['n'],audit=True)
                    math = (answer['proof_bytes'],answer['basis_terms'],answer['assignment'],answer['basis_certificate']['solutions'])
                    if baseline is None:baseline=math
                    self.assertEqual(math,baseline)


if __name__=='__main__':
    unittest.main(verbosity=2)
