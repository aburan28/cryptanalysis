#!/usr/bin/env python3
"""Aggregate n=83 query-orbit rectangles and retain failed-work uncertainty."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
FINITE = HERE / "n83_knownlog_conditional_screen.json"
SCREEN = HERE / "n83_query_orbit_reuse_screen.json"
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
    screen = json.loads(SCREEN.read_text())
    records = []
    for path in args.receipts:
        record = json.loads(path.read_text())
        if record["kind"] not in {
                "n83_public_target_orbit_query_exact_replay_chunk",
                "n83_public_target_orbit_query_chunk_failed"}:
            raise ValueError(f"not a terminal orbit-query chunk: {path}")
        records.append((path, record))
    first = records[0][1]
    if first["kind"] != "n83_public_target_orbit_query_exact_replay_chunk":
        raise ValueError("need one completed chunk to fix identity")
    curve_id = first["curve_id"]
    assert curve_id == finite["curve_id"] == screen[
        "curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert first["isogeny"] == "none"
    assert first["factor_base"]["enumerated_set_sha256"] == screen[
        "factor_base_enumerated_set_sha256"]
    expected = {key: first[key] for key in (
        "curve_id", "curve_identity_record", "public_target",
        "compiled_binary_sha256", "native_source_sha256",
        "bloom_core_sha256", "native_pairs_sha256",
        "key_file_sha256", "schedule_receipt_sha256",
        "rho_reference_receipt_sha256", "bits_per_key", "hashes",
        "representative_batch", "query_workers", "table_schedule",
        "query_representative_schedule")}
    rectangles = []
    table_groups = {}
    completed = []
    failed = []
    for path, record in records:
        if record["curve_id"] != curve_id:
            raise ValueError(f"curve mismatch: {path}")
        if record["kind"] == "n83_public_target_orbit_query_chunk_failed":
            failed.append({
                "receipt": str(path), "receipt_sha256": sha(path),
                "table_start": record["table_start"],
                "table_descriptors": record["table_descriptors"],
                "query_start": record["query_start"],
                "query_representatives": record["query_representatives"],
                "reason": record.get("stderr"),
                "charged_work_unknown": True,
            })
            continue
        if record["isogeny"] != "none" or any(
                record[key] != value for key, value in expected.items()):
            raise ValueError(f"algorithm, source, or workload mismatch: {path}")
        if record["factor_base"]["enumerated_set_sha256"] != first[
                "factor_base"]["enumerated_set_sha256"]:
            raise ValueError(f"factor-base mismatch: {path}")
        native = record["native_result"]
        for key in ("table_start", "table_descriptors", "query_start",
                    "query_representatives", "lifted_query_pairs"):
            if record[key] != native[key]:
                raise ValueError(f"native count mismatch: {path}: {key}")
        if (native["bloom_bits_per_key"] != record["bits_per_key"] or
                native["bloom_hashes"] != record["hashes"] or
                native["representative_batch"] != record[
                    "representative_batch"] or
                native["query_workers"] != record["query_workers"]):
            raise ValueError(f"native solver parameters mismatch: {path}")
        t0 = record["table_start"]
        t1 = t0 + record["table_descriptors"]
        q0 = record["query_start"]
        q1 = q0 + record["query_representatives"]
        rectangles.append((t0, t1, q0, q1, path))
        table_groups.setdefault((t0, t1), []).append((q0, q1))
        completed.append((path, record))
    for i, (t0, t1, q0, q1, path) in enumerate(rectangles):
        for s0, s1, r0, r1, other in rectangles[:i]:
            if max(t0, s0) < min(t1, s1) and max(q0, r0) < min(q1, r1):
                raise ValueError(
                    f"overlapping table/query rectangles: {other}, {path}")
    groups = sorted(table_groups)
    for (t0, t1), (s0, s1) in zip(groups, groups[1:]):
        if s0 < t1:
            raise ValueError("partially overlapping table shards unsupported")
    group_prefixes = []
    for t_range in groups:
        prefix = 0
        for q0, q1 in sorted(table_groups[t_range]):
            if q0 != prefix:
                break
            prefix = q1
        group_prefixes.append((*t_range, prefix))
    table_prefix = 0
    common_query_prefix = None
    for t0, t1, qprefix in group_prefixes:
        if t0 != table_prefix or not qprefix:
            break
        table_prefix = t1
        common_query_prefix = (qprefix if common_query_prefix is None else
                               min(common_query_prefix, qprefix))
    common_query_prefix = common_query_prefix or 0
    work_known = not failed
    field_calls = (sum(int(record["native_field_add_mul_sqr_call_model"])
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
    f = table_prefix / finite[
        "signed_frobenius_zero_pair_key_cap_before_accidental_collisions"]
    t = (common_query_prefix * 166) / finite[
        "unordered_pair_domain"]
    mu = finite[
        "heuristic_mean_four_point_multiset_relations_for_one_target"]
    model_success = -math.expm1(-mu * (1 - (1 - f * t) ** 6))
    report = {
        "kind": "n83_public_target_orbit_query_chunk_cumulative_accounting",
        "scope": "all supplied terminal rectangles; failed work unknown; model success separate from measured yield",
        "proposal_id": "Q1050", "candidate_id": None,
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
        "completed_chunks": [{
            "receipt": str(path), "receipt_sha256": sha(path),
            "table_start": record["table_start"],
            "table_descriptors": record["table_descriptors"],
            "query_start": record["query_start"],
            "query_representatives": record[
                "query_representatives"],
            "verified_relations": len(record[
                "verified_public_target_relations"]),
            "field_calls": record["native_field_add_mul_sqr_call_model"],
        } for path, record in completed],
        "failed_chunks_with_unknown_work": failed,
        "completed_table_query_rectangles": [
            [t0, t1, q0, q1] for t0, t1, q0, q1, _ in rectangles],
        "table_descriptor_prefix_end": table_prefix,
        "common_query_representative_prefix_end_for_table_prefix":
            common_query_prefix,
        "lifted_query_pair_prefix_per_table_descriptor": (
            common_query_prefix * 166),
        "model_success_probability_for_common_prefix": model_success,
        "verified_relation_count": len(certificates),
        "verified_public_target_dlp_from_orbit_query": solved,
        "recovered_scalar_if_solved": (
            str(certificates[0]["recovered_scalar"]) if solved else None),
        "cumulative_native_field_add_mul_sqr_calls": (
            str(field_calls) if work_known else None),
        "cumulative_native_field_add_mul_sqr_calls_log2": (
            math.log2(field_calls) if field_calls else None),
        "cumulative_target_online_seconds": online_seconds,
        "cumulative_target_independent_filter_build_seconds":
            build_seconds,
        "complete_end_to_end_work_log2": None,
        "work_boundary": "field add, multiply, and square calls from every supplied completed chunk; failed chunks with unknown phase counts make cumulative work unknown; keying, Bloom, memory, base setup, and final verification remain outside this model",
        "same_target_rho_reference": finite[
            "n83_same_target_rho_reference"],
        "finite_support_screen_sha256": sha(FINITE),
        "orbit_screen_sha256": sha(SCREEN),
        "source_sha256": sha(Path(__file__)),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "completed_chunks": len(completed),
        "failed_chunks": len(failed),
        "table_descriptor_prefix_end": table_prefix,
        "common_query_representative_prefix_end": common_query_prefix,
        "verified_relation_count": len(certificates),
        "verified_public_target_dlp": solved,
        "cumulative_field_calls_log2": report[
            "cumulative_native_field_add_mul_sqr_calls_log2"],
    }))


if __name__ == "__main__":
    main()
