import unittest
from compact_admissibility import admissible,CompactTemplate,PowerCompactTemplate
from fixed_phase import scalar,subgroup_order,payload_x,exact_oracle
from gf2n import GF2n,Curve


class CompactTests(unittest.TestCase):
    def test_predicate_against_all_field_coordinates(self):
        for n in (5,7,13):
            F=GF2n(n);E=Curve(F,1);r=subgroup_order(n)
            for x in range(1<<n):
                p=E.lift_x(x) if x else None
                self.assertEqual(admissible(F,x),p is not None and scalar(E,r,p).inf,(n,x))

    def test_power_circuit_against_every_payload(self):
        for n,l in ((7,4),(13,6)):
            F=GF2n(n)
            for encoding in ('s4','s3-chain'):
                t=PowerCompactTemplate(F,l,(0,1,2),encoding)
                for u in range(1<<l):
                    # Define every primary wire; gate evaluation overwrites gate wires.
                    inputs={w:False for w in range(2,t.c.nvars+1)}
                    for block in t.payload:
                        inputs.update({w:bool(u>>j&1) for j,w in enumerate(block)})
                    vals=t.c.evaluate(inputs)
                    for basis,outputs,inv in zip(t.bases,t.admissibility_outputs,t.inverse):
                        x=payload_x(u,basis)
                        got_inv=sum(int(vals[w])<<j for j,w in enumerate(inv))
                        self.assertEqual(got_inv,F.inv(x) if x else 0)
                        got=x!=0 and not any(vals[w] for w in outputs)
                        self.assertEqual(got,admissible(F,x))

    def test_compact_solver_small_group(self):
        F=GF2n(7);E=Curve(F,1);r=subgroup_order(7)
        targets=[p for x in range(1,128) if (p:=E.lift_x(x)) is not None and scalar(E,r,p).inf]
        for factory in (CompactTemplate,PowerCompactTemplate):
            t=factory(F,4,(0,1,2),'s4');solver=t.c.solver()
            for R in targets+[E.neg(p) for p in reversed(targets)]:
                got=t.search(solver,E,r,R,2,2)
                self.assertNotEqual(got['status'],'timeout')
                self.assertEqual(got['status']=='sat',exact_oracle(E,r,t.bases,R) is not None)

    def test_compact_construction_does_not_lift_points(self):
        from unittest.mock import patch
        F=GF2n(13)
        with patch.object(Curve,'lift_x',side_effect=AssertionError('enumeration during build')):
            for factory in (CompactTemplate,PowerCompactTemplate):
                t=factory(F,6,(0,1,2),'s4')
                self.assertEqual(len(t.admissibility_outputs),3)


if __name__=='__main__':
    unittest.main()
