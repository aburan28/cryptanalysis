"""Differential whole certificates, adversarial ABI inputs and original replay."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
from dataclasses import replace
import random
import unittest

from ordered_query import ARMS, NativeDescent, library_path, packed_query, query
from boolean_certificate_native import Certificate, _pack
from boolean_basis import certify_boolean_basis
from descend import make_instance

U32, U64 = ct.c_uint32, ct.c_uint64


def buffers(pairs, equations):
    words = (equations+63)//64
    return ((U32*len(pairs))(*(m for m,_ in pairs)),
            (U64*(len(pairs)*words))(*(c>>(64*j)&((1<<64)-1) for _,c in pairs for j in range(words))))


def signature(result):
    return tuple(tuple(getattr(result,name)) if name=='solutions' else getattr(result,name)
                 for name,_ in Certificate._fields_)


class OrderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.libraries = []
        with query(1,1) as exemplar:
            args = exemplar._verifier.packed_boolean_certificate.argtypes
        for sanitizer in (False,True):
            for arm in ARMS:
                lib = ct.CDLL(str(library_path(arm,sanitizer)))
                lib.packed_boolean_certificate.argtypes = args
                lib.packed_boolean_certificate.restype = ct.c_int
                lib.boolean_certificate.argtypes = [U32,ct.POINTER(U32),U32,ct.POINTER(U32),U32,
                    ct.POINTER(U32),U32,ct.POINTER(U32),U32,ct.POINTER(Certificate)]
                lib.boolean_certificate.restype = ct.c_int
                cls.libraries.append((arm,sanitizer,lib))

    def check_raw(self,n,e,pairs,basis,changes=None,expected=None):
        masks,coefficients = buffers(pairs,e)
        terms,offsets = _pack(basis,n)
        args = [n,e,masks,coefficients,len(masks),terms,len(terms),offsets,len(basis)]
        for i,value in (changes or {}).items(): args[i] = value
        outputs = []
        for arm,sanitizer,lib in self.libraries:
            result = Certificate()
            code = lib.packed_boolean_certificate(*args,ct.byref(result))
            self.assertEqual(code,result.code,(arm,sanitizer))
            if expected is not None: self.assertEqual(code,expected,(arm,sanitizer))
            outputs.append(signature(result))
        self.assertTrue(all(r==outputs[0] for r in outputs))
        return outputs[0]

    def test_random_certificates_permutations_and_parity(self):
        rng = random.Random(2026092603)
        count = 0
        for e in (1,2,31,63,64,65,127,128,4096):
            for repeat in range(8):
                n = 1+repeat%8
                pairs = [(rng.randrange(1<<n),rng.getrandbits(e)) for _ in range(3+repeat*2)]
                # Explicit duplicates with cancelling and noncancelling coefficients.
                pairs += pairs[:3]+pairs[:2]
                if repeat%2==0:
                    planted = rng.randrange(1<<n)
                    value = 0
                    for m,c in pairs:
                        if m&~planted==0: value ^= c
                    pairs.append((0,value))
                anf = {}
                for m,c in pairs: anf[m] = anf.get(m,0)^c
                with packed_query(n,e) as producer:
                    result = producer.compute(anf)
                    self.assertTrue(result['groebner_verified'],result)
                    if repeat%2==0:
                        self.assertIn(planted,result['basis_certificate']['solutions'])
                basis = result['basis_terms']
                equations = [[m for m,c in anf.items() if c>>j&1] for j in range(e)]
                self.assertTrue(certify_boolean_basis(n,equations,basis)['verified'])
                for ordered in (pairs,sorted(pairs),list(reversed(sorted(pairs)))):
                    shuffled_basis = [r[:] for r in basis]
                    for r in shuffled_basis: rng.shuffle(r)
                    self.check_raw(n,e,ordered,shuffled_basis,expected=0)
                    count += 1
                damaged = [r[:] for r in basis]
                if damaged:
                    damaged[0] += damaged[0][:1]
                    self.check_raw(n,e,pairs,damaged,expected=1)
        print('random ordering/parity certificates:',count,'across',len(self.libraries),'builds')

    def test_empty_zero_wide_and_rejected_inputs(self):
        for n in (1,6,20):
            self.check_raw(n,1,[],[],expected=0)
            self.check_raw(n,1,[(0,0),(0,1),(0,1)],[],expected=0)
            pairs = [(1<<i,1<<i) for i in range(n)]
            basis = [[1<<i] for i in range(n)]
            self.check_raw(n,n,list(reversed(pairs)),basis,expected=0)
        pairs,basis = [(1,1)],[[1]]
        for change in ({0:0},{0:21},{1:0},{1:4097},{2:None},{3:None},
                       {2:(U32*1)(4)},{3:(U64*1)(2)},{5:None},{7:None},
                       {7:(U32*2)(1,1)},{7:(U32*2)(0,0)},
                       {5:(U32*1)(4)}):
            self.check_raw(2,1,pairs,basis,changes=change,expected=6)
        for e in (63,65,127):
            self.check_raw(2,e,pairs,basis,
                           changes={3:(U64*((e+63)//64))(*([0]*((e-1)//64)+[1<<(e%64)]))},expected=6)
        for bad,code in (([[]],1),([[1,1]],1),([[1,0]],2),([],3),([[1],[1]],4)):
            self.check_raw(2,1,pairs,bad,expected=code)
        self.check_raw(2,2,[(1,1),(2,2)],[[1,2],[2]],expected=5)
        for _,_,lib in self.libraries:
            self.assertEqual(lib.packed_boolean_certificate(2,1,None,None,0,None,0,None,0,None),6)

    def test_generic_rows_reject_nonmonotone_offsets(self):
        terms = (U32*2)(1,0); bad = (U32*3)(0,3,2); empty = (U32*1)(0)
        for _,_,lib in self.libraries:
            result = Certificate()
            self.assertEqual(lib.boolean_certificate(2,terms,2,bad,2,None,0,empty,0,ct.byref(result)),6)

    def test_complete_curve_replay_mutation_and_concurrent_freshness(self):
        for n,ell,seed in ((11,2,1),(31,6,101),(83,2,2)):
            original = make_instance(n,3,ell,seed=seed)
            with NativeDescent(n,original.mod,original.b,3,ell) as native:
                anf = native.descend_packed(original.xR)
                results = []
                for arm in ARMS:
                    for sanitizer in (False,True):
                        with query(original.nvars,n,arm,sanitizer=sanitizer) as checker:
                            result = checker.solve(replace(original,anf=anf))
                            self.assertTrue(result.get('verified'),result)
                            self.assertEqual(original.evaluate(result['assignment']),0)
                            results.append((result['basis_sha256'],result['assignment'],result['basis_certificate']))
                            basis = checker.compute(anf)['basis_terms']
                            bad = anf.to_dict(); bad[0] = bad.get(0,0)^((1<<n)-1)
                            calls = [anf,bad]*8
                            with ThreadPoolExecutor(max_workers=4) as executor:
                                answers = list(executor.map(lambda a:checker.certify(a,basis),calls))
                            self.assertEqual([a['verified'] for a in answers],[True,False]*8)
                self.assertTrue(all(r==results[0] for r in results))


if __name__=='__main__': unittest.main()
