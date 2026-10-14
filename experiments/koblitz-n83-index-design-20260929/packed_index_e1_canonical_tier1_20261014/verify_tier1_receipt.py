#!/usr/bin/env python3
"""Independently audit a Tier 1 full-scan/zero-gap N83 canonicalization receipt.

The archive directory holds allocation.json, run-summary.json and results/
(the isolated_bench output: manifest.json, preflight.json, summary.json,
runs.jsonl, pairs.jsonl and each arm's stdout/stderr). The audit replays the
raw native results embedded in stdout, recomputes every paired ratio and
bootstrap interval, and applies the decision rule frozen in
tier1_protocol.json. A panel that failed a frozen gate gets verdict
"invalid"; a receipt whose files disagree with each other raises.
"""

import argparse
import base64
import hashlib
import json
import random
import statistics
from pathlib import Path

from verify_inputs import (ARM_FIELDS, HERE, MODES, PAIR_FIELDS, ROOT,
                           canonical, digest, verify as verify_inputs)

PHASES = ("target_query_preparation", "target_s3_batch", "target_partner_check")
SUBPHASES = ("target_cycle_canonical", "target_exact_lookup")


def load(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def bootstrap(ratios):
    rng = random.Random(20261011)
    boot = sorted(statistics.median(ratios[rng.randrange(len(ratios))] for _ in ratios)
                  for _ in range(10000))
    return [boot[250], boot[9749]]


def classify(interval):
    if interval[0] > 1:
        return "promoted"
    if interval[1] < 1:
        return "refuted_regression"
    return "not_promoted_inconclusive"


def magnitude(interval, reference):
    if interval[1] < reference:
        return "exploratory_magnitude_refuted_overstated"
    if interval[0] > reference:
        return "exploratory_magnitude_refuted_understated"
    return "exploratory_magnitude_consistent"


def audit(archive):
    archive = Path(archive).resolve(strict=True)
    results = archive / "results"
    tier = load(HERE / "tier1_protocol.json")
    verify_inputs(check_snapshot=False)
    summary = load(results / "summary.json")
    manifest = load(results / "manifest.json")
    preflight = load(results / "preflight.json")
    allocation = load(archive / "allocation.json")
    frozen = {"reference": load((HERE / tier["expected_reference_raw"]).resolve()),
              "candidate": load((HERE / tier["expected_candidate_raw"]).resolve())}
    repetitions = tier["repetitions"]
    hashes = summary["artifact_sha256"]

    def bound(suffix):
        matches = [path for path in hashes if path.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError("receipt does not hash exactly one " + suffix)
        return hashes[matches[0]]

    if (load(archive / "run-summary.json")["summary"] != summary or
            summary["manifest_sha256"] != digest(results / "manifest.json") or
            summary["runner_sha256"] != tier["bound_sha256"]["isolated_bench_runner"] or
            summary["runner_sha256"] != digest(ROOT / "scripts" / "isolated_bench.py") or
            summary["measurement_tier"] != "tier1_instance" or
            manifest["measurement_tier"] != "tier1_instance" or
            manifest["repetitions"] != repetitions or
            manifest["timeout_s"] != tier["timeout_s_per_arm"] or
            manifest["pair_fields"] != tier["pair_fields"] or
            manifest["allocation"]["provider"] != allocation["provider"] or
            manifest["allocation"]["instance_id"] != allocation["instance_id"] or
            bound("/tier1_protocol.json") != digest(HERE / "tier1_protocol.json") or
            bound("/native_packed_index.rs") != tier["bound_sha256"]["native_source"] or
            bound("/allocation.json") != digest(archive / "allocation.json") or
            bound("/benchmark_stage.py") != tier["bound_sha256"]["stage_wrapper"]):
        raise ValueError("receipt allocation, protocol, source, runner, or summary differs")
    base = {"allocation": {key: allocation.get(key) for key in
                           ("provider", "instance_id", "run_url", "git_sha")},
            "measurement_tier": "tier1_instance",
            "tier1_protocol_sha256": digest(HERE / "tier1_protocol.json")}
    problems = []
    if not preflight["ok"]:
        problems.append("preflight rejected: " + "; ".join(preflight["problems"]))
    if summary["status"] != "completed" or not summary.get("artifacts_stable"):
        problems.append("runner status " + str(summary["status"]))
    if problems:
        return dict(base, verdict="invalid", problems=problems)

    rows = lines(results / "runs.jsonl")
    pairs = lines(results / "pairs.jsonl")
    order = [variant for pair in tier["pair_order"] for variant in pair]
    if (len(rows) != 2 * repetitions or len(pairs) != repetitions or
            summary["valid_pairs"] != repetitions or summary["expected_pairs"] != repetitions or
            [row["variant"] for row in rows] != order):
        raise ValueError("completed receipt has the wrong pair count or order")
    if len({row["binary_sha256"] for row in rows}) != 1:
        problems.append("more than one binary digest")
    expected_fields = tier["expected_fields"]
    phase = {"reference": [], "candidate": []}
    control = {"reference": [], "candidate": []}
    online = {"reference": [], "candidate": []}
    observed = []
    peak_rss = 0
    for row in rows:
        variant = row["variant"]
        if row["status"] != "valid" or row["issues"]:
            problems.append("arm {} invalid: {}".format(row["serial"], row["issues"]))
            continue
        stdout = (results / row["stdout_file"]).read_text().splitlines()
        raw_line = next(line for line in stdout if line.startswith("raw_result_json_base64="))
        raw_bytes = base64.b64decode(raw_line.split("=", 1)[1], validate=True)
        raw = json.loads(raw_bytes)
        timing = {key: int(value) for key, value in raw["timing_ns"].items()}
        deltas = row["tier1_observations"]["counter_deltas"]
        certificate = hashlib.sha256(canonical({k: raw[k] for k in PAIR_FIELDS})).hexdigest()
        if (hashlib.sha256(raw_bytes).hexdigest() != row["fields"]["raw_result_sha256"] or
                raw["index_mode"] != MODES[variant == "candidate"] or
                certificate != tier["expected_result"] or
                any(row["fields"].get(k) != v for k, v in expected_fields.items()) or
                row["fields"]["verified"] != "1" or row["fields"]["stage_verified"] != "1" or
                any(raw[name] != frozen[variant][name] for name in ARM_FIELDS) or
                abs(timing["target_pdp_and_native_check"] / 1e6 - row["online_ms"]) > 1e-5):
            raise ValueError("arm {} raw output differs from its receipt".format(row["serial"]))
        if (sum(timing[name] for name in PHASES) > timing["target_pdp_and_native_check"] or
                sum(timing[name] for name in SUBPHASES) > timing["target_partner_check"] or
                timing["target_cycle_canonical"] <= 0 or timing["target_s3_batch"] <= 0):
            problems.append("arm {} phase accounting".format(row["serial"]))
        if raw["peak_rss_bytes"] > tier["peak_rss_cap_mib"] << 20:
            problems.append("arm {} RSS cap".format(row["serial"]))
        if (deltas["cpu_stat"].get("nr_throttled") != 0 or
                deltas["memory_events"].get("oom") != 0 or
                deltas["memory_events"].get("oom_kill", 0) != 0):
            problems.append("arm {} throttling or memory event".format(row["serial"]))
        peak_rss = max(peak_rss, raw["peak_rss_bytes"])
        phase[variant].append(timing["target_cycle_canonical"])
        control[variant].append(timing["target_s3_batch"])
        online[variant].append(row["online_ms"])
        cpu = str(manifest["isolation"]["execution_cpu"])
        observed.append({"serial": row["serial"], "variant": variant,
                         "steal_ticks": deltas["per_cpu"].get(cpu, {}).get("steal"),
                         "involuntary_switches":
                             row["tier1_observations"]["child_involuntary_switches"],
                         "child_user_ms": row["tier1_observations"]["child_user_ms"]})
    if problems:
        return dict(base, verdict="invalid", problems=problems)

    def paired(values):
        out = []
        for repeat in range(repetitions):
            out.append(values["reference"][repeat] / values["candidate"][repeat])
        return out

    stage_ratios = paired(online)
    for ratio, pair in zip(stage_ratios, pairs):
        if pair["status"] != "valid" or abs(ratio - pair["speedup"]) > 1e-12:
            raise ValueError("runner pair ratio differs")
    stage_interval = bootstrap(stage_ratios)
    if (abs(statistics.median(stage_ratios) - summary["paired_speedup"]) > 1e-12 or
            any(abs(a - b) > 1e-12 for a, b in
                zip(stage_interval, summary["tier1_bootstrap95_by_pair"])) or
            (stage_interval[0] > 1) != bool(summary["speedup_claim_eligible"])):
        raise ValueError("runner bootstrap or eligibility differs")
    canon_ratios = paired(phase)
    canon_interval = bootstrap(canon_ratios)
    control_ratios = paired(control)
    reference = float(tier["statistics"]["exploratory_reference"]["canonicalization_phase_ratio"])
    return dict(
        base,
        verdict=classify(canon_interval),
        magnitude=magnitude(canon_interval, reference),
        primary={"name": "canonicalization_phase_ratio",
                 "median": statistics.median(canon_ratios),
                 "bootstrap95": canon_interval, "per_pair": canon_ratios,
                 "exploratory_reference": reference},
        secondary={"name": "target_stage_ratio", "verdict": classify(stage_interval),
                   "median": statistics.median(stage_ratios),
                   "bootstrap95": stage_interval, "per_pair": stage_ratios},
        negative_control={"name": "s3_batch_phase_ratio",
                          "median": statistics.median(control_ratios),
                          "bootstrap95": bootstrap(control_ratios)},
        median_canonicalization_ns={k: statistics.median(v) for k, v in phase.items()},
        median_online_ms={k: statistics.median(v) for k, v in online.items()},
        max_native_rss_bytes=peak_rss, valid_pairs=repetitions,
        recorded_not_gated=observed)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
