#!/usr/bin/env python3
"""Validate the four hash-index runs despite macOS time -l wrapper failure."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "a1_hash_audit.json"
    if output.exists():
        raise FileExistsError(output)
    source = HERE / "a1_index_bench.partial.json"
    rows = json.loads(source.read_text())["runs"]
    assert len(rows) == 4
    for row in rows:
        result = row["result"]
        assert result["status"] == "verified_recovery"
        assert result["charged_online_ns_exploratory"] == sum(
            result["phase_ns_exploratory"].values())
        assert "sysctl kern.clockrate: Operation not permitted" in row["stderr_tail"]
        cpu = re.search(r"([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys",
                        row["stderr_tail"])
        assert cpu
        row["time_wrapper"] = {"real_s": float(cpu.group(1)),
                               "user_s": float(cpu.group(2)),
                               "system_s": float(cpu.group(3))}
        row["status"] = "verified_child_wrapper_error"
        row["raw_sha256_verified"] = sha(HERE / "a1_runs" / row["raw_path"])
        assert row["raw_sha256_verified"] == row["raw_sha256"]
    for key in ("base_hash_blake3", "target_point", "recovered_scalar",
                "witness_indices", "pair_sums", "distinct_pair_x_orbit_keys",
                "duplicate_pair_keys", "lookups"):
        assert len({json.dumps(row["result"][key], sort_keys=True) for row in rows}) == 1, key
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "status": "four_raw_records_verified",
              "timing_class": "exploratory_unisolated",
              "wrapper_error": "macOS time -l queried denied kern.clockrate; child records completed",
              "executed_driver_sha256": sha(HERE / "a1_index_bench.py"),
              "source_sha256": sha(Path(__file__)),
              "partial_sha256": sha(source), "rows": rows}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": answer["status"], "runs": len(rows)}))


if __name__ == "__main__":
    main()
