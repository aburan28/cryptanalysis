#!/usr/bin/env python3
"""Compare the two/five restart traces against their audited raw logs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "R1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    audit = json.loads((RUN / "audit.json").read_text())
    if audit["status"] != "PASS_EVIDENCE_BINDING":
        raise ValueError("independent audit has not passed")
    cells = {row["variant"]: row for row in audit["cells"]}
    reports = {}
    restart_sets = {}
    for variant in ("two", "five"):
        path = RUN / f"normal4_counter_{variant}.stdout.txt"
        raw = path.read_bytes()
        if sha(raw) != cells[variant]["stdout_sha256"]:
            raise ValueError(f"stdout differs from audited bytes: {variant}")
        lines = raw.decode(errors="replace").splitlines()
        restarts = [line for line in lines
                    if line.lstrip().startswith("c rst ")]
        final_conflicts = [int(value) for value in re.findall(
            r"^c conflicts\s*:\s*(\d+)\s*$", raw.decode(errors="replace"), re.M)]
        if not final_conflicts:
            raise ValueError(f"missing terminal conflict counter: {variant}")
        calls = [
            {"matrix_index": int(index), "printed_calls": value}
            for index, value in re.findall(
                r"c \[g (\d+)\] elim called\s*:\s*(\d+[KM]?)", raw.decode(errors="replace"))
        ]
        restart_sets[variant] = restarts
        reports[variant] = {
            "stdout_sha256": sha(raw),
            "restart_rows": len(restarts),
            "final_conflicts": final_conflicts[-1],
            "restart_trace_sha256": sha(("\n".join(restarts) + "\n").encode()),
            "printed_elimination_calls": calls,
        }
    report = {
        "schema": "ecc2k130-equalb-normal4-conflict-trace-v1",
        "audit_sha256": sha((RUN / "audit.json").read_bytes()),
        "exact_restart_trace_equal": restart_sets["two"] == restart_sets["five"],
        "variants": reports,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        if args.out.exists():
            raise FileExistsError(args.out)
        args.out.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
