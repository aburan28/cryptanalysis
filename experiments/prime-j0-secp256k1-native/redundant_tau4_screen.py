#!/usr/bin/env python3
"""Screen two unit-orbit representatives per tau^4 class on frozen scalars."""

import argparse
from collections import defaultdict
from functools import cache
import hashlib
import json
from pathlib import Path
import random
import subprocess

import lazy_tau_screen as curve
from check_eisenstein_scalar_fixed import LAMBDA_TAU, affine_from_native


HERE = Path(__file__).resolve().parent
# One representative for each of the nine six-class unit orbits.
PRIMARY = ((-1, 0), (-2, 0), (-1, -1), (-1, 2), (-2, -1),
           (-2, 3), (-4, 0), (-1, -2), (-1, 3))
# A second representative in the same respective residue orbit.
ALTERNATE = ((8, 0), (7, 0), (8, -1), (8, -7), (7, -1),
             (7, -6), (5, 0), (8, -2), (8, -6))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(z):
    a, b = z
    return a * a + 3 * a * b + 3 * b * b


def omega(z):
    a, b = z
    return a + 3 * b, -a - 2 * b


def tau(z):
    a, b = z
    return -3 * b, a + 3 * b


def orbit(seed):
    result = []
    for _ in range(3):
        result += [seed, (-seed[0], -seed[1])]
        seed = omega(seed)
    assert len(set(result)) == 6
    return result


def digit_table():
    table = defaultdict(list)
    for primary, alternate in zip(PRIMARY, ALTERNATE):
        assert (primary[0] % 9, primary[1] % 9) == (
            alternate[0] % 9, alternate[1] % 9)
        for seed in (primary, alternate):
            for digit in orbit(seed):
                table[(digit[0] % 9, digit[1] % 9)].append(digit)
    assert len(table) == 54 and all(len(digits) == 2 for digits in table.values())
    assert all(a % 3 for a, _ in table)
    assert {norm(d) for digits in table.values() for d in digits} <= {
        1, 4, 7, 13, 16, 19, 25, 28, 31, 43, 49, 64}
    return dict(table)


def zero_quotient(z):
    a, b = z
    assert a % 3 == 0
    result = a + b, -a // 3
    assert tau(result) == z and norm(result) * 3 == norm(z)
    return result


def block_quotient(z, digit):
    a, b = z[0] - digit[0], z[1] - digit[1]
    assert a % 9 == 0 and b % 9 == 0
    result = omega((a // 9, b // 9))
    assert (9 * (-2 * result[0] - 3 * result[1]),
            9 * (result[0] + result[1])) == (a, b)
    assert norm(result) * 81 == norm((a, b))
    assert norm(result) < norm(z), (z, digit, result)
    return result


class Policy:
    def __init__(self, table, dual_terminal):
        self.table = table
        self.terminal = ({(0, 0)} | {
            digit for digits in table.values()
            for digit in (digits if dual_terminal else digits[:1])})

    @cache
    def base_value(self, z):
        if z in self.terminal:
            return 0
        if z[0] % 3 == 0:
            return 5 + self.base_value(zero_quotient(z))
        digit = self.table[(z[0] % 9, z[1] % 9)][0]
        return 31 + self.base_value(block_quotient(z, digit))

    @cache
    def look_value(self, z, horizon):
        if horizon == 0 or z in self.terminal:
            return self.base_value(z)
        if z[0] % 3 == 0:
            return 5 + self.look_value(zero_quotient(z), horizon)
        return 31 + min(self.look_value(block_quotient(z, digit), horizon - 1)
                        for digit in self.table[(z[0] % 9, z[1] % 9)])

    @cache
    def optimal_value(self, z):
        if z in self.terminal:
            return 0
        if z[0] % 3 == 0:
            return 5 + self.optimal_value(zero_quotient(z))
        return 31 + min(self.optimal_value(block_quotient(z, digit))
                        for digit in self.table[(z[0] % 9, z[1] % 9)])

    def recode(self, start, horizon=None):
        z = start
        actions = []
        steps = additions = alternate_uses = 0
        while z not in self.terminal:
            if z[0] % 3 == 0:
                actions.append((1, (0, 0)))
                z = zero_quotient(z)
                steps += 1
            else:
                choices = self.table[(z[0] % 9, z[1] % 9)]
                if horizon is None:
                    index = min(range(len(choices)), key=lambda i: (
                        self.optimal_value(block_quotient(z, choices[i])), i))
                elif horizon == 0:
                    index = 0
                else:
                    index = min(range(len(choices)), key=lambda i: (
                        self.look_value(block_quotient(z, choices[i]), horizon - 1), i))
                digit = choices[index]
                actions.append((4, digit))
                z = block_quotient(z, digit)
                steps += 4
                additions += 1
                alternate_uses += index == 1
            assert steps <= 512
        rebuilt = z
        for width, digit in reversed(actions):
            rebuilt = tau(rebuilt) if width == 1 else (
                9 * (-2 * rebuilt[0] - 3 * rebuilt[1]) + digit[0],
                9 * (rebuilt[0] + rebuilt[1]) + digit[1])
        assert rebuilt == start
        cost = 5 * steps + 11 * additions
        if horizon is None:
            assert cost == self.optimal_value(start)
        elif horizon == 0:
            assert cost == self.base_value(start)
        return {"tau_steps": steps, "additions": additions,
                "alternate_uses": alternate_uses, "field_product_proxy": cost}


def native_representatives(binary, scalars):
    request = "".join(format(scalar, "x") + "\n" for scalar in scalars)
    process = subprocess.run(
        [str(binary), "--scalar-w3-fixed"], input=request, text=True,
        capture_output=True, check=True, timeout=120)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    result = []
    for scalar, row in zip(scalars, rows):
        a, b = map(int, row["representative"])
        assert (a + b * LAMBDA_TAU - scalar) % curve.ORDER == 0
        assert affine_from_native(row["point"]) == curve.point_multiply(scalar % curve.ORDER)
        result.append((a, b))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    parser.add_argument("--fixture", type=Path,
                        default=HERE / "eisenstein-pair-fixture.json")
    parser.add_argument("--output", type=Path,
                        default=HERE / "redundant-tau4-result.json")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    fixture_path = args.fixture.resolve(strict=True)
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 86
    assert all(not row["expected_identity"] for row in fixture["cases"])
    rng = random.Random(20261013)
    scalars = [int(row["scalar_hex"], 16) for row in fixture["cases"]]
    scalars += [rng.randrange(1, curve.ORDER) for _ in range(128)]
    representatives = native_representatives(binary, scalars)
    table = digit_table()
    single = Policy(table, dual_terminal=False)
    dual = Policy(table, dual_terminal=True)
    paths = ("single", "dual_base", "rollout_1", "rollout_2", "rollout_3",
             "optimal_field_proxy")
    panels = ("frozen_edges", "frozen_random", "holdout_random")
    totals = {panel: {path: 0 for path in paths} for panel in panels}
    rows = []
    for index, (scalar, representative) in enumerate(zip(scalars, representatives)):
        panel = panels[0 if index < 22 else 1 if index < 86 else 2]
        results = {
            "single": single.recode(representative, horizon=0),
            "dual_base": dual.recode(representative, horizon=0),
            "rollout_1": dual.recode(representative, horizon=1),
            "rollout_2": dual.recode(representative, horizon=2),
            "rollout_3": dual.recode(representative, horizon=3),
            "optimal_field_proxy": dual.recode(representative, horizon=None),
        }
        for name, result in results.items():
            totals[panel][name] += result["field_product_proxy"]
        assert (results["optimal_field_proxy"]["field_product_proxy"]
                <= results["rollout_3"]["field_product_proxy"]
                <= results["dual_base"]["field_product_proxy"])
        rows.append({"index": index, "panel": panel,
                     "scalar_hex": format(scalar, "x"),
                     "representative": list(representative),
                     "policies": results})
    output = {
        "schema": 1, "status": "passed",
        "curve": "secp256k1", "base": "standard-generator",
        "algorithm": "dual-orbit-tau4-bounded-rollout",
        "design_seed": 20261009, "holdout_seed": 20261013,
        "primary_seeds": PRIMARY, "alternate_seeds": ALTERNATE,
        "frozen_cases": 86, "holdout_cases": 128,
        "digit_residue_classes": len(table),
        "max_digit_norm": max(norm(d) for digits in table.values() for d in digits),
        "timing_status": "source-operation-screen",
        "totals": totals, "cases": rows,
        "cache_states": {
            "single_base": single.base_value.cache_info().currsize,
            "dual_base": dual.base_value.cache_info().currsize,
            "dual_look": dual.look_value.cache_info().currsize,
            "dual_optimal": dual.optimal_value.cache_info().currsize,
        },
        "binary_sha256": sha(binary), "fixture_sha256": sha(fixture_path),
        "source_sha256": sha(Path(__file__)),
        "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py"),
        "field_reference_sha256": sha(HERE / "eisenstein_montgomery.py"),
    }
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": output["status"], "cases": len(rows),
                      "totals": totals, "result_sha256": sha(args.output)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
