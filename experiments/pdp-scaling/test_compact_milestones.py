import hashlib
import json
from pathlib import Path
import unittest

from compact_milestones import OrbitRank
from fixed_phase import corpus,scalar,subgroup_order
from gf2n import GF2n,Curve,Point


class AccountingTests(unittest.TestCase):
    def test_orbit_coefficients_reconstruct_points(self):
        for n in (7,9,13,19):
            F=GF2n(n);E=Curve(F,1);r=subgroup_order(n)
            G=corpus(E,r,1,601)[0];rank=OrbitRank(E,r,G)
            p=G
            for _ in range(n):
                for q in (p,E.neg(p)):
                    key,c=rank.canonical(q)
                    self.assertEqual(scalar(E,c,Point(*key)),q)
                p=Point(F.sqr(p.x),F.sqr(p.y))

    def test_sign_and_frobenius_do_not_inflate_rank(self):
        F=GF2n(7);E=Curve(F,1);r=subgroup_order(7)
        G=corpus(E,r,1,601)[0];rank=OrbitRank(E,r,G)
        self.assertTrue(rank.add([G,G,G])[0])
        for p in (G,E.neg(G),Point(F.sqr(G.x),F.sqr(G.y))):
            independent,row=rank.add([p,p,p])
            self.assertFalse(independent)
            reconstructed=E.sum([scalar(E,c,Point(x,y)) for x,y,c in row])
            self.assertEqual(reconstructed,E.sum([p,p,p]))
        Q=next(p for k in range(2,r) if
               rank.canonical(p:=scalar(E,k,G))[0]!=rank.canonical(G)[0])
        self.assertTrue(rank.add([Q,Q,Q])[0])
        self.assertFalse(rank.add([G,E.neg(G),Q])[0])
        self.assertEqual(len(rank.pivots),2)

    def test_frozen_corpus_has_distinct_sign_orbits(self):
        path=Path(__file__).with_name('results')/'compact_corpus_100.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '2ccc317a6ca2bcacbac5c15dbbfd3aaafe5875af98579c9886e2627bd5233184')
        fixture=json.loads(path.read_text());targets=fixture['targets']
        self.assertEqual(len(targets),100)
        self.assertEqual(len({row['point'][0] for row in targets}),100)
        self.assertEqual([row['split'] for row in targets],
                         ['development']*50+['holdout']*50)
        E=Curve(GF2n(13),1);r=subgroup_order(13)
        for row in targets:
            P=Point(*row['point'])
            self.assertTrue(E.on_curve(P))
            self.assertTrue(scalar(E,r,P).inf)

    def test_composite_order_is_rejected(self):
        E=Curve(GF2n(17),1);r=subgroup_order(17)
        with self.assertRaisesRegex(ValueError,'prime subgroup'):
            OrbitRank(E,r,corpus(E,r,1,601)[0])


if __name__=='__main__':
    unittest.main()
