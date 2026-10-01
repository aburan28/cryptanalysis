import itertools
import unittest

from fixed_phase import Template, exact_oracle, payload_x, scalar, subgroup_order
from gf2n import Curve, GF2n
from toy_domain import ToyDomainTemplate


class DomainTests(unittest.TestCase):
    def test_admissibility_for_every_payload_and_phase(self):
        for n,l in ((7,4),(13,6)):
            F=GF2n(n); E=Curve(F,1); r=subgroup_order(n)
            for phases in ((0,0,0),(0,1,2),(n-1,n+1,2*n+3)):
                t=ToyDomainTemplate(F,l,phases,'s3-chain')
                for basis in t.bases:
                    for u in range(1 << l):
                        x=payload_x(u,basis)
                        p=E.lift_x(x) if x else None
                        expected=p is not None and scalar(E,r,p).inf
                        self.assertEqual(u in t.domain_payloads,expected)

    def test_exhaustive_small_group_both_encodings(self):
        F=GF2n(7); E=Curve(F,1); r=subgroup_order(7)
        targets=[p for x in range(1,128) if (p:=E.lift_x(x)) is not None and scalar(E,r,p).inf]
        sat=unsat=0
        for phases,encoding in itertools.product(((0,0,0),(0,1,2)),('s4','s3-chain')):
            t=ToyDomainTemplate(F,4,phases,encoding); solver=t.c.solver()
            for R in targets+[E.neg(p) for p in reversed(targets)]:
                out=t.search(solver,E,r,R,2,2)
                self.assertNotEqual(out['status'],'timeout')
                truth=exact_oracle(E,r,t.bases,R)
                self.assertEqual(out['status']=='sat',truth is not None)
                sat+=out['status']=='sat'; unsat+=out['status']=='unsat'
                if truth is not None:
                    self.assertIsNotNone(t.verify(E,r,R,out['payloads']))
        self.assertGreater(sat,0); self.assertGreater(unsat,0)

    def test_larger_field_positive_and_negative_targets(self):
        F=GF2n(13); E=Curve(F,1); r=subgroup_order(13)
        t=ToyDomainTemplate(F,6,(0,1,2),'s3-chain'); solver=t.c.solver()
        # Planted positive is a correctness fixture only, never a benchmark input.
        pts=[E.lift_x(payload_x(t.domain_payloads[0],basis)) for basis in t.bases]
        positive=E.sum(pts)
        self.assertFalse(positive.inf)
        negative=next(p for x in range(1,1<<13) if (p:=E.lift_x(x)) is not None
                      and scalar(E,r,p).inf and exact_oracle(E,r,t.bases,p) is None)
        for R,want in ((positive,'sat'),(negative,'unsat'),(E.neg(positive),'sat')):
            out=t.search(solver,E,r,R,2,5)
            self.assertEqual(out['status'],want)

    def test_empty_domain_and_size_guard(self):
        F=GF2n(7); E=Curve(F,1)
        t=ToyDomainTemplate(F,3,(0,1,2),'s3-chain')
        self.assertEqual(t.domain_payloads,[])
        p=E.lift_x(12)
        self.assertEqual(t.search(t.c.solver(),E,29,p,0,1)['status'],'unsat')
        with self.assertRaises(ValueError):
            ToyDomainTemplate(GF2n(13),9,(0,1,2),'s3-chain')
        with self.assertRaises(ValueError):
            ToyDomainTemplate(GF2n(23),4,(0,1,2),'s3-chain')


if __name__=='__main__':
    unittest.main()
