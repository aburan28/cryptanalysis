#!/usr/bin/env python3
"""Check positive and one-bit-negative exact leaves in native-XOR SAT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

import build_formula as circuit
import field as ref


HERE = Path(__file__).resolve().parent
EXPECTED_SOLVER_SHA = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"


def one_control(policy: str, mask: int, changed_x: bool, path: Path):
    prog, roots, leaves, chain = circuit.build_ir(policy, "leaf", None)
    formula, selectors = circuit.encode(prog, roots, leaves, chain, policy, None)
    width = len(selectors[0])
    expected_selectors = list(range(2, 2 + width))
    if selectors[0] != expected_selectors:
        raise ArithmeticError("input variable layout changed")
    basis = ref.words(policy)
    w = ref.parameter(basis, mask)
    z = ref.inverse(w)
    x = ref.leaf_x(basis, mask) ^ int(changed_x)
    x_vars = list(range(2 + width, 2 + width + 131))
    z_vars = list(range(2 + width + 131, 2 + width + 262))
    for variables, value in ((selectors[0], mask), (x_vars, x), (z_vars, z)):
        for bit, variable in enumerate(variables):
            formula.addClause([variable if value & (1 << bit) else -variable])
    formula.writeDimacs(path)
    return formula.stats()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir
    if out.exists():
        parser.error("refusing to overwrite control directory")
    out.mkdir(parents=True)
    verifier = json.loads((HERE / "runs/R1/sage_verification.json").read_text())
    if verifier["status"] != "PASS_SAGE_POINT_AND_BOOLEAN_REPLAY":
        raise ValueError("Sage planted control not verified")
    binary = Path(shutil.which("cryptominisat5") or "").resolve()
    if ref.sha(binary) != EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed")
    results = []
    for policy in ("w24_source", "normal4_source"):
        mask = int(verifier["planted"][policy]["selectors"][0])
        for changed_x, expected in ((False, "SAT"), (True, "UNSAT")):
            label = policy + ("_negative" if changed_x else "_positive")
            formula = out / (label + ".xcnf")
            stats = one_control(policy, mask, changed_x, formula)
            command = [str(binary), "--threads=1", "--maxtime=20",
                       "--verb=0", "--printsol=0", str(formula)]
            started = time.perf_counter()
            try:
                process = subprocess.run(command, text=True, capture_output=True,
                                         timeout=30, check=False)
                output = process.stdout
                stderr = process.stderr
                exit_code = process.returncode
            except subprocess.TimeoutExpired as error:
                raise TimeoutError("pinned control did not finish: " + label) from error
            observed = ("UNSAT" if "s UNSATISFIABLE" in output else
                        "SAT" if "s SATISFIABLE" in output else "UNKNOWN")
            stdout = out / (label + ".stdout.txt")
            stderr_path = out / (label + ".stderr.txt")
            stdout.write_text(output)
            stderr_path.write_text(stderr)
            if observed != expected:
                raise ArithmeticError("pinned control %s: %s, expected %s" %
                                      (label, observed, expected))
            results.append({
                "policy": policy,
                "mask": str(mask),
                "changed_x_bit_0": changed_x,
                "expected": expected,
                "observed": observed,
                "formula_sha256": ref.sha(formula),
                "stdout_sha256": ref.sha(stdout),
                "stderr_sha256": ref.sha(stderr_path),
                "stats": stats,
                "exit_code": exit_code,
                "wall_seconds": time.perf_counter() - started,
            })
    receipt = {
        "schema": "ecc2k130-equalb-leaf-cnf-controls-v1",
        "status": "PASS_PINNED_POSITIVE_AND_NEGATIVE",
        "candidate_id": None,
        "solver_sha256": ref.sha(binary),
        "sage_verification_sha256": ref.sha(HERE / "runs/R1/sage_verification.json"),
        "results": results,
    }
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "controls": len(results)}, sort_keys=True))


if __name__ == "__main__":
    main()
