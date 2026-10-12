"""Compare grouped specialization with untouched direct mathematical references."""
import importlib.util
import random
import sys
import unittest

from narrow import HERE, Producer, Packed
sys.path.insert(0, str(HERE.parent/'round32'))
from packed_reference import branch_model,branch_counts,contradiction_count
from quadratic_reference import branch_counts as direct_counts

_spec=importlib.util.spec_from_file_location('direct_contradiction_control',HERE.parent/'round32/test_certificates.py')
_direct=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_direct)


class PackedReferenceTests(unittest.TestCase):
    def check(self,x,y,e,items):
        counts,residuals,monomials=branch_model(x,y,e,tuple(items))
        self.assertEqual(dict(counts),direct_counts(x,y,e,items))
        for assignment,vector in enumerate(residuals):
            for index,monomial in enumerate(monomials):
                expected=0
                for mask,coefficient in items:
                    if mask>>x==monomial and mask&((1<<x)-1)&assignment==mask&((1<<x)-1): expected ^= coefficient
                self.assertEqual((vector>>(e*index))&((1<<e)-1),expected)
        with Producer(x,y,e) as producer:
            answer=producer.produce(Packed(x+y,e,items))
        count=contradiction_count(x,y,e,items,answer['proof_bytes'],answer['proof_byteorder'])
        self.assertEqual(count,_direct.verify_contradictions(x,y,e,items,answer['proof_bytes']))

    def test_all_three_variable_functions(self):
        for bits in range(256): self.check(1,2,1,[(m,1) for m in range(8) if bits>>m&1])

    def test_random_wide_equations_duplicates_and_all_coefficients(self):
        rng=random.Random(202609293301)
        for x,y in ((1,1),(3,3),(5,2)):
            for e in (1,31,32,33,64,65,128):
                items=[(m,rng.getrandbits(e)) for m in range(1<<(x+y)) if (m>>x).bit_count()<=2 and rng.randrange(3)==0]
                items += [(0,1),(0,1),(1,0)]
                self.check(x,y,e,items)

    def test_rejects_invalid_inputs_and_identity(self):
        for args in ((17,1,1,()),(1,1,129,()),(1,3,1,((14,1),)),(1,1,1,((4,1),)),(1,1,1,((1,2),))):
            with self.assertRaises(ValueError): branch_model(*args)
        with self.assertRaises(AssertionError): contradiction_count(1,1,1,[(1,1)],b'\1'+b'\0'*15,'little')
        with self.assertRaises(AssertionError): contradiction_count(1,1,1,[(1,1)],b'\0'*8,'little')


if __name__=='__main__': unittest.main()
