"""Check the compact S3 circuit against exact curve arithmetic."""

import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from chain_s3 import (Formula, build, evaluate_s3, multiplication_table,
                      square_destinations)
from chain_s3_factored import build_factored
from chain_s3_multitarget import (build_multitarget, choose_target_x,
                                  decode_choice)
from chain_s3_orbit import frobenius_barrel
from chain_s3_ordered import less_or_equal
from chain_s3_rational import add_rationality_filter
from run_probe import lift, parse_model
from ecc2k130.codegen import curves, field


class ChainS3Tests(unittest.TestCase):
    def test_multiplication_table(self):
        for n in (5, 53, 83):
            onb = field.Onb(n)
            table = multiplication_table(onb)
            rng = random.Random(n)
            for _ in range(12):
                a = rng.getrandbits(n)
                b = rng.getrandbits(n)
                got = 0
                for i in range(n):
                    if a >> i & 1:
                        for j in range(n):
                            if b >> j & 1:
                                got ^= table[i][j]
                self.assertEqual(got, onb.toCoords(onb.mul(
                    onb.fromCoords(a), onb.fromCoords(b))))

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_planted_four_points_satisfy_circuit(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x))
                  for x in range(1, 1 << 5) if x.bit_count() <= 2]
        points = [point for point in points if point is not None]
        rng = random.Random(19)
        while True:
            chosen = [rng.choice(points) for _ in range(4)]
            first = curve.add(chosen[0], chosen[1])
            second = curve.add(first, chosen[2])
            target = curve.add(second, chosen[3])
            if first and second and target and target[0]:
                break
        for values in ((chosen[0][0], chosen[1][0], first[0]),
                       (first[0], chosen[2][0], second[0]),
                       (second[0], chosen[3][0], target[0])):
            self.assertEqual(evaluate_s3(onb, *values), 0)
        formula, leaves, mids = build(5, 2, onb.toCoords(target[0]))
        for variables, point in zip(leaves, chosen):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([var if value >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
        for variables, point in zip(mids, (first, second)):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([var if value >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "planted.xcnf"
            formula.write(path)
            result = subprocess.run(["cryptominisat5", "--verb", "0",
                                     "--threads", "1", str(path)],
                                    capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 10, result.stdout[-500:])
        coords, relation, status = lift(onb, curve, leaves,
                                        parse_model(result.stdout), target,
                                        curve.mul(target, 4), 4)
        self.assertEqual(status, "verified_four_point_relation")
        self.assertEqual(coords, [onb.toCoords(p[0]) for p in chosen])
        self.assertIsNotNone(relation)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_factored_chain_accepts_witness_and_rejects_wrong_target(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x))
                  for x in range(1, 1 << 5) if x.bit_count() <= 2]
        points = [point for point in points if point is not None]
        rng = random.Random(29)
        while True:
            leaves = [rng.choice(points) for _ in range(4)]
            first = curve.add(leaves[0], leaves[1])
            if first is None:
                continue
            second = curve.add(first, leaves[2])
            if second is None:
                continue
            target = curve.add(second, leaves[3])
            if target is not None and target[0]:
                break
        target_x = onb.toCoords(target[0])
        bad_x = next(x for x in range(1, 1 << 5) if
                     evaluate_s3(onb, second[0], leaves[3][0],
                                 onb.fromCoords(x)) != 0)

        def locked_result(x):
            formula, leaf_variables, mids = build_factored(5, 2, x)
            for variables, point in zip(leaf_variables, leaves):
                value = onb.toCoords(point[0])
                formula.clauses.extend(([var if value >> i & 1 else -var]
                                        for i, var in enumerate(variables)))
            for variables, point in zip(mids, (first, second)):
                value = onb.toCoords(point[0])
                formula.clauses.extend(([var if value >> i & 1 else -var]
                                        for i, var in enumerate(variables)))
            with tempfile.TemporaryDirectory() as name:
                path = Path(name) / "factored.xcnf"
                formula.write(path)
                return subprocess.run(["cryptominisat5", "--verb", "0",
                                       "--threads", "1", str(path)],
                                      capture_output=True, text=True,
                                      timeout=20).returncode

        self.assertEqual(locked_result(target_x), 10)
        self.assertEqual(locked_result(bad_x), 20)

    def test_factored_formula_reduces_non_linear_gates(self):
        for n, weight in ((53, 3), (83, 4)):
            old, _, _ = build(n, weight, 123456789)
            new, _, _ = build_factored(n, weight, 123456789)
            self.assertLess(len(new.and_cache), len(old.and_cache))
            self.assertLess(len(new.clauses), len(old.clauses))

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_multitarget_selector_finds_only_valid_raw_sum(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x))
                  for x in range(1, 1 << 5) if x.bit_count() <= 2]
        points = [point for point in points if point is not None]
        rng = random.Random(31)
        while True:
            leaves = [rng.choice(points) for _ in range(4)]
            first = curve.add(leaves[0], leaves[1])
            if first is None:
                continue
            second = curve.add(first, leaves[2])
            if second is None:
                continue
            total = curve.add(second, leaves[3])
            if total is not None and total[0]:
                break
        correct = onb.toCoords(total[0])
        wrong = next(x for x in range(1, 1 << 5)
                     if evaluate_s3(onb, second[0], leaves[3][0],
                                    onb.fromCoords(x)) != 0)

        def solve(targets):
            formula, leaf_variables, mids, _, selector = build_multitarget(
                5, 2, targets)
            for variables, point in zip(leaf_variables, leaves):
                x = onb.toCoords(point[0])
                formula.clauses.extend(([bit if x >> i & 1 else -bit]
                                        for i, bit in enumerate(variables)))
            for variables, point in zip(mids, (first, second)):
                x = onb.toCoords(point[0])
                formula.clauses.extend(([bit if x >> i & 1 else -bit]
                                        for i, bit in enumerate(variables)))
            with tempfile.TemporaryDirectory() as name:
                path = Path(name) / "choice.xcnf"
                formula.write(path)
                result = subprocess.run(["cryptominisat5", "--verb", "0",
                                         "--threads", "1", str(path)],
                                        capture_output=True, text=True,
                                        timeout=20)
            return result.returncode, decode_choice(
                selector, parse_model(result.stdout) or {})

        self.assertEqual(solve([wrong, correct]), (10, 1))
        self.assertEqual(solve([wrong])[0], 20)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_rational_support_filter_is_exact_under_weight_bound(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        masks = [mask for mask in range(1, 1 << 5)
                 if mask.bit_count() <= 2]
        invalid = [mask for mask in masks if curve.pointFromX(
            onb.fromCoords(mask)) is None]
        for mask in masks:
            formula = Formula()
            variables = [formula.new() for _ in range(5)]
            formula.at_most(variables, 2)
            formula.clauses.append(variables[:])
            add_rationality_filter(formula, [variables], invalid, 2)
            formula.clauses.extend(([var if mask >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
            with tempfile.TemporaryDirectory() as name:
                path = Path(name) / "filter.xcnf"
                formula.write(path)
                result = subprocess.run(["cryptominisat5", "--verb", "0",
                                         "--threads", "1", str(path)],
                                        capture_output=True, text=True,
                                        timeout=20)
            self.assertEqual(result.returncode, 20 if mask in invalid else 10,
                             mask)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_frobenius_barrel_matches_field_on_every_small_shift(self):
        onb = field.Onb(5)
        xs = (3, 19)
        for choice, x in enumerate(xs):
            for shift in range(5):
                formula = Formula()
                base, base_selector = choose_target_x(formula, 5, xs)
                output, shift_selector = frobenius_barrel(
                    formula, base, square_destinations(onb))
                formula.clauses.extend(([
                    bit if choice >> i & 1 else -bit]
                    for i, bit in enumerate(base_selector)))
                formula.clauses.extend(([
                    bit if shift >> i & 1 else -bit]
                    for i, bit in enumerate(shift_selector)))
                with tempfile.TemporaryDirectory() as name:
                    path = Path(name) / "frob.xcnf"
                    formula.write(path)
                    result = subprocess.run(["cryptominisat5", "--verb", "0",
                                             "--threads", "1", str(path)],
                                            capture_output=True, text=True,
                                            timeout=20)
                self.assertEqual(result.returncode, 10)
                values = parse_model(result.stdout)
                got = sum(1 << i for i, bit in enumerate(output)
                          if values.get(bit, False))
                want = onb.toCoords(onb.frob(onb.fromCoords(x), shift))
                self.assertEqual(got, want)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_leaf_order_comparator_accepts_exactly_non_decreasing_values(self):
        for left_value in range(8):
            for right_value in range(8):
                formula = Formula()
                left = [formula.new() for _ in range(3)]
                right = [formula.new() for _ in range(3)]
                less_or_equal(formula, left, right)
                for variables, value in ((left, left_value),
                                         (right, right_value)):
                    formula.clauses.extend(([
                        bit if value >> i & 1 else -bit]
                        for i, bit in enumerate(variables)))
                with tempfile.TemporaryDirectory() as name:
                    path = Path(name) / "ordered.xcnf"
                    formula.write(path)
                    result = subprocess.run(["cryptominisat5", "--verb", "0",
                                             "--threads", "1", str(path)],
                                            capture_output=True, text=True,
                                            timeout=20)
                self.assertEqual(result.returncode,
                                 10 if left_value <= right_value else 20,
                                 (left_value, right_value))


if __name__ == "__main__":
    unittest.main()
