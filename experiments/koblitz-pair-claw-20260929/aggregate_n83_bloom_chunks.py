#!/usr/bin/env python3
"""Aggregate exact n83 chunk receipts without dropping failed work."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
FINITE = HERE / "n83_knownlog_conditional_screen.json"
sys.path.insert(0, str(CODEGEN))

import curves
import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    finite = json.loads(FINITE.read_text())
    records = []
    for path in args.receipts:
        record = json.loads(path.read_text())
        if record["kind"] not in {
                "n83_public_target_bloom_exact_replay_chunk",
                "n83_public_target_bloom_chunk_failed"}:
            raise ValueError(f"not a terminal chunk receipt: {path}")
        records.append((path, record))
    first = records[0][1]
    curve_id = first["curve_id"]
    assert curve_id == finite["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    if first["kind"] != "n83_public_target_bloom_exact_replay_chunk":
        raise ValueError("need at least one completed chunk to fix identity")
    expected = {
        key: first[key] for key in (
            "curve_id", "curve_identity_record", "public_target",
            "compiled_binary_sha256",
            "native_source_sha256", "native_pairs_source_sha256",
            "key_and_log_file_sha256", "schedule_receipt_sha256",
            "rho_reference_receipt_sha256", "bits_per_key", "hashes")
    }
    assert first["isogeny"] == "none"
    assert first["factor_base"]["enumerated_set_sha256"] == finite[
        "factor_base_enumerated_set_sha256"]
    assert first["factor_base"]["actual_usable_points_B_before_folding"] == finite[
        "actual_usable_points_B_before_folding"]
    rectangles = []
    table_groups = {}
    completed = []
    failed = []
    for path, record in records:
        if record["curve_id"] != curve_id:
            raise ValueError(f"curve mismatch: {path}")
        if record["kind"] == "n83_public_target_bloom_chunk_failed":
            failed.append({
                "receipt": str(path),
                "receipt_sha256": sha(path),
                "query_start": record["query_start"],
                "query_count": record["query_count"],
                "table_start": record.get("table_start", 0),
                "table_descriptors": record["table_descriptors"],
                "bits_per_key": record.get("bits_per_key"),
                "hashes": record.get("hashes"),
                "reason": record.get("stderr"),
                "charged_work_unknown": True,
            })
            continue
        if record["isogeny"] != "none" or any(
                record[key] != value for key, value in expected.items()):
            raise ValueError(f"algorithm, workload, or source mismatch: {path}")
        if record["factor_base"]["enumerated_set_sha256"] != first[
                "factor_base"]["enumerated_set_sha256"]:
            raise ValueError(f"factor-base mismatch: {path}")
        native = record["native_result"]
        if (record["query_start"] != native["query_start"] or
                record["query_count"] != native["query_pairs"] or
                record["table_descriptors"] != native["table_descriptors"] or
                record["table_start"] != native["table_start"]):
            raise ValueError(f"native range mismatch: {path}")
        if (native["batch_size"] != first["native_result"]["batch_size"] or
                native["bloom_bits_per_key"] != record["bits_per_key"] or
                native["bloom_hashes"] != record["hashes"]):
            raise ValueError(f"native solver parameters mismatch: {path}")
        q_start = record["query_start"]
        q_end = q_start + record["query_count"]
        t_start = record["table_start"]
        t_end = t_start + record["table_descriptors"]
        rectangles.append((t_start, t_end, q_start, q_end, path))
        table_groups.setdefault((t_start, t_end), []).append((q_start, q_end))
        completed.append((path, record))
    for i, (t0, t1, q0, q1, path) in enumerate(rectangles):
        for s0, s1, r0, r1, other in rectangles[:i]:
            if max(t0, s0) < min(t1, s1) and max(q0, r0) < min(q1, r1):
                raise ValueError(f"overlapping table/query rectangles: {other}, {path}")
    groups = sorted(table_groups)
    for (t0, t1), (s0, s1) in zip(groups, groups[1:]):
        if s0 < t1:
            raise ValueError("partially overlapping table shards are unsupported")
    group_prefixes = []
    for t_range in groups:
        prefix = 0
        for q_start, q_end in sorted(table_groups[t_range]):
            if q_start != prefix:
                break
            prefix = q_end
        group_prefixes.append((*t_range, prefix))
    contiguous_table_prefix_end = 0
    common_query_prefix_end = None
    for t_start, t_end, q_prefix in group_prefixes:
        if t_start != contiguous_table_prefix_end or not q_prefix:
            break
        contiguous_table_prefix_end = t_end
        common_query_prefix_end = (q_prefix if common_query_prefix_end is None
                                   else min(common_query_prefix_end, q_prefix))
    common_query_prefix_end = common_query_prefix_end or 0
    completed_query_pairs_with_repeats = sum(
        q_end - q_start for _, _, q_start, q_end, _ in rectangles)
    work_known = not failed
    field_calls = (sum(int(record["native_field_add_mul_sqr_call_model"])
                       for _, record in completed) if work_known else None)
    total_pair_evaluations = (sum(
        2 * record["table_descriptors"] + record["query_count"]
        for _, record in completed) if work_known else None)
    online_seconds = (sum(record["target_online_seconds"]
                          for _, record in completed) if work_known else None)
    build_seconds = (sum(record["target_independent_filter_build_seconds"]
                         for _, record in completed) if work_known else None)
    certificates = [certificate for _, record in completed
                    for certificate in record[
                        "verified_public_target_relations"]]
    curve = curves.Curve(field.Onb(83))
    generator = tuple(first["curve_identity_record"]["curve"]["generator"])
    target = tuple(first["public_target"])
    order = first["curve_identity_record"]["curve"]["subgroup_order"]
    assert curve.onCurve(generator) and curve.onCurve(target)
    assert curve.mul(generator, order) is None
    for certificate in certificates:
        assert certificate["independent_scalar_replay"] is True
        assert curve.mul(generator, certificate["recovered_scalar"]) == target
        assert str(certificate["recovered_scalar"]) == finite[
            "n83_same_target_rho_reference"]["recovered_scalar"]
    solved = bool(certificates)
    f = contiguous_table_prefix_end / finite[
        "signed_frobenius_zero_pair_key_cap_before_accidental_collisions"]
    t = common_query_prefix_end / finite["unordered_pair_domain"]
    mu = finite[
        "heuristic_mean_four_point_multiset_relations_for_one_target"]
    model_success = -math.expm1(-mu * (1 - (1 - f * t) ** 6))
    report = {
        "kind": "n83_public_target_bloom_chunk_cumulative_accounting",
        "scope": "all supplied terminal chunks, including zero-hit work; model success is separate from measured yield",
        "proposal_id": "Q1049", "candidate_id": None,
        "curve_id": curve_id,
        "curve_identity_record": first["curve_identity_record"],
        "isogeny": "none",
        "public_target": first["public_target"],
        "factor_base_enumerated_set_sha256": first[
            "factor_base"]["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": first[
            "factor_base"]["actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": first[
            "factor_base"]["signed_frobenius_columns"],
        "table_descriptor_prefix_end": contiguous_table_prefix_end,
        "bits_per_key": first["bits_per_key"],
        "hashes": first["hashes"],
        "batch_size": first["native_result"]["batch_size"],
        "completed_chunks": [{
            "receipt": str(path), "receipt_sha256": sha(path),
            "query_start": record["query_start"],
            "query_count": record["query_count"],
            "table_start": record["table_start"],
            "table_descriptors": record["table_descriptors"],
            "verified_relations": len(record[
                "verified_public_target_relations"]),
            "field_calls": record["native_field_add_mul_sqr_call_model"],
        } for path, record in completed],
        "failed_chunks_with_unknown_work": failed,
        "completed_table_query_rectangles": [
            [t0, t1, q0, q1] for t0, t1, q0, q1, _ in rectangles],
        "completed_query_pair_evaluations": completed_query_pairs_with_repeats,
        "common_query_prefix_end_for_table_prefix": common_query_prefix_end,
        "model_success_probability_for_contiguous_prefix": model_success,
        "verified_relation_count": len(certificates),
        "verified_public_target_dlp_from_quotient_table": solved,
        "recovered_scalar_if_solved": (
            str(certificates[0]["recovered_scalar"]) if solved else None),
        "cumulative_native_field_add_mul_sqr_calls": (
            str(field_calls) if work_known else None),
        "cumulative_native_field_add_mul_sqr_calls_log2": (
            math.log2(field_calls) if field_calls else None),
        "cumulative_pair_evaluations": (
            str(total_pair_evaluations) if work_known else None),
        "cumulative_target_online_seconds": online_seconds,
        "cumulative_target_independent_filter_build_seconds":
            build_seconds,
        "complete_end_to_end_work_log2": None,
        "work_boundary": "field add, multiply, and square calls from every supplied completed chunk; failed chunks with unknown phase counts make cumulative work unknown; bit-level keying, hashing, memory traffic, and final verification remain outside this count",
        "rho_reference": finite["n83_same_target_rho_reference"],
        "finite_support_screen_sha256": sha(FINITE),
        "source_sha256": sha(Path(__file__)),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "completed_chunks": len(completed),
        "failed_chunks": len(failed),
        "table_descriptor_prefix_end": contiguous_table_prefix_end,
        "common_query_prefix_end_for_table_prefix": common_query_prefix_end,
        "verified_relation_count": len(certificates),
        "verified_public_target_dlp": solved,
        "cumulative_field_calls_log2": report[
            "cumulative_native_field_add_mul_sqr_calls_log2"],
    }))


if __name__ == "__main__":
    main()
