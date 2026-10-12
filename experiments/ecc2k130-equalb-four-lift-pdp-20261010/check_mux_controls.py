#!/usr/bin/env python3
"""Independently pin all four target-mux choices in native-XOR CNF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import build_four_lift as circuit


EXPECTED_SOLVER_SHA = (
    "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
)


def status(output: str) -> str:
    if "s SATISFIABLE" in output and "s UNSATISFIABLE" not in output:
        return "SAT"
    if "s UNSATISFIABLE" in output:
        return "UNSAT"
    return "UNKNOWN"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("refusing to overwrite target-mux controls")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if circuit.ref.sha(solver) != EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    xs = circuit.target_lifts()
    args.out_dir.mkdir(parents=True)
    cases = []
    for choice in range(4):
        for altered in (False, True):
            formula = circuit.source.cnf.Cnf()
            target_bits, selectors = circuit.encode_target_mux(formula, xs)
            for bit, literal in enumerate(selectors):
                formula.addClause([literal if choice & (1 << bit) else -literal])
            expected = xs[choice] ^ int(altered)
            for bit, literal in enumerate(target_bits):
                formula.addClause([literal if expected & (1 << bit) else -literal])
            name = "j%d_%s" % (choice, "xbit0_changed" if altered else "exact")
            path = args.out_dir / (name + ".xcnf")
            formula.writeDimacs(path)
            run = subprocess.run([str(solver), "--threads=1", "--maxtime=10",
                                  "--verb=0", str(path)], text=True,
                                 capture_output=True, timeout=15, check=False)
            stdout = args.out_dir / (name + ".stdout.txt")
            stderr = args.out_dir / (name + ".stderr.txt")
            stdout.write_text(run.stdout)
            stderr.write_text(run.stderr)
            actual = status(run.stdout)
            wanted = "UNSAT" if altered else "SAT"
            if actual != wanted:
                raise AssertionError("target mux %s gave %s, expected %s" %
                                     (name, actual, wanted))
            cases.append({
                "choice": choice, "changed_x_bit_zero": altered,
                "expected_x": str(expected), "status": actual,
                "formula_sha256": circuit.ref.sha(path),
                "stdout_sha256": circuit.ref.sha(stdout),
                "stderr_sha256": circuit.ref.sha(stderr),
                "exit_code": run.returncode, "stats": formula.stats(),
            })
    receipt = {
        "schema": "ecc2k130-four-lift-target-mux-controls-v1",
        "status": "PASS_FOUR_POSITIVE_FOUR_NEGATIVE_NATIVE_XOR_CONTROLS",
        "target_x_choices": [str(x) for x in xs],
        "cases": cases,
        "solver_sha256": circuit.ref.sha(solver),
        "solver_version": version,
        "builder_sha256": circuit.ref.sha(circuit.HERE / "build_four_lift.py"),
        "control_source_sha256": circuit.ref.sha(Path(__file__)),
        "parent_torsion_lifts_sha256": circuit.ref.sha(circuit.LIFTS),
    }
    (args.out_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "cases": len(cases)}, sort_keys=True))


if __name__ == "__main__":
    main()
