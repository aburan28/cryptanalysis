import concurrent.futures
import ctypes as ct
import itertools
from pathlib import Path
import random
import unittest

from conditional import Basis, Checker, Inconclusive, Packed, Producer, Stats, U32, U64, Unsupported
from reference import branch_counts, evaluate, full_roots, verify_basis


def planted(x,y,e,seed):
    rng = random.Random(seed)
    target = rng.randrange(1<<(x+y))
    masks = [0,*[1<<j for j in range(x+y)],
             *[(1<<i)|(1<<(x+j)) for i in range(x) for j in range(y)]]
    items = [(m,rng.randrange(1<<e)) for m in masks if m]
    return [(0,evaluate(items,target)),*items], target


class ConditionalTests(unittest.TestCase):
    def compare(self,x,y,e,items,sanitizer=False,enumerate_all=True):
        packed = Packed(x+y,e,items)
        with Basis(x,y,e,sanitizer=sanitizer) as b:
            answer = b.compute(packed)
            self.assertEqual(answer['status'],'gb')
            certificate = answer['basis_certificate']
            roots = certificate['solutions']
            if enumerate_all:
                self.assertEqual(roots,full_roots(x+y,items))
            counts = branch_counts(x,y,e,items)
            self.assertEqual(len(roots),counts['root_count'])
            self.assertEqual(certificate['stats']['branches'],1<<x)
            self.assertEqual(answer['metrics']['branches'],1<<x)
            self.assertTrue(verify_basis(x+y,items,roots,answer['basis_terms'],len(roots)))
            self.assertTrue(all(b.checker.evaluate(packed,r)==0 for r in roots))
            return answer

    def test_all_two_variable_two_equation_systems(self):
        for sanitizer in (False,True):
            for coefficients in itertools.product(range(4),repeat=4):
                self.compare(1,1,2,list(enumerate(coefficients)),sanitizer)

    def test_random_bilinear_wide_equations(self):
        for sanitizer in (False,True):
            for e in (1,2,7,63,64,65,83,127,128):
                for seed in range(4):
                    items,_=planted(2,3,e,100*e+seed)
                    self.compare(2,3,e,items,sanitizer)

    def test_large_exact_certificates(self):
        for sanitizer in (False,True):
            for x,y,e in ((11,11,31),(12,12,31),(8,24,65),(5,43,83),(1,62,128)):
                items,target=planted(x,y,e,1000+x+y)
                answer=self.compare(x,y,e,items,sanitizer,False)
                self.assertIn(target,answer['basis_certificate']['solutions'])

    def test_root_limit_and_empty_unit_ideals(self):
        for sanitizer in (False,True):
            self.compare(4,4,1,[],sanitizer)  # exactly 256
            self.compare(1,62,1,[(0,1)],sanitizer,False)
            with Basis(4,5,1,sanitizer=sanitizer) as b:
                p=Packed(9,1,[])
                self.assertEqual(b.compute(p)['status'],'inconclusive')
                cert=b.checker.certify(p,[],[[0]])
                self.assertFalse(cert['verified'])
                self.assertEqual(cert['code'],5)
                self.assertIsNone(cert['root_count'])
                self.assertEqual(b.compute(Packed(9,1,[(0,1)]))['status'],'gb')

    def test_branch_count_completeness_and_corrupt_basis(self):
        items=[(3,1)]
        p=Packed(2,1,items)
        for sanitizer in (False,True):
            with Producer(1,1,1,sanitizer=sanitizer) as producer, Checker(1,1,1,sanitizer=sanitizer) as c:
                result=producer.produce(p)
                roots,basis=result['roots'],result['basis']
                self.assertTrue(c.certify(p,roots,basis)['verified'])
                for wrong in (roots[:-1],roots[1:],[],[0,0,1],[0,1,3],list(reversed(roots))):
                    self.assertFalse(c.certify(p,wrong,basis)['verified'])
                for bad in ([],[[0]],[[1]],[[2]],[[3],[3]],[[3,0]],[[0,3]],[[0,0,3]],[[]]):
                    self.assertFalse(c.certify(p,roots,bad)['verified'])

    def test_linear_dependencies_and_rank_changes(self):
        for sanitizer in (False,True):
            for seed in range(16):
                rng=random.Random(seed)
                # Repeated coordinate equations and rank varying with x.
                items=[(0,rng.randrange(4)),(1,3),(2,3),(5,3),(10,3),(16,2)]
                self.compare(2,3,2,items,sanitizer)

    def test_duplicate_parity_zero_terms_and_unordered_inputs(self):
        for sanitizer in (False,True):
            items=[(16,3),(0,1),(5,2),(16,3),(5,2),(15,0),(2,1)]
            self.compare(2,3,2,items,sanitizer)

    def test_nonlinear_rejected_and_no_stale_result(self):
        for sanitizer in (False,True):
            with Basis(2,2,1,sanitizer=sanitizer) as b:
                good=Packed(4,1,[(0,1)])
                self.assertEqual(b.compute(good)['status'],'gb')
                for m in (3,12,15):
                    bad=Packed(4,1,[(m,1)])
                    self.assertEqual(b.compute(bad)['status'],'unsupported')
                    self.assertEqual(b.checker.certify(bad,[],[[0]])['code'],7)
                self.assertEqual(b.compute(good)['basis_terms'],[[0]])

    def test_dimensions_and_packed_extents(self):
        for dims in ((0,2,3),(21,1,1),(1,63,1),(1,1,129),(True,1,1),(1,0,1)):
            with self.assertRaises(ValueError):
                Basis(*dims)
        with Basis(1,1,2) as b:
            p=Packed(2,2,[(1,1)])
            p.coefficients=(U64*0)()
            with self.assertRaises(ValueError): b.compute(p)
            p=Packed(2,2,[(1,1)])
            p.masks[0]=4
            with self.assertRaises(ValueError): b.compute(p)
            p.masks[0]=1
            p.coefficients[0]=4
            with self.assertRaises(ValueError): b.compute(p)
            with self.assertRaises(ValueError): b.checker.evaluate(p,False)
        for items in ([(True,1)],[(1,True)],[(4,1)],[(1,4)],[(-1,1)]):
            with self.assertRaises(ValueError): Packed(2,2,items)

    def test_32_bit_views_do_not_materialize_anf(self):
        class Legacy:
            nvars,equations=4,2
            masks=(U32*3)(0,1,4)
            coefficients=(U64*3)(3,1,2)
            def to_dict(self): raise AssertionError('ANF materialized')
            def items(self): raise AssertionError('ANF iterated')
        with Basis(2,2,2) as b:
            answer=b.compute(Legacy())
            self.assertEqual(answer['basis_certificate']['solutions'],[5,7,13,15])

    def test_lifetime_concurrent_calls_and_result_ownership(self):
        with Basis(2,3,5) as b:
            inputs=[Packed(5,5,planted(2,3,5,s)[0]) for s in range(12)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                answers=list(pool.map(b.compute,inputs))
            for p,a in zip(inputs,answers):
                self.assertEqual(a['status'],'gb')
                self.assertTrue(all(b.checker.evaluate(p,r)==0 for r in a['basis_certificate']['solutions']))
            b.close()
            b.close()
            with self.assertRaises(RuntimeError): b.compute(inputs[0])
            with self.assertRaises(RuntimeError): b.checker.certify(inputs[0],[],[])
            with self.assertRaises(RuntimeError): b.producer.produce(inputs[0])

    def test_raw_abi_rejects_shapes_and_noncanonical_rows(self):
        with Producer(1,1,65) as p, Checker(1,1,65) as c:
            stats=Stats()
            masks=(U64*1)(1)
            coefficients=(U64*2)(0,2) # bit 65 is outside equations
            self.assertFalse(p.lib.branch_solve(p._handle,masks,64,coefficients,1,ct.byref(stats)))
            self.assertEqual(p.lib.branch_error_code(),6)
            self.assertFalse(p.lib.branch_solve(p._handle,masks,17,coefficients,1,ct.byref(stats)))
            roots,terms,offsets=(U64*0)(),(U64*1)(0),(U32*2)(1,1)
            self.assertEqual(c.lib.branch_check(c._handle,masks,64,coefficients,1,
                roots,0,terms,1,offsets,1,ct.byref(stats)),6)
            self.assertEqual(c.lib.branch_check(None,masks,64,coefficients,1,
                roots,0,terms,1,offsets,1,ct.byref(stats)),6)
            for x,y,e in ((1,2**32-1,1),(2**32-1,1,1),(20,44,1)):
                self.assertFalse(p.lib.branch_create(x,y,e))
                self.assertFalse(c.lib.check_create(x,y,e))

    def test_proof_budget_is_inconclusive(self):
        items=[(1<<j,1<<j) for j in range(6)]
        packed=Packed(6,6,items)
        with Producer(3,3,6) as p, Checker(3,3,6,budget_test=True) as c:
            result=p.produce(packed)
            cert=c.certify(packed,result['roots'],result['basis'])
            self.assertEqual(cert['code'],5)
            self.assertFalse(cert['verified'])
            self.assertIsNone(cert['root_count'])


if __name__=='__main__':
    unittest.main()
