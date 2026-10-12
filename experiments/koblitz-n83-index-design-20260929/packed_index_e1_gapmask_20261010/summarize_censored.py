#!/usr/bin/env python3
"""Validate completed N83 gap-mask arms while preserving censored runs."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import run


HERE = Path(__file__).resolve().parent
PAIR_FIELDS = (
    "curve_id", "workload_id", "factor_base_enumerated_set_sha256",
    "input_representatives_sha256", "target_count",
    "index_pair_states_examined", "index_satisfiable_s3_states",
    "index_distinct_root_keys", "root_table_slots_or_records",
    "target_states_scanned", "target_state_orientations_tested",
    "target_partner_roots", "target_table_hits", "target_root_windows",
    "lookup_sample", "relation", "status",
    "native_s3_generator_target_control", "verified_single_target_dlp",
    "root_table_hash_probes", "root_table_tagged_singleton_buckets",
    "target_singleton_tag_rejections",
)
PHASES = ("setup", "index_build", "target_pdp_and_native_check")


def same_noncanonical_ops(left, right):
    return all(
        {k: v for k, v in left["operation_counts"][phase].items()
         if k != "canonical_rotation_steps"} ==
        {k: v for k, v in right["operation_counts"][phase].items()
         if k != "canonical_rotation_steps"}
        for phase in PHASES
    )


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    stage = json.loads((HERE / "stage_manifest.json").read_text())
    assert run.digest(protocol_path) == stage["stage_protocol_sha256"]
    assert run.digest(HERE / "native_packed_index.rs") == protocol["inputs_sha256"]["native_source"]
    assert run.digest(HERE / "run.py") == protocol["inputs_sha256"]["runner"]
    assert stage["workload_id"] == protocol["workload_id"]

    rows = []
    completed = []
    for number, mode in enumerate(run.MODES, 1):
        stem = f"run_{number}_{mode}"
        record = json.loads((HERE / f"{stem}.record.json").read_text())
        assert record["mode"] == mode and record["sequence_number"] == number
        assert record["host"]["source_sha256"] == protocol["inputs_sha256"]["native_source"]
        raw_path = HERE / f"{stem}.json"
        row = {
            "sequence_number": number,
            "mode": mode,
            "execution_status": record["execution_status"],
            "stage_status": None,
            "target_stage_ns": None,
            "target_cycle_canonical_ns": None,
            "target_exact_lookup_ns": None,
            "index_build_ns": None,
            "peak_rss_bytes": None,
            "table_allocated_bytes": None,
            "index_canonical_rotations": None,
            "target_canonical_rotations": None,
        }
        if record["execution_status"] == "completed":
            assert raw_path.is_file() and run.digest(raw_path) == record["raw_result_sha256"]
            result = json.loads(raw_path.read_text())
            assert result["native_source_sha256"] == protocol["inputs_sha256"]["native_source"]
            assert result["stage_protocol_sha256"] == run.digest(protocol_path)
            assert result["workload_id"] == stage["workload_id"]
            assert result["root_table_record_bytes"] == 16
            assert result["peak_rss_bytes"] <= stage["peak_rss_cap_mib"] * 1024**2
            assert result["status"] == "state_cap_no_relation"
            assert result["native_s3_generator_target_control"]["status"] == "PASS"
            row.update({
                "stage_status": result["status"],
                "target_stage_ns": int(result["timing_ns"]["target_pdp_and_native_check"]),
                "target_cycle_canonical_ns": int(result["timing_ns"]["target_cycle_canonical"]),
                "target_exact_lookup_ns": int(result["timing_ns"]["target_exact_lookup"]),
                "index_build_ns": int(result["timing_ns"]["index_build"]),
                "peak_rss_bytes": result["peak_rss_bytes"],
                "table_allocated_bytes": result["root_table_allocated_bytes"],
                "index_canonical_rotations": result["operation_counts"]["index_build"]["canonical_rotation_steps"],
                "target_canonical_rotations": result["operation_counts"]["target_pdp_and_native_check"]["canonical_rotation_steps"],
            })
            completed.append((mode, result))
        else:
            assert not raw_path.exists() and record["raw_result_sha256"] is None
        rows.append(row)

    reference = next(result for mode, result in completed if mode == run.REFERENCE)
    mismatches = {}
    for mode, result in completed:
        wrong = [field for field in PAIR_FIELDS if result[field] != reference[field]]
        if wrong or not same_noncanonical_ops(result, reference):
            mismatches[mode] = wrong + ([] if same_noncanonical_ops(result, reference)
                                       else ["noncanonical_operation_counts"])
    assert not mismatches, mismatches
    assert any(mode == run.CANDIDATE for mode, _ in completed)
    def unique_rotations(mode, phase):
        values = {result["operation_counts"][phase]["canonical_rotation_steps"]
                  for arm, result in completed if arm == mode}
        assert len(values) == 1, (mode, phase, values)
        return values.pop()
    index_ref = unique_rotations(run.REFERENCE, "index_build")
    index_new = unique_rotations(run.CANDIDATE, "index_build")
    target_ref = unique_rotations(run.REFERENCE, "target_pdp_and_native_check")
    target_new = unique_rotations(run.CANDIDATE, "target_pdp_and_native_check")
    assert 0 < index_new < index_ref and 0 < target_new < target_ref
    certificate = hashlib.sha256(run.canonical(
        {field: reference[field] for field in PAIR_FIELDS})).hexdigest()
    summary = {
        "kind": "n83_packed_root_gapmask_censored_stage_comparison",
        "status": "validated_censored_stage_comparison",
        "proposal_id": run.PROPOSAL_ID,
        "candidate_id": None, "run_id": None,
        "curve_id": stage["curve_id"], "workload_id": stage["workload_id"],
        "source_sha256": protocol["inputs_sha256"]["native_source"],
        "protocol_sha256": run.digest(protocol_path),
        "summarizer_sha256": run.digest(Path(__file__)),
        "pair_certificate_sha256": certificate,
        "invariant_mismatches": mismatches,
        "completed_rows": len(completed),
        "censored_rows": len(rows) - len(completed),
        "paired_rows": rows,
        "canonical_rotations": {
            "index_build_reference": index_ref,
            "index_build_candidate": index_new,
            "target_reference": target_ref,
            "target_candidate": target_new,
            "target_reduction_percent": str((Decimal(target_ref - target_new) * 100 /
                                             Decimal(target_ref)).quantize(Decimal("0.01"))),
        },
        "cpu_timing_claim": "exploratory stage costs; one reference timeout and no host-isolation receipt",
        "ic_online_ms": None, "rho_online_ms": None, "online_speedup": None,
    }
    run.save(HERE / "summary.json", summary)
    print(json.dumps({"status": summary["status"],
                      "completed_rows": len(completed),
                      "censored_rows": summary["censored_rows"],
                      "canonical_rotations": summary["canonical_rotations"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
