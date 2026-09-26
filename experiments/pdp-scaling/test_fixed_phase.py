"""Independent arithmetic/oracle tests for the fixed-phase PDP experiment."""
import itertools
import random
import unittest

from fixed_phase import (AnfTemplate, Circuit, FieldCircuit, Template, bases, direct_anf, exact_oracle,
                         payload_x, scalar, subgroup_order)
from gf2n import Curve, GF2n
import sumpoly


class CircuitTests(unittest.TestCase):
    def test_field_circuit_against_numeric_field(self):
        F, c = GF2n(5), Circuit()
        fc = FieldCircuit(F, c)
        x, y = fc.inputs(), fc.inputs()
        mul, sq = fc.mul(x, y), fc.square(x)
        for a, b in itertools.product(range(32), repeat=2):
            inputs = {w: bool(a >> j & 1) for j, w in enumerate(x)}
            inputs.update({w: bool(b >> j & 1) for j, w in enumerate(y)})
            values = c.evaluate(inputs)
            decode = lambda wires: sum(int(values[w]) << j for j, w in enumerate(wires))
            self.assertEqual(decode(mul), F.mul(a, b))
            self.assertEqual(decode(sq), F.sqr(a))

    def test_s4_against_independent_resultant(self):
        F, c = GF2n(5), Circuit()
        fc = FieldCircuit(F, c)
        words = [fc.inputs() for _ in range(4)]
        out = fc.s4(*words)
        polynomial = sumpoly.load(4)[4]
        rng = random.Random(981)
        for _ in range(100):
            xs = [rng.randrange(32) for _ in range(4)]
            values = c.evaluate({w: bool(x >> j & 1)
                                 for x, wires in zip(xs, words) for j, w in enumerate(wires)})
            actual = sum(int(values[w]) << j for j, w in enumerate(out))
            expected = 0
            for mono in polynomial:
                term = 1
                for x, e in zip(xs, mono[:4]):
                    term = F.mul(term, F.pow(x, e))
                expected ^= term
            self.assertEqual(actual, expected)

    def test_phase_payload_maps(self):
        F = GF2n(7)
        for phase in range(7):
            basis = bases(F, 4, (phase,) * 3)[0]
            for payload in range(16):
                self.assertEqual(payload_x(payload, basis), F.frob(payload, phase))

    def test_solver_matches_full_small_subgroup_and_reuse(self):
        F = GF2n(7)
        E, r = Curve(F, 1), subgroup_order(7)
        self.assertEqual(r, 29)
        targets = [p for x in range(1, 128) if (p := E.lift_x(x)) is not None
                   and scalar(E, r, p).inf]
        self.assertEqual(len(targets), 14)
        sat_count = unsat_count = rejected = 0
        for phases, encoding, guess in itertools.product(((0, 0, 0), (0, 1, 2)),
                                                         ("s4", "s3-chain"), (0, 2)):
            t = Template(F, 4, phases, encoding)
            solver = t.c.solver()
            for R in targets + [E.neg(p) for p in reversed(targets)]:
                truth = exact_oracle(E, r, t.bases, R)
                result = t.search(solver, E, r, R, guess, 5.0)
                self.assertNotEqual(result["status"], "timeout")
                self.assertEqual(result["status"] == "sat", truth is not None)
                rejected += result["rejected"]
                if truth is not None:
                    sat_count += 1
                    self.assertIsNotNone(t.verify(E, r, R, result["payloads"]))
                else:
                    unsat_count += 1
        self.assertGreater(sat_count, 0)
        self.assertGreater(unsat_count, 0)
        self.assertGreater(rejected, 0)

    def test_chain_infinity_branch(self):
        F = GF2n(7)
        E, r = Curve(F, 1), subgroup_order(7)
        t = Template(F, 4, (0, 0, 0), "s3-chain")
        p = next(E.lift_x(x) for x in range(1, 16)
                 if E.lift_x(x) is not None and scalar(E, r, E.lift_x(x)).inf)
        solver = t.c.solver()
        assumptions = t.target_assumptions(p.x) + [-t.finite]
        assumptions += [w if p.x >> j & 1 else -w for block in t.payload for j, w in enumerate(block)]
        sat, model = solver.solve(assumptions)
        self.assertTrue(sat)
        self.assertIsNotNone(t.verify(E, r, p, t.assignment(model)))

    def test_direct_anf_matches_existing_descent(self):
        from descend import descend
        F = GF2n(7)
        E = Curve(F, 1)
        S = sumpoly.load(4)
        for r in (0, 1, 7, 33):
            self.assertEqual(direct_anf(F, 3, (0, 0, 0), r), descend(S, F, E, 3, 3, r))
        for phases in ((0, 0, 0), (0, 1, 2)):
            for x in range(1, 128):
                R = E.lift_x(x)
                if R is None or not scalar(E, 29, R).inf:
                    continue
                t = AnfTemplate(F, 4, phases, R.x)
                result = t.search(t.c.solver(), E, 29, R, 0, 5.0)
                self.assertNotEqual(result["status"], "timeout")
                self.assertEqual(result["status"] == "sat", exact_oracle(E, 29, t.bases, R) is not None)

    def test_boolean_export_matches_sat_model(self):
        import tempfile
        from pathlib import Path
        F = GF2n(5)
        for encoding in ("s4", "s3-chain"):
            t = Template(F, 3, (0, 0, 0), encoding)
            sat, model = t.c.solver().solve(t.target_assumptions(2))
            self.assertTrue(sat)
            assignment = sum(int(bool(v)) << (j - 1) for j, v in enumerate(model) if j)
            equations = t.boolean_equations(2)
            evaluate = lambda eq: sum((mask & ~assignment) == 0 for mask in eq) % 2
            self.assertTrue(all(evaluate(eq) == 0 for eq in equations))
            self.assertTrue(any(evaluate(eq) != 0 for eq in t.boolean_equations(3)))
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "system.ms"
                t.export_msolve(path, 2)
                self.assertEqual(path.read_text().splitlines()[1], "2")
                with self.assertRaises(FileExistsError):
                    t.export_msolve(path, 2)

    def test_timeout_is_not_unsat(self):
        F = GF2n(7)
        E, r = Curve(F, 1), subgroup_order(7)
        t = Template(F, 3, (0, 0, 0), "s4")
        result = t.search(t.c.solver(), E, r, E.lift_x(1), 0, 0.0)
        self.assertEqual(result["status"], "timeout")


if __name__ == "__main__":
    unittest.main()
