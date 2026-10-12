#!/usr/bin/env python3
"""Independently bind exact selector formula and raw solver transcript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_selector as circuit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite audit")
    built = json.loads(args.formula.with_suffix(".json").read_text())
    pilot = json.loads(args.pilot.read_text())
    stdout_path = args.pilot.with_suffix(".stdout.txt")
    stderr_path = args.pilot.with_suffix(".stderr.txt")
    stdout = stdout_path.read_text(errors="replace")
    stderr = stderr_path.read_text(errors="replace")
    live = [line for line in stdout.splitlines()
            if line.lstrip().startswith("c rst")]
    if (built["formula_sha256"] != circuit.ref.sha(args.formula)
            or built["formula_sha256"] != pilot["formula_sha256"]
            or pilot["formula_receipt_sha256"]
            != circuit.ref.sha(args.formula.with_suffix(".json"))
            or pilot["stdout_sha256"] != circuit.ref.sha(stdout_path)
            or pilot["stderr_sha256"] != circuit.ref.sha(stderr_path)
            or pilot["runner_sha256"] != circuit.ref.sha(
                circuit.HERE / "run_pilot.py")
            or pilot["live_restart_rows"] != len(live)
            or pilot["last_live_restart_row"]
            != (live[-1] if live else None)):
        raise ValueError("formula, runner, or raw transcript changed")
    if pilot["status"] == "BOUNDED_UNKNOWN":
        if (pilot["guard"] != "WALL_CAP" or len(live) == 0
                or "s SATISFIABLE" in stdout
                or "s UNSATISFIABLE" in stdout):
            raise ValueError("censored search evidence is inconsistent")
    elif pilot["status"] == "SAT_UNVERIFIED":
        if "s SATISFIABLE" not in stdout or "s UNSATISFIABLE" in stdout:
            raise ValueError("SAT transcript is inconsistent")
    elif pilot["status"] == "UNSAT":
        if "s UNSATISFIABLE" not in stdout:
            raise ValueError("UNSAT transcript is inconsistent")
    else:
        raise ValueError("pilot status needs separate audit: " + pilot["status"])
    audit = {
        "schema": "ecc2k130-normal4-selector-pilot-audit-v1",
        "status": "PASS_TRANSCRIPT_AND_FORMULA_BINDING",
        "candidate_id": None,
        "policy": pilot["policy"],
        "solver_status": pilot["status"],
        "verified_relation": False,
        "novel_rank": None,
        "live_restart_rows": len(live),
        "last_live_restart_row": live[-1] if live else None,
        "formula_sha256": built["formula_sha256"],
        "pilot_sha256": circuit.ref.sha(args.pilot),
        "stdout_sha256": circuit.ref.sha(stdout_path),
        "stderr_sha256": circuit.ref.sha(stderr_path),
        "audit_source_sha256": circuit.ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: audit[key] for key in
                      ("policy", "solver_status", "live_restart_rows")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
