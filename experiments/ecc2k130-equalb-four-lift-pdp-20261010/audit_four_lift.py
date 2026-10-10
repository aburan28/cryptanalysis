#!/usr/bin/env python3
"""Independently bind a four-lift formula to its bounded solver transcript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_four_lift as gate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=gate.POLICIES, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite an audit")
    built = json.loads(args.formula.with_suffix(".json").read_text())
    pilot = json.loads(args.pilot.read_text())
    stdout_path = args.pilot.with_suffix(".stdout.txt")
    stderr_path = args.pilot.with_suffix(".stderr.txt")
    output = stdout_path.read_text(errors="replace")
    progress = [line for line in output.splitlines()
                if ("conflict" in line.lower() or "restarts" in line.lower()
                    or line.startswith("s "))]
    if (built["policy"] != args.policy or pilot["policy"] != args.policy
            or built["formula_sha256"] != gate.ref.sha(args.formula)
            or pilot["formula_sha256"] != built["formula_sha256"]
            or pilot["formula_receipt_sha256"] != gate.ref.sha(
                args.formula.with_suffix(".json"))
            or built["target_x_choices"] != [str(x) for x in gate.target_lifts()]
            or pilot["stdout_sha256"] != gate.ref.sha(stdout_path)
            or pilot["stderr_sha256"] != gate.ref.sha(stderr_path)
            or pilot["search_progress_lines"] != len(progress)
            or pilot["runner_sha256"] != gate.ref.sha(gate.HERE / "run_four_lift.py")
            or pilot["threads"] != 1
            or pilot["solver_maxtime_seconds"] != 120
            or pilot["external_wall_cap_seconds"] != 150
            or pilot["rss_cap_bytes"] != 4*(1 << 30)):
        raise ValueError("source, input, formula, or transcript changed")
    terminal = [line for line in output.splitlines() if line.startswith("s ")]
    if pilot["status"] == "BOUNDED_UNKNOWN":
        if (not progress or pilot["guard"] != "WALL_CAP"
                or any("SATISFIABLE" in line for line in terminal)):
            raise ValueError("bounded status lacks live-search and guard evidence")
    elif pilot["status"] == "SAT_UNVERIFIED":
        if not any(line == "s SATISFIABLE" for line in terminal):
            raise ValueError("SAT status lacks solver declaration")
    elif pilot["status"] == "UNSAT":
        if not any(line == "s UNSATISFIABLE" for line in terminal):
            raise ValueError("UNSAT status lacks solver declaration")
    elif pilot["status"] not in ("OOM_GUARD", "PRODUCER_FAILURE"):
        raise ValueError("unknown solver outcome")
    result = {
        "schema": "ecc2k130-four-lift-solver-audit-v1",
        "status": "PASS_TRANSCRIPT_AND_SOURCE_BINDING",
        "policy": args.policy,
        "solver_status": pilot["status"],
        "formula_sha256": built["formula_sha256"],
        "pilot_sha256": gate.ref.sha(args.pilot),
        "stdout_sha256": gate.ref.sha(stdout_path),
        "stderr_sha256": gate.ref.sha(stderr_path),
        "search_progress_lines": len(progress),
        "terminal_lines": terminal,
        "audit_source_sha256": gate.ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "policy", "solver_status",
                       "search_progress_lines")}, sort_keys=True))


if __name__ == "__main__":
    main()
