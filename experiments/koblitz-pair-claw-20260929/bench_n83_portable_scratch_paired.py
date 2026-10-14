#!/usr/bin/env python3
"""Paired Q1061 scratch-buffer stage probe on one frozen n=83 workload."""

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path

import n83_low_memory_smoke_check as smoke

HERE = Path(__file__).resolve().parent
BASE_SHA = "93e8f9d642ff23d1952903d3b088ef08f5be0eae"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sha(root):
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()


def run_one(root, out_dir, label, index, args):
    runner = root / "experiments/koblitz-pair-claw-20260929/run_n83_portable_chunk.py"
    output = out_dir / f"{index:02d}_{label}.json"
    binary = out_dir / f"{index:02d}_{label}_binary"
    command = [
        sys.executable, str(runner),
        "--cpu-backend", args.cpu_backend, "--cxx", args.cxx,
        "--spill-dir", str(args.spill_dir), "--binary", str(binary),
        "--table-log2", str(args.table_log2),
        "--query-reps-log2", str(args.query_reps_log2),
        "--table-start", "0", "--query-start", str(1 << 30),
        "--workers", str(args.workers), "--rep-batch", "8",
        "--bits-per-key", "20", "--hashes", "10",
        "--out", str(output),
    ]
    print(json.dumps({"starting":label, "index":index, "command":command}),
          flush=True)
    subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
    row = json.loads(output.read_text())
    assert row["proposal_id"] == "Q1061" and row["candidate_id"] is None
    assert row["isogeny"] == "none"
    assert row["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert row["factor_base"]["actual_usable_points_B_before_folding"] == 8000204
    assert row["factor_base"]["signed_frobenius_columns"] == 48194
    assert row["factor_base"]["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    assert row["public_target"] == [166311729772738850527374020566776271469570801390478,
                                     31581718638330981782208350563395118515724809132456]
    assert row["table_descriptors"] == 1 << args.table_log2
    assert row["query_representatives"] == 1 << args.query_reps_log2
    assert row["query_workers"] == args.workers
    assert row["native_result"]["candidate_store_mode"] == "unlinked_file"
    assert row["native_result"]["candidate_spill_bytes"] == (
        24 * row["native_result"]["bloom_positive_queries"])
    assert row["native_result"]["peak_rss_bytes"] >= row[
        "native_result"]["bloom_bytes"]
    print(json.dumps({"finished":label, "index":index,
                      "query_seconds":row["native_result"]["query_seconds"],
                      "exact_hits":row["native_result"]["exact_hit_queries"]}),
          flush=True)
    return output, row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--spill-dir", type=Path, required=True)
    parser.add_argument("--cpu-backend", choices=("arm_pmull", "x86_pclmul",
                                                  "generic"), required=True)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--table-log2", type=int, default=24)
    parser.add_argument("--query-reps-log2", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--measurement-label", required=True)
    args = parser.parse_args()
    args.baseline_root = args.baseline_root.resolve()
    args.current_root = args.current_root.resolve()
    args.out_dir = args.out_dir.resolve()
    args.spill_dir = args.spill_dir.resolve()
    assert args.baseline_root != args.current_root
    assert git_sha(args.baseline_root) == BASE_SHA
    assert args.out_dir.is_dir() and not list(args.out_dir.iterdir())
    assert args.spill_dir.is_dir()
    assert 1 <= args.workers <= 64
    assert 16 <= args.table_log2 <= 28 and 10 <= args.query_reps_log2 <= 30
    command = [args.cxx, "--version"]
    compiler_version = subprocess.run(command, check=True, capture_output=True,
                                      text=True).stdout.splitlines()[0]
    sequence = [("baseline", args.baseline_root),
                ("current", args.current_root),
                ("current", args.current_root),
                ("baseline", args.baseline_root)]
    rows = []
    for index, (label, root) in enumerate(sequence):
        path, row = run_one(root, args.out_dir, label, index, args)
        rows.append((label, path, row))
    first = rows[0][2]
    for _, _, row in rows[1:]:
        assert row["curve_identity_record"] == first["curve_identity_record"]
        assert row["factor_base"] == first["factor_base"]
        assert row["public_target"] == first["public_target"]
        assert row["table_schedule"] == first["table_schedule"]
        assert row["query_representative_schedule"] == first[
            "query_representative_schedule"]
        assert row["native_field_add_mul_sqr_call_model"] == first[
            "native_field_add_mul_sqr_call_model"]
        for key in smoke.EQUAL_NATIVE_FIELDS:
            assert row["native_result"][key] == first["native_result"][key], key
        assert row["native_result"]["candidate_spill_bytes"] == first[
            "native_result"]["candidate_spill_bytes"]
        assert row["verified_public_target_quotient_table_dlp"] == first[
            "verified_public_target_quotient_table_dlp"]
    baseline = [row for label, _, row in rows if label == "baseline"]
    current = [row for label, _, row in rows if label == "current"]
    query_ratios = [a["native_result"]["query_seconds"] /
                    b["native_result"]["query_seconds"]
                    for a, b in zip(baseline, current)]
    online_ratios = [a["target_online_seconds"] /
                     b["target_online_seconds"]
                     for a, b in zip(baseline, current)]
    report = {
        "kind": "n83_q1061_reusable_scratch_paired_stage_probe",
        "scope": "same-target bounded stage comparison; not a natural relation or complete DLP",
        "measurement_label": args.measurement_label,
        "proposal_id": "Q1061", "candidate_id": None, "run_id": None,
        "curve_id": first["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": first["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "public_target": first["public_target"],
        "table_descriptors": first["table_descriptors"],
        "query_representatives": first["query_representatives"],
        "query_workers": args.workers,
        "cpu_backend": args.cpu_backend,
        "source_commits": {"baseline": BASE_SHA,
                           "current": git_sha(args.current_root)},
        "native_source_sha256s": {
            label: row["native_source_sha256"]
            for label, _, row in rows},
        "native_pairs_sha256s": {
            label: row["native_pairs_sha256"]
            for label, _, row in rows},
        "sequence": [{"position": i, "variant": label,
                      "receipt": path.name, "receipt_sha256": sha(path),
                      "query_seconds": row["native_result"]["query_seconds"],
                      "online_seconds": row["target_online_seconds"],
                      "peak_rss_bytes": row["native_result"]["peak_rss_bytes"]}
                     for i, (label, path, row) in enumerate(rows)],
        "paired_query_speedup_baseline_over_current": query_ratios,
        "median_paired_query_speedup": statistics.median(query_ratios),
        "paired_online_speedup_baseline_over_current": online_ratios,
        "median_paired_online_speedup": statistics.median(online_ratios),
        "exact_outcomes_equal": True,
        "exact_hit_queries": first["native_result"]["exact_hit_queries"],
        "verified_public_target_quotient_table_dlp": first[
            "verified_public_target_quotient_table_dlp"],
        "complete_solve_work_log2": None,
        "hardware": {"os": platform.platform(), "architecture": platform.machine(),
                     "python": sys.version, "compiler": compiler_version,
                     "logical_cpu_count": os.cpu_count()},
        "source_sha256": sha(Path(__file__)),
        "limits": ["Two ABBA pairs provide a range and median, not a confidence interval.",
                   "The baseline and current methods have identical mathematical work; only scratch allocation changes.",
                   "A stage timing ratio does not establish a verified single-target IC speedup."],
    }
    assert all(math.isfinite(x) and x > 0 for x in query_ratios + online_ratios)
    output = args.out_dir / "paired_summary.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"summary": str(output),
                      "median_query_speedup": report[
                          "median_paired_query_speedup"],
                      "exact_outcomes_equal": True}), flush=True)


if __name__ == "__main__":
    main()
