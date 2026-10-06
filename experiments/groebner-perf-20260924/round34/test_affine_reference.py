"""Independent reference specialization, identity and policy-counter controls."""
import importlib.util
import random
import sys
import unittest

from multipliers import HERE, Producer, Checker, Packed
from affine_reference import branch_model, certify_roots, producer_model
from test_multipliers import truth

_spec=importlib.util.spec_from_file_location('affine_old_reference',HERE.parent/'round33/packed_reference.py')
_old=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_old)


class ReferenceTests(unittest.TestCase):
    def verify(self,x,y,e,items):
        items=tuple(items)
        model=branch_model(x,y,e,items)
        self.assertEqual(model[:3],_old.branch_model(x,y,e,items))
        with Producer(x,y,e) as p,Checker(x,y,e) as c:
            r=p.produce(Packed(x+y,e,items),checker=c)
        roots,constant,extended,assignments=certify_roots(x,y,e,items,r['proof_bytes'],sys.byteorder)
        self.assertEqual(list(roots),truth(x+y,items))
        self.assertEqual(list(roots),r['roots'])
        self.assertEqual(constant+len(extended),r['certificate']['stats']['contradictions'])
        self.assertEqual(assignments,r['certificate']['stats']['assignments'])
        counts,stats=producer_model(x,y,e,items,roots,extended)
        self.assertTrue(all(r['stats'][k]==v for k,v in counts))
        self.assertTrue(all(r['multiplier_stats'][k]==v for k,v in stats))

    def test_exhaustive_truth_functions(self):
        for bits in range(256):
            self.verify(1,2,1,[(m,1) for m in range(8) if bits>>m&1])

    def test_random_widths_and_high_equation_affine_proofs(self):
        rng=random.Random(3401)
        for e in (1,3,31,32,33,63,64,65,127,128):
            for _ in range(3):
                self.verify(2,3,e,[(m,rng.getrandbits(e)) for m in range(32)
                                   if (m>>2).bit_count()<=2])
            if e>=3:
                self.verify(2,3,e,[(4,1),(8,2),(12,1<<(e-1)),(0,1<<(e-1))])

    def test_direct_every_coefficient_and_invalid_identity(self):
        items=((0,3),(1,1),(2,2),(4,1),(8,2),(12,4),(0,4))
        _,vectors,monomials,_,_=branch_model(2,3,3,items)
        for a,vector in enumerate(vectors):
            for j,m in enumerate(monomials):
                expected=0
                for original,c in items:
                    if original>>2==m and a&(original&3)==original&3:expected ^= c
                self.assertEqual((vector>>(3*j))&7,expected)
        with self.assertRaises(AssertionError):
            certify_roots(2,3,3,items,bytes(8),sys.byteorder)
        with self.assertRaises(ValueError):
            branch_model(2,3,3,((28,1),))


if __name__=='__main__':unittest.main()
