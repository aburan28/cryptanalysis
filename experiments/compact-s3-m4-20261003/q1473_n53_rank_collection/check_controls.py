#!/usr/bin/env python3
"""Check warm-table outputs against Q1469's archived absent/found controls."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from build import sha

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
RESULT = HERE / "control_result.json"


def check() -> dict:
    command = [str(HERE / "batch_oracle"),
               str(PARENT / "q1420_root_theory/n53_field.txt"),
               str(PARENT / "q1468_n53_pair_oracle/inputs/base_points.txt"),
               str(HERE / "control_targets.txt"), "60", "2"]
    completed = subprocess.run(command, check=True, capture_output=True,
                               text=True, timeout=180)
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(rows) == 3
    setup, *queries = rows
    assert setup["pair_table_entries"] == 3651700
    assert setup["duplicate_pair_sums"] == 0
    for index, row in enumerate(queries):
        prior = json.loads((PARENT / "q1469_n53_yield_panel/runs" /
                            f"{index:03d}/receipt.json").read_text())[
                                "native_report"]
        assert row["index"] == index
        for key in ("status", "witness_indices", "query_pair_sums_examined",
                    "complement_hits", "rejected_shared_columns",
                    "query_field_calls"):
            assert row[key] == prior[key], (index, key)
    return {
        "kind": "q1473_exact_q1469_matched_controls",
        "status": "passed", "proposal_id": "Q1473",
        "binary_sha256": sha(HERE / "batch_oracle"),
        "control_targets_sha256": sha(HERE / "control_targets.txt"),
        "archived_receipt_sha256": [
            sha(PARENT / "q1469_n53_yield_panel/runs" /
                f"{index:03d}/receipt.json") for index in range(2)],
        "table_field_calls": setup["table_field_calls"],
        "cases": [{"index": row["index"], "status": row["status"],
                   "witness_indices": row["witness_indices"],
                   "query_pair_sums_examined": row[
                       "query_pair_sums_examined"],
                   "query_field_calls": row["query_field_calls"]}
                  for row in queries],
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = check()
    if args.emit:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, sort_keys=True, indent=2) +
                          "\n")
    else:
        assert result == json.loads(RESULT.read_text())
    print(json.dumps({"status": result["status"],
                      "cases": [row["status"] for row in result["cases"]]}),
          flush=True)


if __name__ == "__main__":
    main()
