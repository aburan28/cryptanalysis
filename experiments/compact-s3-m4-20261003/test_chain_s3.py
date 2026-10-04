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
from chain_s3_base_orbit import (build_base_orbit_chain,
                                 choose_base_orbit_x, decode_base_choice)
from chain_s3_multitarget import (build_multitarget, choose_target_x,
                                  decode_choice)
from chain_s3_projected_sparse import projected_sparse_leaf
from s3_root_oracle import half_trace, s3_roots
from chain_s3_rooted import half_trace_columns, s3_root_link
from chain_group_add import add_four_to_target, inverse_circuit
from chain_s3_orbit import frobenius_barrel
from chain_s3_ordered import less_or_equal
from chain_s3_rational import add_rationality_filter
from run_probe import lift, parse_model
from run_base_orbit_probe import read_inputs, witness_points
from ecc2k130.codegen import curves, field


class ChainS3Tests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_forward_inverse_circuit_matches_field(self):
        for n, samples in ((5, range(1, 1 << 5)),
                           (11, (1, 2, 3, 17, 1023))):
            onb = field.Onb(n)
            table = multiplication_table(onb)
            destinations = square_destinations(onb)
            for value in samples:
                formula = Formula()
                bits = [formula.new() for _ in range(n)]
                inverse = inverse_circuit(formula, bits, table, destinations)
                formula.clauses.extend(([
                    bit if value >> position & 1 else -bit]
                    for position, bit in enumerate(bits)))
                with tempfile.TemporaryDirectory() as name:
                    path = Path(name) / "inverse.xcnf"
                    formula.write(path)
                    result = subprocess.run(
                        ["cryptominisat5", "--verb", "0", "--threads", "1",
                         str(path)], capture_output=True, text=True,
                        timeout=20)
                self.assertEqual(result.returncode, 10,
                                 (n, value, result.stdout[-500:]))
                model = parse_model(result.stdout)
                got = sum(1 << position for position, bit in
                          enumerate(inverse) if model.get(bit, False))
                expected = onb.toCoords(onb.inv(onb.fromCoords(value)))
                self.assertEqual(got, expected, (n, value))

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
    def test_exact_base_orbit_selector(self):
        onb = field.Onb(5)
        keys = (3, 5, 11)
        for index, key in enumerate(keys):
            for shift in range(5):
                formula = Formula()
                output, index_vars, shift_vars = choose_base_orbit_x(
                    formula, 5, keys, square_destinations(onb))
                for variables, value in ((index_vars, index),
                                         (shift_vars, shift)):
                    formula.clauses.extend(([
                        bit if value >> i & 1 else -bit]
                        for i, bit in enumerate(variables)))
                with tempfile.TemporaryDirectory() as name:
                    path = Path(name) / "base-orbit.xcnf"
                    formula.write(path)
                    result = subprocess.run(["cryptominisat5", "--verb", "0",
                                             "--threads", "1", str(path)],
                                            capture_output=True, text=True,
                                            timeout=20)
                self.assertEqual(result.returncode, 10)
                values = parse_model(result.stdout)
                self.assertEqual(decode_base_choice(
                    (index_vars, shift_vars), values), (index, shift))
                got = sum(1 << i for i, bit in enumerate(output)
                          if values.get(bit, False))
                want = onb.toCoords(onb.frob(onb.fromCoords(key), shift))
                self.assertEqual(got, want)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_exact_base_orbit_chain_accepts_group_witness(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x))
                  for x in range(1, 1 << 5)]
        points = [point for point in points if point is not None]
        canonical = {}
        for point in points:
            x = onb.toCoords(point[0])
            orbit = [onb.toCoords(onb.frob(point[0], shift))
                     for shift in range(5)]
            canonical[x] = min(orbit)
        keys = sorted(set(canonical.values()))
        rng = random.Random(130315)
        while True:
            selected = [rng.choice(points) for _ in range(4)]
            choices = []
            for point in selected:
                key = canonical[onb.toCoords(point[0])]
                shift = next(shift for shift in range(5)
                             if onb.toCoords(onb.frob(
                                 onb.fromCoords(key), shift)) == (
                                     onb.toCoords(point[0])))
                choices.append((keys.index(key), shift))
            selected = [point for _, point in sorted(zip(choices, selected))]
            choices.sort()
            first = curve.add(selected[0], selected[1])
            if first is None:
                continue
            second = curve.add(first, selected[2])
            if second is None:
                continue
            target = curve.add(second, selected[3])
            if target is not None and target[0]:
                break
        formula, leaves, mids, selectors = build_base_orbit_chain(
            5, keys, onb.toCoords(target[0]))
        for (index, shift), (index_vars, shift_vars) in zip(choices, selectors):
            for variables, value in ((index_vars, index),
                                     (shift_vars, shift)):
                formula.clauses.extend(([
                    bit if value >> i & 1 else -bit]
                    for i, bit in enumerate(variables)))
        for row, point in zip(mids, (first, second)):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([
                bit if value >> i & 1 else -bit]
                for i, bit in enumerate(row)))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "base-orbit-chain.xcnf"
            formula.write(path)
            result = subprocess.run(["cryptominisat5", "--verb", "0",
                                     "--threads", "1", str(path)],
                                    capture_output=True, text=True,
                                    timeout=20)
        self.assertEqual(result.returncode, 10, result.stdout[-500:])
        values = parse_model(result.stdout)
        coords, relation, status = lift(
            onb, curve, leaves, values, target, target, 1)
        self.assertEqual(status, "verified_four_point_relation")
        self.assertEqual(coords, [onb.toCoords(point[0])
                                  for point in selected])
        self.assertIsNotNone(relation)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_sparse_raw_x_projects_to_exact_cofactor_four_base(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        table = multiplication_table(onb)
        destinations = square_destinations(onb)
        for x_bits in range(1, 1 << 5):
            formula = Formula()
            raw, projected = projected_sparse_leaf(
                formula, 5, 5, table, destinations)
            formula.clauses.extend(([
                bit if x_bits >> position & 1 else -bit]
                for position, bit in enumerate(raw)))
            point = curve.pointFromX(onb.fromCoords(x_bits))
            expected = curve.mul(point, 4) if point is not None else None
            if expected is not None:
                projected_bits = onb.toCoords(expected[0])
                formula.clauses.extend(([
                    bit if projected_bits >> position & 1 else -bit]
                    for position, bit in enumerate(projected)))
            with tempfile.TemporaryDirectory() as name:
                path = Path(name) / "projected-sparse.xcnf"
                formula.write(path)
                result = subprocess.run(["cryptominisat5", "--verb", "0",
                                         "--threads", "1", str(path)],
                                        capture_output=True, text=True,
                                        timeout=20)
            self.assertEqual(result.returncode, 10 if expected else 20,
                             (x_bits, result.stdout[-500:]))
            if expected is not None:
                values = parse_model(result.stdout)
                got = sum(1 << position for position, bit in
                          enumerate(projected) if values.get(bit, False))
                self.assertEqual(got, projected_bits)

    def test_cofactor_four_projection_identity(self):
        for n in (5, 11):
            onb = field.Onb(n)
            curve = curves.Curve(onb)
            for x_bits in range(1, 1 << n):
                x = onb.fromCoords(x_bits)
                inverse = onb.inv(x)
                point = curve.pointFromX(x)
                self.assertEqual(onb.trace(onb.add(x, inverse)) == 0,
                                 point is not None)
                if point is None:
                    continue
                projected = curve.mul(point, 4)
                x4 = onb.frob(x, 2)
                x8 = onb.frob(x, 3)
                x16 = onb.frob(x, 4)
                denominator = onb.add(onb.mul(x8, x4), x4)
                numerator = onb.add(onb.add(x16, x8), onb.one())
                if projected is None:
                    self.assertEqual(denominator, 0)
                else:
                    self.assertEqual(onb.mul(projected[0], denominator),
                                     numerator)

    def test_exact_s3_root_oracle_matches_group_sums(self):
        rng = random.Random(131718)
        for n in (5, 11):
            onb = field.Onb(n)
            curve = curves.Curve(onb)
            x_values = list(range(1, 1 << n))
            if n == 11:
                x_values = rng.sample(x_values, 80)
            rational = [curve.pointFromX(onb.fromCoords(x))
                        for x in x_values]
            rational = [point for point in rational if point is not None]
            if n == 5:
                pairs = ((i, j) for i in range(len(rational))
                         for j in range(len(rational)))
            else:
                pairs = ((rng.randrange(len(rational)),
                          rng.randrange(len(rational))) for _ in range(160))
            for i, j in pairs:
                a, b = rational[i], rational[j]
                roots = {onb.toCoords(root) for root in
                         s3_roots(onb, a[0], b[0])}
                group_x = set()
                for left in (a, curve.neg(a)):
                    for right in (b, curve.neg(b)):
                        total = curve.add(left, right)
                        if total is not None:
                            group_x.add(onb.toCoords(total[0]))
                self.assertEqual(roots, group_x)
            for x_bits in x_values[:100]:
                value = onb.fromCoords(x_bits)
                got = onb.add(onb.sqr(half_trace(onb, value)),
                              half_trace(onb, value))
                want = onb.add(value, onb.one() if onb.trace(value) else 0)
                self.assertEqual(got, want)

    def test_s3_root_oracle_contains_full_size_known_chains(self):
        for n, kind in ((53, "ordinary"), (83, "planted")):
            _, baseline, _, archive, _ = read_inputs(n, kind)
            onb = field.Onb(n)
            curve = curves.Curve(onb)
            _, points = witness_points(
                n, kind, onb, curve, baseline,
                int(archive["curve"]["cofactor"]))
            public = tuple(map(int, baseline["public_subgroup_target"]))
            first = curve.add(points[0], points[1])
            second = curve.add(first, points[2])
            self.assertEqual(curve.add(second, points[3]), public)
            for left, right, expected in (
                    (points[0], points[1], first),
                    (first, points[2], second),
                    (second, points[3], public)):
                roots = {onb.toCoords(root) for root in
                         s3_roots(onb, left[0], right[0])}
                self.assertIn(onb.toCoords(expected[0]), roots)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_half_trace_s3_root_circuit_selects_exact_roots(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        table = multiplication_table(onb)
        destinations = square_destinations(onb)
        columns = half_trace_columns(onb)
        rational_x = [x for x in range(1, 1 << 5)
                      if curve.pointFromX(onb.fromCoords(x)) is not None]
        pairs = [(a, b) for a in rational_x[:4]
                 for b in rational_x[4:8]]
        for a, b in pairs:
            observed = set()
            for branch_value in (0, 1):
                formula = Formula()
                left = [formula.new() for _ in range(5)]
                right = [formula.new() for _ in range(5)]
                root, branch = s3_root_link(
                    formula, left, right, table, destinations, columns)
                for variables, value in ((left, a), (right, b)):
                    formula.clauses.extend(([
                        bit if value >> position & 1 else -bit]
                        for position, bit in enumerate(variables)))
                formula.clauses.append([
                    branch if branch_value else -branch])
                with tempfile.TemporaryDirectory() as name:
                    path = Path(name) / "root-circuit.xcnf"
                    formula.write(path)
                    result = subprocess.run(["cryptominisat5", "--verb", "0",
                                             "--threads", "1", str(path)],
                                            capture_output=True, text=True,
                                            timeout=20)
                self.assertEqual(result.returncode, 10,
                                 (a, b, branch_value, result.stdout[-500:]))
                model = parse_model(result.stdout)
                observed.add(sum(1 << position for position, bit in
                                 enumerate(root) if model.get(bit, False)))
            expected = {onb.toCoords(value) for value in s3_roots(
                onb, onb.fromCoords(a), onb.fromCoords(b))}
            self.assertEqual(observed, expected)

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_full_group_addition_circuit_recovers_known_point_sum(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        table = multiplication_table(onb)
        destinations = square_destinations(onb)
        points = [curve.pointFromX(onb.fromCoords(x))
                  for x in range(1, 1 << 5)]
        points = [point for point in points if point is not None]
        rng = random.Random(132021)
        while True:
            chosen = [rng.choice(points) for _ in range(4)]
            first = curve.add(chosen[0], chosen[1])
            if first is None or chosen[0][0] == chosen[1][0]:
                continue
            second = curve.add(first, chosen[2])
            if second is None or first[0] == chosen[2][0]:
                continue
            target = curve.add(second, chosen[3])
            if target is not None and second[0] != chosen[3][0]:
                break
        formula = Formula()
        leaf_x = [[formula.new() for _ in range(5)] for _ in range(4)]
        leaves, mids, slopes = add_four_to_target(
            formula, leaf_x,
            tuple(onb.toCoords(value) for value in target),
            table, destinations)
        self.assertEqual(len(slopes), 3)
        for variables, point in zip(leaf_x, chosen):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(variables)))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "group-chain.xcnf"
            formula.write(path)
            result = subprocess.run(["cryptominisat5", "--verb", "0",
                                     "--threads", "1", str(path)],
                                    capture_output=True, text=True,
                                    timeout=20)
        self.assertEqual(result.returncode, 10, result.stdout[-500:])
        model = parse_model(result.stdout)
        decoded = []
        for x_bits, y_bits in leaves:
            x = sum(1 << position for position, bit in enumerate(x_bits)
                    if model.get(bit, False))
            y = sum(1 << position for position, bit in enumerate(y_bits)
                    if model.get(bit, False))
            point = (onb.fromCoords(x), onb.fromCoords(y))
            self.assertTrue(curve.onCurve(point))
            decoded.append(point)
        total = None
        for point in decoded:
            total = curve.add(total, point)
        self.assertEqual(total, target)

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
