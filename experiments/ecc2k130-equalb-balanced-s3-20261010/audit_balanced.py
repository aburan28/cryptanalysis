#!/usr/bin/env python3
"""Bind a balanced-S3 XCNF to its raw native-XOR solver transcript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import build_balanced as balanced
import archive_formulas  # noqa: E402; balanced adds the parent experiment path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=balanced.POLICIES, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite independent audit")
    if args.formula.name.endswith(".xcnf.gz"):
        built_path = args.formula.with_suffix("").with_suffix(".json")
        formula_sha, _ = archive_formulas.decompressed_sha(args.formula)
    else:
        built_path = args.formula.with_suffix(".json")
        formula_sha = balanced.ref.sha(args.formula)
    built = json.loads(built_path.read_text())
    pilot = json.loads(args.pilot.read_text())
    stdout_path = args.pilot.with_suffix(".stdout.txt")
    stderr_path = args.pilot.with_suffix(".stderr.txt")
    output = stdout_path.read_text(errors="replace")
    progress = [line for line in output.splitlines()
                if ("conflict" in line.lower() or "restarts" in line.lower()
                    or line.startswith("s "))]
    # CryptoMiniSat prints live search as "c rst ... <restarts> <conflicts>".
    # The frozen pilot runner only counted spelled-out summary lines; external
    # termination can leave that count zero even after substantial search.
    restart_rows = []
    for line in output.splitlines():
        words = line.split()
        if (len(words) >= 7 and words[:2] == ["c", "rst"]
                and words[5].isdigit()
                and re.fullmatch(r"\d+(?:\.\d+)?[KMG]?", words[6])):
            restart_rows.append((int(words[5]), words[6]))
    if (built["schema"] != "ecc2k130-equalb-balanced-s3-m6-xcnf-v1"
            or built["policy"] != args.policy or pilot["policy"] != args.policy
            or built["formula_sha256"] != formula_sha
            or pilot["formula_sha256"] != formula_sha
            or pilot["formula_receipt_sha256"] != balanced.ref.sha(built_path)
            or built["target_x_choices"] != [
                str(x) for x in balanced.gate.target_lifts()]
            or pilot["stdout_sha256"] != balanced.ref.sha(stdout_path)
            or pilot["stderr_sha256"] != balanced.ref.sha(stderr_path)
            or pilot["search_progress_lines"] != len(progress)
            or pilot["runner_sha256"] != balanced.ref.sha(
                balanced.HERE / "run_balanced.py")
            or pilot["threads"] != 1
            or pilot["solver_maxtime_seconds"] != 120
            or pilot["external_wall_cap_seconds"] != 150
            or pilot["rss_cap_bytes"] != 4*(1 << 30)):
        raise ValueError("source, input, formula, or transcript changed")
    terminal = [line for line in output.splitlines() if line.startswith("s ")]
    conflicts = [int(value) for value in re.findall(
        r"^c conflicts\s*:\s*(\d+)", output, flags=re.MULTILINE)]
    restarts = [int(value) for value in re.findall(
        r"^c restarts\s*:\s*(\d+)", output, flags=re.MULTILINE)]
    if pilot["status"] == "BOUNDED_UNKNOWN":
        guarded = pilot["guard"] == "WALL_CAP"
        internal_timeout = (pilot["guard"] is None
                            and pilot["exit_code"] == 15
                            and "s INDETERMINATE" in terminal)
        live_search = (restart_rows and restart_rows[-1][0] > 0
                       or conflicts and max(conflicts) > 0
                       and restarts and max(restarts) > 0)
        if (not live_search
                or not (guarded or internal_timeout)
                or any("SATISFIABLE" in line for line in terminal)):
            raise ValueError("bounded status lacks search and timeout evidence")
    elif pilot["status"] == "SAT_UNVERIFIED":
        if not any(line == "s SATISFIABLE" for line in terminal):
            raise ValueError("SAT status lacks solver declaration")
    elif pilot["status"] == "UNSAT":
        if not any(line == "s UNSATISFIABLE" for line in terminal):
            raise ValueError("UNSAT status lacks solver declaration")
    elif pilot["status"] not in ("OOM_GUARD", "PRODUCER_FAILURE"):
        raise ValueError("unknown solver outcome")
    result = {
        "schema": "ecc2k130-balanced-s3-solver-audit-v1",
        "status": "PASS_TRANSCRIPT_AND_SOURCE_BINDING",
        "policy": args.policy,
        "solver_status": pilot["status"],
        "formula_sha256": formula_sha,
        "pilot_sha256": balanced.ref.sha(args.pilot),
        "stdout_sha256": balanced.ref.sha(stdout_path),
        "stderr_sha256": balanced.ref.sha(stderr_path),
        "search_progress_lines": len(progress),
        "live_restart_rows": len(restart_rows),
        "last_live_restart_count": restart_rows[-1][0] if restart_rows else None,
        "last_live_conflict_display": restart_rows[-1][1]
        if restart_rows else None,
        "exact_terminal_conflicts": max(conflicts) if conflicts else None,
        "exact_terminal_restarts": max(restarts) if restarts else None,
        "terminal_lines": terminal,
        "audit_source_sha256": balanced.ref.sha(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "policy", "solver_status",
                       "search_progress_lines")}, sort_keys=True))


if __name__ == "__main__":
    main()
