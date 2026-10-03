#!/usr/bin/env python3
"""Check Q1058/Q1059 exact outcomes on one identical public-target rectangle."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
REFERENCE = RUNS / "n83_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json"
FAST = RUNS / "n83_fast_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json"
OUTPUT = RUNS / "n83_low_memory_smoke_paired.json"
EQUAL_NATIVE_FIELDS = (
    "actual_B", "table_descriptors", "table_start",
    "query_representatives", "query_start", "lifted_query_pairs",
    "query_workers", "representative_batch", "table_batch",
    "bloom_bits_per_key", "bloom_hashes", "bloom_bytes",
    "bloom_positive_queries", "duplicate_positive_keys",
    "exact_hit_keys", "exact_hit_queries", "false_positive_queries",
    "complement_identity_queries", "hits",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reference = json.loads(REFERENCE.read_text())
    fast = json.loads(FAST.read_text())
    assert reference["proposal_id"] == "Q1058"
    assert fast["proposal_id"] == "Q1059"
    assert all(row["candidate_id"] is None and row["isogeny"] == "none"
               for row in (reference, fast))
    assert reference["fast_keyer_enabled"] is False
    assert fast["fast_keyer_enabled"] is True
    for key in ("curve_id", "curve_identity_record", "public_target",
                "factor_base", "table_start", "table_descriptors",
                "query_start", "query_representatives", "lifted_query_pairs",
                "query_workers", "representative_batch", "bits_per_key",
                "hashes", "table_schedule", "query_representative_schedule",
                "native_source_sha256", "bloom_core_sha256",
                "native_pairs_sha256", "key_file_sha256",
                "schedule_receipt_sha256"):
        assert reference[key] == fast[key], key
    assert reference["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    base = reference["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 8000204
    assert base["signed_frobenius_columns"] == 48194
    assert base["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    assert reference["table_descriptors"] == 1 << 20
    assert reference["query_representatives"] == 1 << 14
    assert reference["query_start"] == 1 << 30
    assert reference["hashes"] == 10
    assert reference["native_field_add_mul_sqr_call_model"] == fast[
        "native_field_add_mul_sqr_call_model"]
    assert reference["verified_public_target_quotient_table_dlp"] is False
    assert fast["verified_public_target_quotient_table_dlp"] is False
    assert all(reference["native_result"][key] == fast["native_result"][key]
               for key in EQUAL_NATIVE_FIELDS)
    assert reference["native_result"]["exact_hit_queries"] == 0
    report = {
        "kind": "n83_q1058_q1059_identical_public_target_smoke_outcomes",
        "scope": "paired correctness control on one small rectangle; not a relation-yield or full-size speedup measurement",
        "proposal_ids": ["Q1058", "Q1059"], "candidate_id": None,
        "curve_id": reference["curve_id"], "isogeny": "none",
        "public_target": reference["public_target"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "table_start": reference["table_start"],
        "table_descriptors": reference["table_descriptors"],
        "query_start": reference["query_start"],
        "query_representatives": reference["query_representatives"],
        "exact_native_outcomes_identical": True,
        "equal_native_fields": list(EQUAL_NATIVE_FIELDS),
        "bloom_positive_queries": reference[
            "native_result"]["bloom_positive_queries"],
        "exact_hit_queries": 0,
        "reference_query_seconds": reference["native_result"]["query_seconds"],
        "fast_query_seconds": fast["native_result"]["query_seconds"],
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "reference_receipt_sha256": sha(REFERENCE),
        "fast_receipt_sha256": sha(FAST),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"identical": True,
                      "bloom_positive_queries": report["bloom_positive_queries"],
                      "exact_hit_queries": 0}))


if __name__ == "__main__":
    main()
