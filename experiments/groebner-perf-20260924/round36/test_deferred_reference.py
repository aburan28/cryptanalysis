"""Independent model checks for actual work, fresh symmetry and proof expansion."""
import os
import random
import sys
import unittest

from deferred import Producer,Checker,Packed
from deferred_reference import deferred_model,certify_roots


def swapped(m,x):
    low=(1<<x)-1
    half=x//2
    mask=(1<<half)-1
    a=m&low
    return (m&~low)|((a&mask)<<half)|(a>>half)


class ReferenceTests(unittest.TestCase):
    def check(self,x,y,e,items,**options):
        with Producer(x,y,e,**options) as p, Checker(x,y,e) as c:
            r=p.produce(Packed(x+y,e,items),checker=c)
        self.assertTrue(r['certificate']['verified'],r['certificate'])
        roots,_,extended,_=certify_roots(x,y,e,tuple(items),r['proof_bytes'],sys.byteorder)
        self.assertEqual(list(roots),r['roots'])
        counts,expected,expected_symmetry,expected_deferred=deferred_model(x,y,e,tuple(items),roots,extended,
            copy_budget=0 if options.get('copy_budget_test') else (64<<20)//8,
            reconstruction_limit=0 if options.get('reconstruction_budget_test') else 67108864)
        for key,value in counts:self.assertEqual(r['stats'][key],value,key)
        actual=dict(r['multiplier_stats']);actual.pop('seconds')
        self.assertEqual(actual,dict(expected))
        actual=dict(r['symmetry_stats']);actual.pop('check_seconds');actual.pop('expand_seconds')
        expected_symmetry=dict(expected_symmetry)
        expected_symmetry['gpu_linearized_branches']=(1<<x)*r['stats']['gpu_used']
        self.assertEqual(actual,expected_symmetry)
        actual=dict(r['deferred_stats']);actual.pop('reconstruction_seconds')
        self.assertEqual(actual,dict(expected_deferred))
        width=4 if e<=32 else 8 if e<=64 else 16
        workspace=(1<<x)*(y*(y+1)//2+1)*width+dict(expected)['proof_capacity_words']*8+dict(expected)['workspace_bytes']+expected_symmetry['workspace_bytes']
        if r['stats']['gpu_used']:workspace+=(1<<x)*(y*(y+1)//2+1)*4+(1<<x)*34*4+12
        self.assertEqual(r['stats']['workspace_bytes'],workspace)
        return r

    def test_every_three_variable_function(self):
        for bits in range(256):
            self.check(2,1,1,[(m,1) for m in range(8) if bits>>m&1])

    def test_symmetric_and_asymmetric_widths_and_proof_copy_bounds(self):
        rng=random.Random(2026092935)
        backends=('cpu','metal') if os.environ.get('QUADRATIC_TEST_METAL')=='1' else ('cpu',)
        for e in (1,3,31,32,33,63,64,65,127,128):
            for backend in backends:
                for x,y in ((2,3),(4,2),(3,2)):
                    coefficients={m:rng.getrandbits(e) for m in range(1<<(x+y)) if (m>>x).bit_count()<=2}
                    if x%2==0:
                        for m in coefficients:coefficients[m]=coefficients[min(m,swapped(m,x))]
                    items=list(coefficients.items())
                    self.check(x,y,e,items+items[:2]*2,backend=backend)
                    self.check(x,y,e,items+[(1,1)],backend=backend)
                if e>=3:
                    items=[(4,1),(8,2),(12,1<<(e-1)),(0,1<<(e-1))]
                    result=self.check(2,2,e,items,backend=backend)
                    self.assertEqual(result['symmetry_stats']['affine_copies'],1)
                    self.check(2,2,e,items,copy_budget_test=True)
                    fallback=self.check(2,2,e,items,reconstruction_budget_test=True)
                    self.assertEqual(fallback['deferred_stats']['reconstruction_pivots'],0)
                    self.assertGreater(fallback['deferred_stats']['reconstruction_attempts'],0)
                    self.assertGreater(fallback['multiplier_stats']['budget_skips'],0)
                    self.assertEqual(fallback['certificate']['stats']['assignments'],16)


    def test_high_dependency_columns_with_sanitizer_and_full_provenance(self):
        from deferred import HERE
        sys.path.insert(0,str(HERE.parent/'round35'))
        from symmetry import Producer as Forward
        for y in (6,7,8,9,10):
            for e in (31,32,33,63,64,65,127,128):
                first=1<<(2+y-2)
                second=1<<(2+y-1)
                items=[(first,1),(second,1<<(e//2)),(first|second,1<<(e-1)),(0,1<<(e-1))]
                result=self.check(2,y,e,items,sanitizer=True)
                with Forward(2,y,e,sanitizer=True) as old:
                    reference=old.produce(Packed(2+y,e,items))
                self.assertEqual(result['proof_bytes'],reference['proof_bytes'])
                self.assertGreater(result['deferred_stats']['reconstruction_pivots'],0)


if __name__=='__main__':unittest.main()
