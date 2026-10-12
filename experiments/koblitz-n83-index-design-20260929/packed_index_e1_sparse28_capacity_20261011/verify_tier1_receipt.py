#!/usr/bin/env python3
"""Independently audit the archived N83 sparse26/sparse28 Tier 1 result."""

import base64
import hashlib
import json
import random
import statistics
from pathlib import Path

from benchmark_stage import ARM_FIELDS, MODES, PAIR_FIELDS, canonical, digest


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "tier1_github_38187970079"
RESULTS = ARCHIVE / "results"


def load(path):
    return json.loads(path.read_text())


def verify():
    summary = load(RESULTS / "summary.json")
    manifest = load(RESULTS / "manifest.json")
    allocation = load(ARCHIVE / "allocation.json")
    preflight = load(RESULTS / "preflight.json")
    rows = [json.loads(line) for line in (RESULTS / "runs.jsonl").read_text().splitlines()]
    pairs = [json.loads(line) for line in (RESULTS / "pairs.jsonl").read_text().splitlines()]
    frozen = {
        "reference": load(HERE / "run_1_sparse26.json"),
        "candidate": load(HERE / "run_2_sparse28.json"),
    }
    protocol = load(HERE / "tier1_protocol.json")
    certificate = hashlib.sha256(canonical(
        {name: frozen["reference"][name] for name in PAIR_FIELDS})).hexdigest()
    source = digest(HERE / "native_packed_index.rs")
    receipt_hashes = summary["artifact_sha256"]
    source_path = next(path for path in receipt_hashes
                       if path.endswith("/native_packed_index.rs"))
    allocation_path = next(path for path in receipt_hashes
                           if path.endswith("/allocation.json"))
    if (summary["status"] != "completed" or
            summary["measurement_tier"] != "tier1_instance" or
            summary["valid_pairs"] != summary["expected_pairs"] != 8 or
            not summary["artifacts_stable"] or not preflight["ok"] or
            summary["manifest_sha256"] != digest(RESULTS / "manifest.json") or
            summary["runner_sha256"] != digest(HERE.parents[2] / "scripts/isolated_bench.py") or
            load(ARCHIVE / "run-summary.json")["summary"] != summary or
            manifest["measurement_tier"] != "tier1_instance" or
            manifest["repetitions"] != 8 or manifest["timeout_s"] != 300 or
            manifest["allocation"]["provider"] != allocation["provider"] != "github_actions" or
            manifest["allocation"]["instance_id"] != allocation["instance_id"] or
            allocation["instance_id"] != "gh-38187970079-1-paired-stage" or
            source != protocol["expected_fields"]["native_source_sha256"] or
            protocol["expected_result"] != certificate or
            receipt_hashes[source_path] != source or
            receipt_hashes[allocation_path] != digest(ARCHIVE / "allocation.json")):
        raise ValueError("Tier 1 allocation, source, or summary differs")
    if (len(rows) != 16 or len(pairs) != 8 or
            [row["variant"] for row in rows] !=
            ["reference", "candidate", "candidate", "reference"] * 4 or
            any(row["status"] != "valid" or row["issues"] for row in rows) or
            any(pair["status"] != "valid" or pair["issues"] for pair in pairs) or
            len({row["binary_sha256"] for row in rows}) != 1):
        raise ValueError("Tier 1 pair order, validity, or binary differs")
    peak_rss = 0
    timings = {"reference": [], "candidate": []}
    for row in rows:
        variant = row["variant"]
        line = (RESULTS / row["stdout_file"]).read_text().splitlines()[0]
        raw_bytes = base64.b64decode(line.split("=", 1)[1], validate=True)
        raw = json.loads(raw_bytes)
        phases = ("target_query_preparation", "target_partner_generation",
                  "target_partner_check")
        deltas = row["tier1_observations"]["counter_deltas"]
        if (hashlib.sha256(raw_bytes).hexdigest() != row["fields"]["raw_result_sha256"] or
                raw["index_mode"] != MODES[variant == "candidate"] or
                raw["native_source_sha256"] != source or
                row["fields"]["pair_certificate"] != certificate or
                row["fields"]["verified"] != "1" or
                row["fields"]["stage_verified"] != "1" or
                any(raw[name] != frozen[variant][name] for name in ARM_FIELDS) or
                abs(int(raw["timing_ns"]["target_pdp_and_native_check"]) / 1e6 -
                    row["online_ms"]) > 1e-5 or
                sum(int(raw["timing_ns"][name]) for name in phases) >
                    int(raw["timing_ns"]["target_pdp_and_native_check"]) or
                raw["peak_rss_bytes"] > 5500 * (1 << 20) or
                deltas["cpu_stat"]["nr_throttled"] != 0 or
                deltas["memory_events"]["oom"] != 0 or
                deltas["memory_events"]["oom_kill"] != 0):
            raise ValueError("Tier 1 raw output, phase, memory, or noise differs")
        peak_rss = max(peak_rss, raw["peak_rss_bytes"])
        timings[variant].append(row["online_ms"])
    ratios = []
    for repeat in range(8):
        arm = rows[2 * repeat:2 * repeat + 2]
        reference = next(row for row in arm if row["variant"] == "reference")
        candidate = next(row for row in arm if row["variant"] == "candidate")
        ratio = reference["online_ms"] / candidate["online_ms"]
        if abs(ratio - pairs[repeat]["speedup"]) > 1e-12:
            raise ValueError("paired ratio differs")
        ratios.append(ratio)
    rng = random.Random(20261011)
    boot = sorted(statistics.median(ratios[rng.randrange(8)] for _ in ratios)
                  for _ in range(10000))
    interval = [boot[250], boot[9749]]
    if (abs(statistics.median(ratios) - summary["paired_speedup"]) > 1e-12 or
            any(abs(a - b) > 1e-12 for a, b in
                zip(interval, summary["tier1_bootstrap95_by_pair"])) or
            interval[0] <= 1 or not summary["speedup_claim_eligible"]):
        raise ValueError("paired confidence calculation or promotion differs")
    return {"status": "PASS", "valid_pairs": 8,
            "paired_speedup": statistics.median(ratios),
            "bootstrap95": interval, "max_native_rss_bytes": peak_rss,
            "median_online_ms": {name: statistics.median(times)
                                 for name, times in timings.items()},
            "speedup_claim_eligible": True}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
