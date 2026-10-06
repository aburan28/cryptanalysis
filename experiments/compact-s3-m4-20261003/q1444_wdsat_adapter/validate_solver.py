#!/usr/bin/env python3
"""Check patched WDSat on exhaustive tiny CNF/XOR SAT and UNSAT cases."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from verify_factor_xcnf import count_violations, read_formula


HERE = Path(__file__).resolve().parent
CASES = {
    "cnf3_sat": ("p cnf 3 3\n1 2 3 0\n-1 0\n-2 0\n", True),
    "cnf3_unsat": ("p cnf 3 4\n1 2 3 0\n-1 0\n-2 0\n-3 0\n", False),
    "xor_sat": ("p cnf 3 3\n1 0\n2 0\nx 1 2 3 0\n", True),
    "xor_unsat": ("p cnf 2 2\n-1 0\nx 1 0\n", False),
    "cnf4_sat": ("p cnf 4 4\n1 2 3 4 0\n-1 0\n-2 0\n-3 0\n", True),
    "cnf4_unsat": ("p cnf 4 5\n1 0\n-1 2 3 4 0\n-2 0\n-3 0\n-4 0\n", False),
    "nonunit_unsat": ("p cnf 2 4\n1 2 0\n-1 2 0\n1 -2 0\n-1 -2 0\n", False),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(binary53, binary83):
    outcomes = []
    with tempfile.TemporaryDirectory() as temp:
        for name, (formula, declared_sat) in CASES.items():
            path = Path(temp) / f"{name}.xcnf"
            path.write_text(formula, encoding="ascii")
            nvars, rows = read_formula(path)
            expected_sat = any(count_violations(rows, {
                j: bool(mask >> (j - 1) & 1) for j in range(1, nvars + 1)
            }) == (0, 0) for mask in range(1 << nvars))
            assert expected_sat == declared_sat
            binary = binary83 if name.startswith("cnf4") else binary53
            cp = subprocess.run([str(binary), "-i", str(path)],
                                capture_output=True, text=True, timeout=5)
            models = [line for line in cp.stdout.splitlines()
                      if len(line) == nvars and set(line) <= {"0", "1"}]
            if expected_sat:
                assert len(models) == 1 and "UNSAT" not in cp.stdout
                assignment = {j: bit == "1" for j, bit in enumerate(models[0], 1)}
                assert count_violations(rows, assignment) == (0, 0)
            else:
                assert "UNSAT" in cp.stdout and not models
            outcomes.append({"case": name, "expected_sat": expected_sat,
                             "solver_model_verified": expected_sat,
                             "solver_reported_unsat": not expected_sat})
    return {"status": "pass", "cases": outcomes,
            "n53_binary_sha256": sha(binary53),
            "n83_binary_sha256": sha(binary83)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary53", type=Path, required=True)
    parser.add_argument("--binary83", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = validate(args.binary53, args.binary83)
    path = HERE / "solver_validation.json"
    if args.check:
        assert json.loads(path.read_text()) == result
    else:
        assert not path.exists(), "refuse to overwrite validation"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
