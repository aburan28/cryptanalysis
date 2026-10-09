#!/usr/bin/env python3
"""Freeze extraction of N41 mixed-cubic null equations after the rank result."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "extract_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first extraction protocol")
    rank = json.loads((HERE / "rank.json").read_text())
    control = json.loads((HERE / "rank_control.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    if (control["status"] != "EXIT_SUCCESS" or
            audit["status"] != "PASS_INDEPENDENT_SAGE_GROUP_REPLAY" or
            rank["rank"] != 47206 or rank["mixed_excess_nullity"] != 1488):
        raise ValueError("rank/audit prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_full_xy_cubic_rref_equation_extraction",
        "proposal_id": "Q20261009231000", "candidate_id": None,
        "rows": 80000, "feature_count": 48818, "expected_rank": 47206,
        "selection_rule": "After full RREF, consider each free-column null vector whose support contains a seed variable and a coordinate variable; choose eight smallest supports, breaking ties by free-column index.",
        "training_validation": "Evaluate each extracted equation directly on all 80000 original rows using independent monomial reads.",
        "limits": {"workers": 1, "wall_seconds": 300, "rss_bytes": 4294967296},
        "compiler": "clang++ -O3 -std=c++17 -I/var/tmp/sage-10.9-current/local/include -L/var/tmp/sage-10.9-current/local/lib -Wl,-rpath,/var/tmp/sage-10.9-current/local/lib extract.cpp -lm4ri -o extract",
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "production.json", "rows.bin",
                          "rank.json", "rank_control.json", "sage_audit.json")},
        "source_sha256": {name: digest(HERE / name) for name in
                          ("extract.cpp", "extract", "freeze_extract.py")},
        "holdout_seed": 20261009231002, "holdout_rows": 50000,
        "holdout_max_draws": 90000,
        "claim_boundary": "null equations are candidate constraints until independently validated on new exact pairs; rejection of public residuals must be measured separately",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
