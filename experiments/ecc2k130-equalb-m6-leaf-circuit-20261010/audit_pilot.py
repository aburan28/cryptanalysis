#!/usr/bin/env python3
"""Independently classify a bounded native-XOR solver transcript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import field as ref


def audit(receipt_path: Path) -> dict:
    receipt = json.loads(receipt_path.read_text())
    stem = receipt_path.with_suffix("")
    stdout_path = Path(str(stem) + ".stdout.txt")
    stderr_path = Path(str(stem) + ".stderr.txt")
    for name, path in (("stdout", stdout_path), ("stderr", stderr_path)):
        if ref.sha(path) != receipt[name + "_sha256"]:
            raise ValueError("solver %s hash changed" % name)
    output = stdout_path.read_text(errors="replace")
    error = stderr_path.read_text(errors="replace")
    lines = output.splitlines()
    progress = [line for line in lines if line.startswith("c rst ")]
    finals = [line for line in lines if line.startswith("s ")]
    starts = [line for line in lines if ("Reading file" in line
               or "reading file" in line or "clauses" in line.lower())]
    if receipt["status"] == "BOUNDED_UNKNOWN":
        if receipt["guard"] not in ("WALL_CAP", "RSS_CAP"):
            raise ValueError("bounded result lacks a matching guard")
        if any("UNSATISFIABLE" in line or "SATISFIABLE" in line
               for line in finals):
            raise ValueError("bounded receipt hid a solver conclusion")
    if receipt["status"] == "UNSAT" and "s UNSATISFIABLE" not in finals:
        raise ValueError("UNSAT lacks solver certificate status")
    if receipt["status"] == "SAT_UNVERIFIED" and "s SATISFIABLE" not in finals:
        raise ValueError("SAT lacks solver status")
    if receipt["policy"] not in ("w24_source", "normal4_source"):
        raise ValueError("wrong policy")
    return {
        "schema": "ecc2k130-equalb-m6-ordinary-pilot-audit-v1",
        "policy": receipt["policy"],
        "status": receipt["status"],
        "ordinary_query_index": receipt["ordinary_query_index"],
        "solver_search_began": bool(progress),
        "solver_restart_progress_lines": len(progress),
        "first_restart_line": progress[0] if progress else None,
        "last_restart_line": progress[-1] if progress else None,
        "solver_final_status_lines": finals,
        "solver_parse_lines": starts[:8],
        "stderr_nonempty": bool(error.strip()),
        "transcript_hashes_valid": True,
        "formula_sha256": receipt["formula_sha256"],
        "verified_relation": False,
        "novel_rank": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite an audit")
    result = audit(args.receipt)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("policy", "status", "solver_search_began",
                       "solver_restart_progress_lines")}, sort_keys=True))


if __name__ == "__main__":
    main()
