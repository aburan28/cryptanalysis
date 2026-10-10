#!/usr/bin/env python3
"""Check every Q1420 source/native target choice in the actual XOR encoder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import build_formula as circuit
import field as ref


EXPECTED_SOLVER_SHA = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"


def solve_status(output):
    if "s SATISFIABLE" in output and "s UNSATISFIABLE" not in output:
        return "SAT"
    if "s UNSATISFIABLE" in output:
        return "UNSAT"
    return "UNKNOWN"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("refusing to overwrite target mux controls")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    args.out_dir.mkdir(parents=True)
    results = {}
    for policy in circuit.POLICIES:
        xs = circuit.target_lifts(policy)
        cases = []
        for choice in range(4):
            for altered in (False, True):
                formula = circuit.cnf.Cnf()
                target_bits, selectors = circuit.target_mux(formula, xs)
                for bit, literal in enumerate(selectors):
                    formula.addClause([literal if choice & (1 << bit)
                                       else -literal])
                expected = xs[choice] ^ int(altered)
                for bit, literal in enumerate(target_bits):
                    formula.addClause([literal if expected & (1 << bit)
                                       else -literal])
                name = "%s_j%d_%s" % (
                    policy, choice, "xbit0_changed" if altered else "exact")
                path = args.out_dir / (name + ".xcnf")
                formula.writeDimacs(path)
                run = subprocess.run(
                    [str(solver), "--threads=1", "--maxtime=10", "--verb=0",
                     str(path)], text=True, capture_output=True,
                    timeout=15, check=False)
                stdout = args.out_dir / (name + ".stdout.txt")
                stderr = args.out_dir / (name + ".stderr.txt")
                stdout.write_text(run.stdout)
                stderr.write_text(run.stderr)
                actual = solve_status(run.stdout)
                wanted = "UNSAT" if altered else "SAT"
                if actual != wanted:
                    raise AssertionError("target mux %s returned %s" %
                                         (name, actual))
                cases.append({"choice": choice,
                              "changed_x_bit_zero": altered,
                              "expected_x": str(expected),
                              "status": actual,
                              "formula_sha256": ref.sha(path),
                              "stdout_sha256": ref.sha(stdout),
                              "stderr_sha256": ref.sha(stderr),
                              "exit_code": run.returncode,
                              "stats": formula.stats()})
        results[policy] = {"target_x_choices": [str(x) for x in xs],
                           "cases": cases}
    receipt = {
        "schema": "ecc2k130-263-native-w24-target-mux-controls-v1",
        "status": "PASS_EIGHT_POSITIVE_EIGHT_NEGATIVE_XOR_CONTROLS",
        "primary_workload_id": ref.read(ref.HERE / "CONFIG.json")[
            "primary_workload_id"],
        "policies": results,
        "solver_sha256": ref.sha(solver),
        "solver_version": version,
        "builder_sha256": ref.sha(ref.HERE / "build_formula.py"),
        "source_sha256": ref.sha(Path(__file__)),
        "lifts_sha256": ref.sha(ref.HERE / "runs/R1/lifts.json"),
    }
    (args.out_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": receipt["status"],
                      "cases": sum(len(row["cases"]) for row in results.values())},
                     sort_keys=True))


if __name__ == "__main__":
    main()
