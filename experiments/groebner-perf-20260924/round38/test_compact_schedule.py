"""Mixed symmetry reuse and exact full-grid equivalence on the requested GPU."""
import os
import sys
import unittest

from compact import HERE,Producer,Checker,Packed
sys.path.insert(0,str(HERE.parent/'round37'))
from fixed_width import Producer as FullGrid


@unittest.skipUnless(os.environ.get('QUADRATIC_TEST_METAL')=='1','physical Metal requested explicitly')
class ScheduleTests(unittest.TestCase):
    def test_diagonals_padded_groups_and_mixed_symmetry_reuse(self):
        # Constrain every variable to zero: one complete root, including the
        # diagonal branch. Equation labels use both sides of each block equally.
        # Then perturb only one block and restore the original input on the
        # same GPU context; stale alias rows cannot supply any answer.
        for x in (2,4,6,8,3,5):
            y=2
            # Symmetric equations for the fixed blocks: sum and product of each
            # corresponding bit force both bits to zero over the Boolean field.
            items=[]
            if x%2==0:
                for bit in range(x//2):
                    items.extend([(1<<bit,1<<(2*bit)),(1<<(bit+x//2),1<<(2*bit)),
                                  ((1<<bit)|(1<<(bit+x//2)),1<<(2*bit+1))])
            else:
                items.extend((1<<bit,1<<bit) for bit in range(x))
            items.extend((1<<(x+j),1<<(x+j)) for j in range(y))
            e=x+y
            variants=[items,items+[(1,1<<(e-1))],items+items[:2]*2,items]
            with Producer(x,y,e,backend='metal') as compact, FullGrid(x,y,e,backend='metal') as full, Checker(x,y,e) as checker:
                for index,current in enumerate(variants):
                    packed=Packed(x+y,e,current)
                    a=full.produce(packed,checker=checker)
                    b=compact.produce(packed,checker=checker)
                    self.assertTrue(a['certificate']['verified'])
                    self.assertTrue(b['certificate']['verified'])
                    self.assertEqual((a['roots'],a['basis'],a['proof_bytes']),
                                     (b['roots'],b['basis'],b['proof_bytes']))
                    symmetric=x%2==0 and index!=1
                    self.assertEqual(b['symmetry_stats']['enabled'],int(symmetric))
                    block=1<<(x//2)
                    expected=block*(block+1)//2 if symmetric else 1<<x
                    self.assertEqual(b['symmetry_stats']['gpu_linearized_branches'],expected)
                    self.assertEqual(a['symmetry_stats']['gpu_linearized_branches'],1<<x)
                    entries=block*(block+1)//2 if x%2==0 else 1
                    self.assertEqual(b['stats']['workspace_bytes']-a['stats']['workspace_bytes'],4+4*entries)


if __name__=='__main__':unittest.main()
