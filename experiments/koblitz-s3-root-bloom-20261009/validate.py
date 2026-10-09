#!/usr/bin/env python3
"""Validate source-bound paired runs, Sage replay, and lookup diagnostic."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

from run_panel import normalized, sha

HERE = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    freeze = load(HERE / "freeze_receipt.json")
    summary = load(HERE / "panel_summary.json")
    rows_path = HERE / "runs/panel_rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert len(rows) == 10 and summary["rows_sha256"] == sha(rows_path)
    assert freeze["workload_sha256"] == sha(HERE / "workload.json")
    assert freeze["target_sha256"] == sha(HERE / "target_point.json")
    assert freeze["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert all(row["status"] == "verified" for row in rows)
    semantic_hashes = set()
    for row in rows:
        name = row["variant"]
        manifest_path = HERE / f"{name}_manifest.json"
        manifest = load(manifest_path)
        assert freeze["variants"][name]["manifest_sha256"] == sha(manifest_path)
        assert hashlib.sha256(json.dumps(manifest["identity_record"], sort_keys=True,
                                        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest() == manifest["identity_sha256"]
        bound = manifest["candidate_freeze"]
        assert row["candidate_id"] == manifest["candidate_id"]
        assert row["workload_id"] == bound["workload_id"] == freeze["workload_id"]
        assert row["run_id"] == f'{row["candidate_id"]}W{row["workload_id"]}R{row["pair"]}'
        assert sha(Path(bound["source_path"])) == bound["source_sha256"]
        assert sha(Path(bound["binary_path"])) == bound["binary_sha256"]
        stem = f'R{row["pair"]}_{name}'
        path = HERE / "runs" / f"{stem}.jsonl"
        assert sha(path) == row["output_sha256"]
        assert sha(HERE / "runs" / f"{stem}.stdout") == row["stdout_sha256"]
        assert sha(HERE / "runs" / f"{stem}.stderr") == row["stderr_sha256"]
        run = load(path)
        assert run["group_verified"] is True
        assert run["target_count"] == 1
        assert run["root_table_entries"] == 3_154_661
        assert run["factor_base_points"] == 25_864
        assert run["recovered_scalar"] == 20_263_353_138_066
        timing = run["timing_ms"]
        assert abs(timing["target_online_phase_sum"] -
                   timing["target_online_after_reusable_setup"]) < 0.02
        assert abs(row["online_ms"] - timing["target_online_after_reusable_setup"]) < 0.02
        semantic = hashlib.sha256(json.dumps(normalized(run), sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        assert semantic == row["semantic_sha256"]
        semantic_hashes.add(semantic)
        if name == "bloom":
            assert run["root_bloom_bytes"] == 4_194_304
            assert timing["index_root_bloom_build_and_exhaustive_check"] > 0
    assert semantic_hashes == {summary["semantic_sha256"]}
    replay = load(HERE / "independent_sage_replay.json")
    assert replay["status"] == "verified" and replay["point_replay"] is True
    assert replay["workload_id"] == freeze["workload_id"]
    assert replay["verified_relation_witnesses"] == 238
    assert replay["matrix_rank"] == 237
    assert replay["recovered_scalar"] == 20_263_353_138_066
    assert replay["sage_runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")

    diagnostic_source = HERE / "diagnostic/src/main.rs"
    diagnostic_binary = HERE / "target/release/koblitz-s3-root-bloom-diagnostic"
    diagnostic_output = HERE / "diagnostic/diagnostic.jsonl"
    diag = load(diagnostic_output)
    assert normalized(diag) == normalized(load(HERE / "runs/R1_bloom.jsonl"))
    checks = diag["root_bloom_online_checks"]
    negatives = diag["root_bloom_online_negatives"]
    misses = diag["root_bloom_online_positive_lookup_misses"]
    hits = diag["root_bloom_online_exact_root_hits"]
    assert checks == negatives + misses + hits
    assert hits == 239 and diag["group_verified"] is True
    memory = load(HERE / "memory_summary.json")
    memory_rows_path = HERE / "memory_runs/panel_rows.jsonl"
    memory_rows = [json.loads(line) for line in memory_rows_path.read_text().splitlines()]
    assert len(memory_rows) == 6 and memory["rows_sha256"] == sha(memory_rows_path)
    assert memory["protocol_sha256"] == sha(HERE / "MEMORY_PROTOCOL.md")
    assert memory["unit"] == "bytes"
    assert all(row["status"] == "verified" and row["outer_status"] == "completed"
               for row in memory_rows)
    paired_peak_deltas = []
    for pair in range(1, 4):
        pair_rows = {row["variant"]: row for row in memory_rows if row["pair"] == pair}
        for name, row in pair_rows.items():
            manifest = load(HERE / f"{name}_manifest.json")
            assert row["binary_sha256"] == manifest["candidate_freeze"]["binary_sha256"]
            path = HERE / "memory_runs" / f"M{pair}_{name}.jsonl"
            assert row["output_sha256"] == sha(path)
            assert normalized(load(path)) == normalized(load(HERE / "runs/R1_bloom.jsonl"))
        paired_peak_deltas.append(pair_rows["bloom"]["ru_maxrss_raw"] -
                                  pair_rows["reference"]["ru_maxrss_raw"])
    result = {
        "status": "verified_exploratory_timing",
        "candidate_ids": {name: load(HERE / f"{name}_manifest.json")["candidate_id"]
                          for name in ("reference", "bloom")},
        "workload_id": freeze["workload_id"],
        "paired_runs": 5,
        "semantic_sha256": summary["semantic_sha256"],
        "independent_sage_replay_sha256": sha(HERE / "independent_sage_replay.json"),
        "diagnostic_source_sha256": sha(diagnostic_source),
        "diagnostic_binary_sha256": sha(diagnostic_binary),
        "diagnostic_output_sha256": sha(diagnostic_output),
        "canonical_root_probes": checks,
        "bloom_negative_probes": negatives,
        "exact_root_table_probes": misses + hits,
        "exact_root_hits": hits,
        "bloom_false_positive_rate_among_exact_misses": misses / (checks - hits),
        "fraction_exact_table_probes_avoided": negatives / checks,
        "bloom_bytes": diag["root_bloom_bytes"],
        "peak_rss_probe_unit": "bytes",
        "peak_rss_reference_median_bytes": memory["reference_median_peak_rss_raw"],
        "peak_rss_bloom_median_bytes": memory["bloom_median_peak_rss_raw"],
        "peak_rss_paired_deltas_bytes": paired_peak_deltas,
        "peak_rss_median_paired_delta_bytes": statistics.median(paired_peak_deltas),
        "peak_rss_rows_sha256": sha(memory_rows_path),
        "controlled_online_speedup": None,
        "timing_status": "exploratory_unisolated_host",
    }
    (HERE / "validated_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
