"""Independent small-curve oracle, forged-certificate and modular-rank tests."""
import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ordinary_campaign as c
from descend import Instance, descend
from sumpoly import summation_polynomials


class OrdinaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.E, cls.base = c.prepare(7, 4)

    def test_curve_order_and_prime_certificate(self):
        points = sum(1 if x == 0 else 2 for x in range(128) if self.E.lift_x(x) is not None) + 1
        self.assertEqual(points, c.curve_order(7))
        self.assertTrue(c.check_prime(self.base["prime_certificate"]))
        import copy
        broken = copy.deepcopy(self.base["prime_certificate"])
        broken["witnesses"][next(iter(broken["witnesses"]))] = 1
        self.assertFalse(c.check_prime(broken))

    def test_every_small_subgroup_target_against_exhaustive_oracle(self):
        E, base = self.E, self.base
        points = [c.decode(p) for p in base["original_points"]]
        decomposable = {E.sum(list(ps)) for ps in itertools.product(points, repeat=3)}
        xs = sorted({p.x for p in points})
        for k in range(1, base["subgroup_order"]):
            target = c.scalar_mul(E, c.decode(base["generator"]), k)
            found = any(c.relation(E, base, target, list(triple)) is not None
                        for triple in itertools.combinations_with_replacement(xs, 3))
            self.assertEqual(found, target in decomposable)

    def test_equations_do_not_lose_valid_small_relations(self):
        E, base = self.E, self.base
        points = [c.decode(p) for p in base["original_points"]]
        polys = summation_polynomials(4)
        for k in (1, 2, 3):
            target = c.scalar_mul(E, c.decode(base["generator"]), k)
            anf = descend(polys, E.F, E, 3, 4, target.x)
            inst = Instance(7, E.F.mod, 1, 3, 4, target.x, anf, 0, [])
            for ps in itertools.product(points, repeat=3):
                if E.sum(list(ps)) == target:
                    word = sum(p.x << (i * 4) for i, p in enumerate(ps))
                    self.assertEqual(inst.evaluate(word), 0)

    def test_incremental_rank_matches_separate_batch_elimination(self):
        from sympy import GF
        from sympy.polys.matrices import DomainMatrix
        rng = random.Random(9)
        rows, tracker = [], c.RelationRank(29, 7)
        for _ in range(15):
            row = [rng.randrange(-2, 3) for _ in range(7)]
            rows.append(row)
            tracker.add(row)
            self.assertEqual(tracker.rank, DomainMatrix.from_list(rows, GF(29)).rank())

    def test_bad_row_rejected_on_replay(self):
        E, base = self.E, self.base
        points = [c.decode(p) for p in base["original_points"]]
        for k in range(1, base["subgroup_order"]):
            target = c.scalar_mul(E, c.decode(base["generator"]), k)
            cert = next((cert for ps in itertools.product(points, repeat=3)
                         if (cert := c.relation(E, base, target, [p.x for p in ps]))), None)
            if cert:
                break
        cert["rhs_scalar"] = base["cofactor"] * k % base["subgroup_order"]
        tracker = c.RelationRank(base["subgroup_order"], base["effective_columns"])
        tracker.add(cert["coefficients"])
        event = {"event": "attempt", "index": 0, "certificate": cert, "rank_after": tracker.rank}
        manifest = {"base": base, "workloads": [{"work": {"queries": [{"scalar": k, "point": c.encode(target)}]}}]}
        self.assertEqual(c.replay(manifest, 0, [event]), (1, tracker.rank))
        cert["coefficients"][0] += 1
        with self.assertRaises(ValueError):
            c.replay(manifest, 0, [event])


if __name__ == "__main__":
    unittest.main()
