#!/usr/bin/env python3
"""Run pinned native-XOR leaf controls for both exact four-hot encodings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

import build_selector as circuit


HERE = Path(__file__).resolve().parent
EXPECTED_SOLVER_SHA = "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"


def pin_word(formula, variables: list[int], value: int) -> None:
    for bit, literal in enumerate(variables):
        formula.addClause([literal if value & (1 << bit) else -literal])


def one_control(policy: str, case: str, mask: int, path: Path) -> dict:
    formula, mapping = circuit.encode(policy, "leaf")
    basis = circuit.ref.words("normal4_source")
    selected = [bit for bit in range(131) if mask & (1 << bit)]
    if len(selected) != 4:
        raise ValueError("planted control is not four-hot")
    if policy == "counter":
        input_mask = mask
        if case == "count3":
            input_mask ^= 1 << selected[0]
        elif case == "count5":
            extra = next(bit for bit in range(131)
                         if not mask & (1 << bit))
            input_mask ^= 1 << extra
        pin_word(formula, mapping["masks"][0], input_mask)
        pins = {"mask": str(input_mask)}
    else:
        if case == "duplicate":
            selected[1] = selected[0]
        elif case == "reverse":
            selected[0], selected[1] = selected[1], selected[0]
        elif case == "out_of_range":
            selected[3] = 131
        for variables, value in zip(mapping["positions"][0], selected):
            pin_word(formula, variables, value)
        pins = {"positions": selected}
    x = circuit.ref.leaf_x(basis, mask) ^ int(case == "changed_x")
    z = circuit.ref.inverse(circuit.ref.parameter(basis, mask))
    pin_word(formula, mapping["coordinates"][0]["x"], x)
    pin_word(formula, mapping["coordinates"][0]["z"], z)
    formula.writeDimacs(path)
    return {"pin_recipe": pins, "pinned_x": str(x), "pinned_z": str(z),
            "stats": formula.stats(), "formula_sha256": circuit.ref.sha(path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("refusing to overwrite control directory")
    sage_path = HERE / "runs/R1/sage_selector.json"
    sage = json.loads(sage_path.read_text())
    if sage["status"] != "PASS_128_POINTS_SUPPORT_BIJECTION_AND_BALANCED_TREE":
        raise ValueError("independent Sage selector control not verified")
    mask = int(sage["planted_selectors"][0])
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if circuit.ref.sha(solver) != EXPECTED_SOLVER_SHA:
        raise ValueError("solver binary changed")
    cases = {"counter": ("positive", "high_index", "changed_x",
                         "count3", "count5"),
             "support_index": ("positive", "high_index", "changed_x",
                               "duplicate", "reverse", "out_of_range")}
    args.out_dir.mkdir(parents=True)
    rows = []
    for policy, names in cases.items():
        for case in names:
            label = policy + "_" + case
            path = args.out_dir / (label + ".xcnf")
            current_mask = (int(sage["high_position_control"]["mask"])
                            if case == "high_index" else mask)
            record = one_control(policy, case, current_mask, path)
            command = [str(solver), "--threads=1", "--maxtime=20",
                       "--verb=0", "--printsol=0", str(path)]
            started = time.perf_counter()
            process = subprocess.run(command, text=True, capture_output=True,
                                     timeout=30, check=False)
            stdout = args.out_dir / (label + ".stdout.txt")
            stderr = args.out_dir / (label + ".stderr.txt")
            stdout.write_text(process.stdout)
            stderr.write_text(process.stderr)
            observed = ("UNSAT" if "s UNSATISFIABLE" in process.stdout else
                        "SAT" if "s SATISFIABLE" in process.stdout else
                        "UNKNOWN")
            expected = "SAT" if case in ("positive", "high_index") else "UNSAT"
            row = {"policy": policy, "case": case, "expected": expected,
                   "observed": observed, "mask": str(current_mask),
                   "command": command, "exit_code": process.returncode,
                   "wall_seconds": time.perf_counter() - started,
                   "stdout_sha256": circuit.ref.sha(stdout),
                   "stderr_sha256": circuit.ref.sha(stderr), **record}
            rows.append(row)
            if observed != expected:
                raise ArithmeticError("native-XOR control failed: " + label)
    receipt = {
        "schema": "ecc2k130-normal4-selector-cnf-controls-v1",
        "status": "PASS_PINNED_ELEVEN_NATIVE_XOR_CONTROLS",
        "candidate_id": None,
        "solver_sha256": circuit.ref.sha(solver),
        "sage_selector_sha256": circuit.ref.sha(sage_path),
        "source_hashes": {name: circuit.ref.sha(HERE / name)
                          for name in ("build_selector.py", "check_cnf_controls.py")},
        "results": rows,
    }
    (args.out_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "controls": len(rows)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
