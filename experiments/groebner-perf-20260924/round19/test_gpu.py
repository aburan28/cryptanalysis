"""Fresh shared-buffer GPU certificates, ABI failures and complete public queries."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
from itertools import product
import random
import sys
import unittest
from unittest.mock import patch

from gpu_query import (ARMS, GPUChecker, GPUQuery, GPUStats, PackedChecker, PackedANF,
                       Result, U32, U64, Curve, GF2n, Point, ordered_query)
from boolean_certificate_native import _pack
from descend import make_instance


def packed(n,e,pairs):
    limbs = (e+63)//64
    masks = (U32*len(pairs))(*(m for m,_ in pairs))
    values = (U64*(len(pairs)*limbs))(*(c>>(64*j)&((1<<64)-1) for _,c in pairs for j in range(limbs)))
    return PackedANF(n,e,masks,values,len(pairs))


def semantics(answer):
    return {k:v for k,v in answer.items() if k not in ('backend','evaluation_counts','scratch_bytes','gpu_timing')}


def scalar(pairs,point):
    result = 0
    for m,c in pairs:
        if m & ~point == 0: result ^= c
    return result


@unittest.skipUnless(sys.platform=='darwin','Metal requires macOS')
class GPUTests(unittest.TestCase):
    def test_random_roots_duplicates_and_direct_equations(self):
        rng = random.Random(2026092707)
        compared = direct = 0
        for n,e in ((1,1),(3,31),(6,63),(6,64),(7,65),(8,128)):
            for case in range(4):
                pairs = [(rng.randrange(1<<n),rng.getrandbits(e)) for _ in range(5+5*case)]
                pairs += pairs[:2]+pairs[:1]
                if case%2==0:
                    point = rng.randrange(1<<n)
                    pairs.append((0,scalar(pairs,point)))
                anf = {}
                for mask,value in pairs: anf[mask] = anf.get(mask,0)^value
                with ordered_query(n,e,'ordered') as reference:
                    expected = reference.compute(anf)
                self.assertTrue(expected.get('groebner_verified'),expected)
                roots = [p for p in range(1<<n) if not scalar(pairs,p)]
                self.assertEqual(expected['basis_certificate']['solutions'],roots)
                for sanitized,poll in product((False,True),(0,5000)):
                    with GPUChecker(n,e,poll_us=poll,sanitizer=sanitized) as checker:
                        value = packed(n,e,list(reversed(pairs)))
                        actual = checker.certify(value,expected['basis_terms'])
                        self.assertEqual(semantics(actual),semantics(expected['basis_certificate']))
                        self.assertEqual(actual['gpu_timing']['dispatches'],2)
                        self.assertEqual(actual['gpu_timing']['calls'],1)
                        self.assertEqual(actual['scratch_bytes'],actual['gpu_timing']['shared_buffer_bytes']+e)
                        for point in range(1<<n):
                            self.assertEqual(checker.evaluate(value,point),scalar(pairs,point))
                            direct += 1
                        compared += 1
        print('GPU/direct-reference certificate comparisons:',compared,'direct equation evaluations:',direct)

    def test_zero_many_roots_and_large_tiles(self):
        for n,e in ((1,1),(6,65),(18,31),(20,128)):
            with PackedChecker(n,e) as cpu:
                zero = packed(n,e,[])
                expected = cpu.certify(zero,[])
                for sanitized,poll,threads in ((False,0,256),(True,5000,64)):
                    with GPUChecker(n,e,sanitizer=sanitized,poll_us=poll,threads=threads) as checker:
                        actual = checker.certify(zero,[])
                        self.assertEqual(semantics(actual),semantics(expected))
                        self.assertEqual(actual['root_count'],1<<n)
                        self.assertEqual(actual['gpu_timing']['threads'],threads)
                        self.assertTrue(checker.certify(packed(n,e,[(0,1<<(e-1))]),[[0]])['verified'])
                        self.assertEqual(semantics(checker.certify(zero,[])),semantics(expected))

    def test_invalid_abi_basis_and_no_dispatch(self):
        for sanitizer in (False,True):
            with GPUChecker(2,2,sanitizer=sanitizer) as checker:
                anf = packed(2,2,[(1,1)])
                terms,offsets = _pack([[1]],2)
                args = [checker._handle,anf.masks,anf.coefficients,1,terms,len(terms),offsets,1]
                for change in ({1:None},{2:None},{1:(U32*1)(4)},{2:(U64*1)(4)},
                               {4:None},{6:None},{6:(U32*2)(1,1)},
                               {6:(U32*2)(0,0)},{4:(U32*1)(4)}):
                    values = args[:]
                    for index,value in change.items(): values[index] = value
                    out,stats = Result(),GPUStats()
                    self.assertEqual(checker.lib.truth_certify(*values,ct.byref(out)),6)
                    self.assertEqual(out.certificate.solution_count,0)
                    self.assertEqual(checker.lib.truth_gpu_stats(checker._handle,ct.byref(stats)),0)
                    self.assertEqual(stats.calls,0)
                self.assertEqual(checker.lib.truth_certify(None,*args[1:],ct.byref(Result())),6)
                self.assertEqual(checker.lib.truth_certify(*args,None),6)
                for basis,code in (([[]],1),([[1,1]],1),([[1,0]],2),([],3),([[1],[1]],4)):
                    bad_terms,bad_offsets = _pack(basis,2)
                    out = Result()
                    self.assertEqual(checker.lib.truth_certify(checker._handle,anf.masks,anf.coefficients,1,
                        bad_terms,len(bad_terms),bad_offsets,len(basis),ct.byref(out)),code)
                answer = checker.certify(packed(2,2,[(1,1),(2,2)]),[[1,2],[2]])
                self.assertEqual(answer['reason'],'nonstandard tail monomial')
                for n,e in ((0,1),(21,1),(1,0),(1,129)):
                    self.assertFalse(checker.lib.truth_create(n,e))
                for poll,threads in ((5001,256),(0,0),(0,65536)):
                    self.assertEqual(checker.lib.truth_gpu_configure(checker._handle,poll,threads),6)
                self.assertEqual(checker.lib.truth_gpu_device(None),b'')
                stats = GPUStats(); stats.calls = 99
                self.assertEqual(checker.lib.truth_gpu_stats(None,ct.byref(stats)),6)
                self.assertEqual(stats.calls,0)
                self.assertEqual(checker.lib.truth_gpu_stats(checker._handle,None),6)
                self.assertTrue(checker.certify(anf,[[1]])['verified'])
        for kwargs in ({'poll_us':True},{'poll_us':5001},{'threads':0},{'threads':1025}):
            with self.assertRaises(ValueError): GPUChecker(2,2,**kwargs)

    def test_concurrent_reuse_and_closed_lifetime(self):
        for poll in (0,5000):
            checker = GPUChecker(3,65,poll_us=poll)
            left = packed(3,65,[(1,1<<64)])
            right = packed(3,65,[(0,1<<64),(1,1<<64)])
            def call(anf): return checker.certify(anf,[[1]])
            with ThreadPoolExecutor(max_workers=4) as pool:
                answers = list(pool.map(call,[left,right]*12))
            self.assertEqual([a['verified'] for a in answers],[True,False]*12)
            self.assertTrue(all(a['gpu_timing']['calls']==1 and a['gpu_timing']['dispatches']==2 for a in answers))
            left.coefficients[1] = 0
            self.assertFalse(call(left)['verified'])
            left.coefficients[1] = 1
            self.assertTrue(call(left)['verified'])
            checker.close(); checker.close()
            with self.assertRaises(RuntimeError): checker.certify(left,[[1]])
            with self.assertRaises(RuntimeError): checker.evaluate(left,0)

    def test_complete_public_queries_and_larger_ring(self):
        compared = 0
        for n,m,ell,seed in ((11,3,2,101),(31,3,6,101),(83,3,2,101),(31,2,10,200),(63,2,10,200)):
            original = make_instance(n,m,ell,seed=seed)
            curve = Curve(GF2n(n,original.mod),original.b)
            target = curve.sum(original.points)
            shape = (n,original.mod,original.b,m,ell)
            before = sys.path[:]
            with GPUQuery(*shape,'cpu') as cpu:
                expected = cpu.solve(target)
            self.assertTrue(expected.get('verified'),expected)
            for arm,sanitizer in product(ARMS[1:],(False,True)):
                with GPUQuery(*shape,arm,sanitizer=sanitizer) as gpu:
                    self.assertEqual(sys.path,before)
                    with patch.object(PackedANF,'to_dict',side_effect=AssertionError('dictionary conversion forbidden')):
                        actual = gpu.solve(target)
                    self.assertTrue(actual.get('verified'),actual)
                    for key in ('basis_sha256','assignment','curve_witness'):
                        self.assertEqual(actual[key],expected[key])
                    self.assertEqual(semantics(actual['basis_certificate']),semantics(expected['basis_certificate']))
                    self.assertEqual(original.evaluate(actual['assignment']),0)
                    points = [Point(**p) for p in actual['curve_witness']['points']]
                    self.assertTrue(all(curve.on_curve(p) for p in points))
                    self.assertEqual(curve.sum(points),target)
                    self.assertEqual(actual['complete_query_ns'],sum(actual['phases_ns'].values()))
                    if n==31 and m==3:
                        changed = make_instance(n,m,ell,seed=102)
                        other = curve.sum(changed.points)
                        self.assertNotEqual(other.x,target.x)
                        fresh = gpu.solve(other)
                        self.assertTrue(fresh.get('verified'))
                        self.assertEqual(changed.evaluate(fresh['assignment']),0)
                        self.assertEqual(curve.sum([Point(**p) for p in fresh['curve_witness']['points']]),other)
                        self.assertTrue(gpu.solve(target)['verified'])
                    with self.assertRaises(ValueError): gpu.solve(Point(0,0))
                    compared += 1
                with self.assertRaises(RuntimeError): gpu.solve(target)
        print('Complete CPU/GPU query comparisons:',compared)


if __name__=='__main__': unittest.main()
