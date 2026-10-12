#!/usr/bin/env python3
"""Validate the frozen source, paired witnesses, timing boundaries, and Sage replay."""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

from run_panel import HERE, normalized, sha


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    archive = sys.argv[1:] == ["--archive"]
    if sys.argv[1:] and not archive:
        raise SystemExit("usage: validate.py [--archive]")
    freeze = load(HERE / "freeze_receipt.json")
    workload = load(HERE / "workload.json")
    summary = load(HERE / "panel_summary.json")
    rows_path = HERE / "runs/panel_rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert len(rows) == 10 and summary["rows_sha256"] == sha(rows_path)
    assert summary["status"] == "verified"
    assert summary["controlled_online_speedup"] is None
    assert summary["freeze_sha256"] == sha(HERE / "freeze_receipt.json")
    assert freeze["workload_id"] == workload["workload_id"] == "c3929365e014"
    assert freeze["workload_sha256"] == sha(HERE / "workload.json")
    assert freeze["target_sha256"] == sha(HERE / "target_point.json")
    assert freeze["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    semantic_hashes = set()
    for row in rows:
        name = row["variant"]
        assert name in {"reference", "sparse"}
        assert row["status"] == "verified" and row["process_exit_code"] == 0
        assert row["process_wall_cap_s"] == 30
        manifest_path = HERE / f"{name}_manifest.json"
        manifest = load(manifest_path)
        assert freeze["variants"][name]["manifest_sha256"] == sha(manifest_path)
        identity_bytes = json.dumps(manifest["identity_record"], sort_keys=True,
                                    separators=(",", ":"), ensure_ascii=False).encode()
        assert hashlib.sha256(identity_bytes).hexdigest() == manifest["identity_sha256"]
        bound = manifest["candidate_freeze"]
        assert row["candidate_id"] == manifest["candidate_id"]
        assert row["workload_id"] == bound["workload_id"] == freeze["workload_id"]
        assert row["run_id"] == f'{row["candidate_id"]}W{row["workload_id"]}R{row["pair"]}'
        source = HERE / ("reference.rs" if name == "reference" else "candidate.rs") if archive else Path(bound["source_path"])
        assert sha(source) == bound["source_sha256"]
        if not archive:
            assert sha(Path(bound["binary_path"])) == bound["binary_sha256"]
        stem = f'R{row["pair"]}_{name}'
        output = HERE / "runs" / f"{stem}.jsonl"
        assert row["output_sha256"] == sha(output)
        assert row["stdout_sha256"] == sha(HERE / "runs" / f"{stem}.stdout")
        assert row["stderr_sha256"] == sha(HERE / "runs" / f"{stem}.stderr")
        record = load(output)
        assert record["target_count"] == 1
        assert record["group_verified"] is True
        assert record["root_table_entries"] == 3_154_661
        assert record["factor_base_points"] == 25_864
        assert record["recovered_scalar"] == 20_263_353_138_066
        phases = record["timing_ms"]
        assert abs(phases["target_online_phase_sum"] -
                   phases["target_online_after_reusable_setup"]) < 0.02
        assert abs(row["online_ms"] - phases["target_online_after_reusable_setup"]) < 0.02
        semantic = hashlib.sha256(json.dumps(normalized(record), sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        assert semantic == row["semantic_sha256"]
        semantic_hashes.add(semantic)
    assert semantic_hashes == {summary["semantic_sha256"]}
    assert summary["pairs"] == 5
    orders = []
    paired_ratios = []
    for pair in range(1, 6):
        pair_rows = sorted((row for row in rows if row["pair"] == pair),
                           key=lambda row: row["position"])
        assert len(pair_rows) == 2
        orders.append([row["variant"] for row in pair_rows])
        reference = next(row for row in pair_rows if row["variant"] == "reference")
        sparse = next(row for row in pair_rows if row["variant"] == "sparse")
        paired_ratios.append(reference["online_ms"] / sparse["online_ms"])
    assert orders == summary["orders"]
    assert paired_ratios == summary["paired_ratios"]
    assert statistics.median(paired_ratios) == summary["median_paired_reference_over_sparse"]
    for name in ("reference", "sparse"):
        assert statistics.median(row["online_ms"] for row in rows if row["variant"] == name) == summary[f"{name}_online_median_ms"]
    replay = load(HERE / "independent_sage_replay.json")
    assert replay["status"] == "verified" and replay["point_replay"] is True
    assert replay["workload_id"] == freeze["workload_id"]
    assert replay["verified_relation_witnesses"] == 238
    assert replay["matrix_rank"] == 237
    assert replay["recovered_scalar"] == 20_263_353_138_066
    assert replay["sage_runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    if archive:
        assert replay["base_source_sha256"] == sha(HERE / "replay_base.json")
    result = {
        "status": "verified_exploratory_timing",
        "candidate_ids": {name: load(HERE / f"{name}_manifest.json")["candidate_id"]
                          for name in ("reference", "sparse")},
        "workload_id": freeze["workload_id"],
        "paired_runs": 5,
        "semantic_sha256": summary["semantic_sha256"],
        "independent_sage_replay_sha256": sha(HERE / "independent_sage_replay.json"),
        "reference_online_median_ms": summary["reference_online_median_ms"],
        "sparse_online_median_ms": summary["sparse_online_median_ms"],
        "median_paired_reference_over_sparse": summary["median_paired_reference_over_sparse"],
        "paired_ratios": summary["paired_ratios"],
        "controlled_online_speedup": None,
        "timing_status": "exploratory_unisolated_host",
        "rows_sha256": sha(rows_path),
        "freeze_sha256": sha(HERE / "freeze_receipt.json"),
    }
    if archive:
        assert result == load(HERE / "validated_result.json")
        print(json.dumps({"status": "verified_archival_result", "result": result}, sort_keys=True))
    else:
        (HERE / "validated_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
