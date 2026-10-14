#!/usr/bin/env python3
"""Verify the frozen inputs of the N83 full-scan/zero-gap Tier 1 replay."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL = HERE.parent / "packed_index_e1_canonical_20261009"
ADAPTER = HERE.parent / "packed_index_e1_isolated_replay_20261010"
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"
ROOT = HERE.parents[2]
sys.path.insert(0, str(ADAPTER))

from benchmark_stage import ARM_FIELDS, MODES, PAIR_FIELDS, canonical, digest  # noqa: E402
from restore_crypto_source import ensure_snapshot  # noqa: E402

RUNS = ("run_1_packed_bucket22", "run_2_packed_bucket22_fastcanon",
        "run_3_packed_bucket22_fastcanon", "run_4_packed_bucket22",
        "run_5_packed_bucket22", "run_6_packed_bucket22_fastcanon")


def load(path):
    return json.loads(Path(path).read_text())


def verify(check_snapshot=True):
    tier = load(HERE / "tier1_protocol.json")
    protocol = load(CANONICAL / "protocol.json")
    stage = load(CANONICAL / "stage_manifest.json")
    bound = tier["bound_sha256"]
    files = {
        "canonical_protocol": CANONICAL / "protocol.json",
        "canonical_stage_manifest": CANONICAL / "stage_manifest.json",
        "canonical_workload": CANONICAL / "workload.json",
        "canonical_summary": CANONICAL / "summary.json",
        "native_source": CANONICAL / "native_packed_index.rs",
        "cargo_manifest": CANONICAL / "Cargo.toml",
        "cargo_lock": CANONICAL / "Cargo.lock",
        "bridge": INPUTS / "n83_onb_poly_bridge.json",
        "representatives": INPUTS / "n83_x_representatives.bin",
        "reference_expected_raw": (HERE / tier["expected_reference_raw"]).resolve(),
        "candidate_expected_raw": (HERE / tier["expected_candidate_raw"]).resolve(),
        "stage_wrapper": (HERE / tier["stage_wrapper"]).resolve(),
        "isolated_bench_runner": ROOT / "scripts" / "isolated_bench.py",
    }
    if set(files) != set(bound):
        raise ValueError("Tier 1 protocol binds a different file set")
    bad = [name for name, path in files.items() if digest(path) != bound[name]]
    if bad:
        raise ValueError("frozen file digest differs: " + ", ".join(bad))
    inputs = protocol["inputs_sha256"]
    if (inputs["native_source"] != bound["native_source"] or
            inputs["cargo_manifest"] != bound["cargo_manifest"] or
            inputs["cargo_lock"] != bound["cargo_lock"] or
            inputs["bridge"] != bound["bridge"] or
            inputs["representatives"] != bound["representatives"] or
            stage["stage_protocol_sha256"] != bound["canonical_protocol"]):
        raise ValueError("canonical protocol and Tier 1 bindings disagree")
    pair_fields = ["curve_id", "workload_id", "input_sha256", "status",
                   "indexed_states", "target_states", "pair_certificate",
                   "native_source_sha256"]
    if (tier["measurement_tier"] != "tier1_instance" or
            not tier["frozen_before_any_timing"] or
            tier["proposal_id"] != protocol["proposal_id"] or
            not tier["curve_id"] == protocol["curve_id"] == stage["curve_id"] or
            not tier["workload_id"] == protocol["workload_id"] == stage["workload_id"] or
            (tier["reference_mode"], tier["candidate_mode"]) != MODES or
            not tier["pair_state_cap"] == stage["pair_state_cap"] == 2_000_000 or
            not tier["peak_rss_cap_mib"] == stage["peak_rss_cap_mib"] == 1024 or
            stage["target_count"] != 1 or
            tier["repetitions"] != 16 or tier["timeout_s_per_arm"] != 180 or
            tier["maximum_panel_wall_s"] != 2 * 16 * 180 or
            tier["pair_order"] != [["reference", "candidate"],
                                   ["candidate", "reference"]] * 8 or
            not tier["same_binary_required"] or
            tier["pair_fields"] != pair_fields or
            sorted(tier["expected_fields"]) != sorted(pair_fields) or
            tier["result_field"] != "pair_certificate" or
            tier["expected_result"] != tier["expected_fields"]["pair_certificate"]):
        raise ValueError("Tier 1 protocol identity, order, or limits differ")
    # The restore script must pin the same crypto snapshot as the frozen run.
    source = (HERE / "restore_crypto_source.py").read_text()
    for key in ("crypto_commit", "crypto_manifest", "crypto_source_tree",
                "crypto_rust_source_tree"):
        if '"{}": "{}"'.format(key, inputs[key]) not in source:
            raise ValueError("restore script pins another crypto " + key)
    if check_snapshot:
        ensure_snapshot()
    raw = {name: load(CANONICAL / (name + ".json")) for name in RUNS}
    for name in RUNS:
        record = load(CANONICAL / (name + ".record.json"))
        if (record["exit_code"] != 0 or record["execution_status"] != "completed" or
                record["raw_result_sha256"] != digest(CANONICAL / (name + ".json")) or
                record["host"]["source_sha256"] != bound["native_source"] or
                record["mode"] != raw[name]["index_mode"]):
            raise ValueError("frozen run record differs: " + name)
    certificates = {hashlib.sha256(canonical({k: row[k] for k in PAIR_FIELDS})).hexdigest()
                    for row in raw.values()}
    if certificates != {tier["expected_result"]}:
        raise ValueError("six frozen rows do not share the pair certificate")
    expected = tier["expected_fields"]
    reference, candidate = raw[RUNS[0]], raw[RUNS[1]]
    for row in raw.values():
        mode_rows = [r for r in raw.values() if r["index_mode"] == row["index_mode"]]
        if any(r[k] != row[k] for r in mode_rows for k in ARM_FIELDS):
            raise ValueError("frozen rows of one mode disagree on an arm field")
        timing = {k: int(v) for k, v in row["timing_ns"].items()}
        if (row["native_source_sha256"] != bound["native_source"] or
                row["status"] != expected["status"] or
                row["curve_id"] != expected["curve_id"] or
                row["workload_id"] != expected["workload_id"] or
                row["input_representatives_sha256"] != expected["input_sha256"] or
                str(row["index_pair_states_examined"]) != expected["indexed_states"] or
                str(row["target_states_scanned"]) != expected["target_states"] or
                row["native_s3_generator_target_control"]["status"] != "PASS" or
                row["peak_rss_bytes"] > 1024 << 20 or
                timing["target_query_preparation"] + timing["target_s3_batch"] +
                timing["target_partner_check"] > timing["target_pdp_and_native_check"] or
                timing["target_cycle_canonical"] + timing["target_exact_lookup"] >
                timing["target_partner_check"]):
            raise ValueError("frozen row correctness, cap, or phase differs")
    counts = {mode: (r["operation_counts"]["index_build"]["canonical_rotation_steps"],
                     r["operation_counts"]["target_pdp_and_native_check"]["canonical_rotation_steps"])
              for mode, r in ((reference["index_mode"], reference),
                              (candidate["index_mode"], candidate))}
    if counts != {"packed_bucket22": (328_000_000, 656_000_000),
                  "packed_bucket22_fastcanon": (19_127_078, 38_261_354)}:
        raise ValueError("frozen rotation counts differ")
    summary = load(CANONICAL / "summary.json")["medians"]
    exploratory = (summary["packed_bucket22"]["target_cycle_canonical_ns"] /
                   summary["packed_bucket22_fastcanon"]["target_cycle_canonical_ns"])
    frozen = tier["statistics"]["exploratory_reference"]["canonicalization_phase_ratio"]
    if "{:.7f}".format(exploratory) != frozen:
        raise ValueError("exploratory canonicalization ratio differs")
    return {"status": "PASS", "pair_certificate": tier["expected_result"],
            "tier1_protocol_sha256": digest(HERE / "tier1_protocol.json"),
            "exploratory_canonicalization_ratio": exploratory,
            "rotation_counts": counts}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
