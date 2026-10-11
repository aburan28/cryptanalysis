#!/usr/bin/env python3
"""Check Karatsuba arithmetic against ONB multiplication and pinned XCNF."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))

import field  # noqa: E402
from chain_s3 import Formula  # noqa: E402
from karatsuba_circuit import (field_product, karatsuba_bits, reduce_bits,
                               xor_images)  # noqa: E402

CMS = Path("/opt/homebrew/bin/cryptominisat5")
OUTPUT = HERE / "circuit_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(formula: Formula, bits: list[int], value: int) -> None:
    for position, literal in enumerate(bits):
        formula.clauses.append([literal if (value >> position) & 1
                                else -literal])


def solver_status(formula: Formula) -> str:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "multiply.xcnf"
        formula.write(path)
        completed = subprocess.run(
            [str(CMS), "--threads", "1", "--maxtime", "10", str(path)],
            capture_output=True, text=True, timeout=15)
    statuses = [line for line in completed.stdout.splitlines()
                if line.startswith("s ")]
    assert len(statuses) == 1, (completed.returncode, statuses,
                                completed.stderr)
    return statuses[0]


def validate(n: int) -> dict:
    bridge_path = PARENT / "field_bridges" / f"n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    assert bridge["status"] == "PASS"
    assert bridge["field_degree"] == n
    assert bridge["isogeny"] == "none"
    onb = field.Onb(n)
    forward = bridge["onb_to_poly_basis_images"]
    inverse = bridge["poly_to_onb_basis_images"]
    low_terms = bridge["target_implementation_basis"]["low_terms"]
    padded = 1 << (n - 1).bit_length()
    rng = random.Random(1497 * n)
    trials = [(1 << i, 1 << j) for i in range(n) for j in range(n)]
    trials += [(rng.getrandbits(n), rng.getrandbits(n))
               for _ in range(128)]
    for left, right in trials:
        actual = onb.toCoords(onb.mul(onb.fromCoords(left),
                                      onb.fromCoords(right)))
        polynomial = karatsuba_bits(xor_images(left, forward),
                                    xor_images(right, forward), padded)
        result = xor_images(reduce_bits(polynomial, n, low_terms), inverse)
        assert result == actual, (n, left, right, result, actual)

    # Input pins force every gate. The correct product is SAT; changing one
    # output bit is UNSAT, which checks the emitted XOR/CNF semantics.
    pin_results = []
    for _ in range(2):
        left, right = rng.getrandbits(n), rng.getrandbits(n)
        expected = onb.toCoords(onb.mul(onb.fromCoords(left),
                                         onb.fromCoords(right)))
        formula = Formula()
        left_bits = [formula.new() for _ in range(n)]
        right_bits = [formula.new() for _ in range(n)]
        output_bits = field_product(formula, left_bits, right_bits, bridge)
        pin(formula, left_bits, left)
        pin(formula, right_bits, right)
        pin(formula, output_bits, expected)
        assert solver_status(formula) == "s SATISFIABLE"
        formula.clauses.append([(-output_bits[0] if expected & 1 else
                                 output_bits[0])])
        assert solver_status(formula) == "s UNSATISFIABLE"
        pin_results.append({"variables": formula.variables,
                            "cnf_clauses": len(formula.clauses),
                            "xor_rows": len(formula.xors),
                            "and_gates": len(formula.and_cache)})
    return {
        "kind": "q1497_karatsuba_same_field_circuit_validation",
        "status": "PASS", "degree_n": n,
        "curve_id": bridge["curve_id"], "isogeny": "none",
        "bridge_sha256": sha(bridge_path),
        "basis_pair_cases": n * n, "random_arithmetic_cases": 128,
        "pinned_sat_and_wrong_output_unsat_cases": 2,
        "single_product_formula_sizes": pin_results,
        "circuit_source_sha256": sha(HERE / "karatsuba_circuit.py"),
        "validation_source_sha256": sha(Path(__file__)),
        "cms_binary_sha256": sha(CMS),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = {"proposal_id": "Q1497", "candidate_id": None,
              "run_id": None, "isogeny": "none",
              "cases": [validate(n) for n in (53, 83)]}
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1497 Karatsuba circuit validation PASS (archived)")
    else:
        assert not OUTPUT.exists(), "refusing to replace validation"
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1497 Karatsuba circuit validation written")


if __name__ == "__main__":
    main()
