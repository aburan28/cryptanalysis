#!/usr/bin/env python3
"""Report Q1051 first-hit work quantiles from the frozen finite-support model.

These are conditional predictions. A completed public-target rectangle is the
unit of work; the native program finishes a rectangle even if it finds a hit.
No field-call result here is a measured complete discrete logarithm.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_large_knownlog_base_screen.json"
OUTPUT = HERE / "n83_large_orbit_solve_work.json"
QUANTILES = ("0.5", "0.8", "0.9", "0.95", "0.99")


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def success_probability(chunks, *, mean_relations, table_fraction,
                        query_fraction_per_chunk):
    covered_pair_fraction = table_fraction * chunks * query_fraction_per_chunk
    assert 0 <= covered_pair_fraction <= 1
    return -math.expm1(-mean_relations *
                       (1 - (1 - covered_pair_fraction) ** 6))


def main():
    screen = json.loads(SCREEN.read_text())
    identity = screen["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == screen["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert screen["proposal_id"] == "Q1051"
    assert screen["candidate_id"] is None and screen["isogeny"] == "none"
    base = screen["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 8000204
    assert base["signed_frobenius_columns"] == 48194
    assert base["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    table = screen["table_descriptors"]
    reps = screen["query_representatives_per_chunk"]
    lift = base["signed_frobenius_orbit_size"]
    assert table == reps == 1 << 31 and lift == 166
    max_chunks = screen["cross_orbit_query_representative_domain"] // reps
    assert max_chunks == 89
    table_fraction = table / screen[
        "zero_pair_key_cap_before_accidental_collisions"]
    query_fraction_per_chunk = reps * lift / screen[
        "unordered_query_pair_domain"]
    mean = screen["heuristic_mean_four_point_multisets"]
    inversion_equivalent_calls = 90 * (
        2 * math.ceil(table / 1024) + 2 * math.ceil(reps / 8))
    calls_per_chunk = (26 * table + 13 * reps + 13 * reps * lift +
                       inversion_equivalent_calls)
    assert math.isclose(
        math.log2(screen["query_chunks_for_95pct_model"] * calls_per_chunk),
        screen["conditional_field_add_mul_sqr_calls_total_log2"])
    cdf = [0.0] + [success_probability(
        chunk, mean_relations=mean, table_fraction=table_fraction,
        query_fraction_per_chunk=query_fraction_per_chunk)
        for chunk in range(1, max_chunks + 1)]
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
    assert cdf[58] < 0.95 <= cdf[59]
    first_hit_mass = [cdf[i] - cdf[i - 1]
                      for i in range(1, max_chunks + 1)]
    success_by_exhaustion = cdf[-1]
    expected_chunks_given_success = sum(
        chunk * chance for chunk, chance in
        enumerate(first_hit_mass, 1)) / success_by_exhaustion
    quantiles = {}
    for label in QUANTILES:
        probability = float(label)
        chunk = next((i for i in range(1, max_chunks + 1)
                      if cdf[i] >= probability), None)
        quantiles[label] = {
            "completed_chunks": chunk,
            "model_success_probability": cdf[chunk] if chunk else None,
            "cumulative_field_calls": str(chunk * calls_per_chunk)
            if chunk else None,
            "cumulative_field_calls_log2":
                math.log2(chunk * calls_per_chunk) if chunk else None,
        }
    full_chunk_projected_days = (
        screen["projected_days_if_bounded_14worker_speedup_holds_at_2pow31_filter"] /
        screen["query_chunks_for_95pct_model"])
    report = {
        "kind": "n83_q1051_first_hit_conditional_work_distribution",
        "scope": "frozen finite-support heuristic; no measured natural relation or complete IC DLP",
        "proposal_id": "Q1051", "candidate_id": None,
        "curve_id": curve_id, "isogeny": "none",
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": base[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": base["signed_frobenius_columns"],
        "field_call_boundary": "native field add, multiply, and square calls plus 90 such calls per modeled inversion; includes a fresh table build and exact replay for each completed chunk; excludes base construction, keying, Bloom operations, memory traffic, and independent scalar replay",
        "modeled_field_calls_per_completed_chunk": str(calls_per_chunk),
        "modeled_field_calls_per_completed_chunk_log2": math.log2(
            calls_per_chunk),
        "first_hit_quantiles": quantiles,
        "maximum_disjoint_full_chunks": max_chunks,
        "model_success_probability_after_all_full_chunks":
            success_by_exhaustion,
        "model_probability_no_hit_after_all_full_chunks":
            1 - success_by_exhaustion,
        "expected_completed_chunks_conditional_on_hit_within_full_support":
            expected_chunks_given_success,
        "expected_field_calls_conditional_on_hit_within_full_support_log2":
            math.log2(expected_chunks_given_success * calls_per_chunk),
        "all_full_chunks_field_calls_log2": math.log2(
            max_chunks * calls_per_chunk),
        "projected_days_per_full_chunk_if_bounded_worker_speedup_transfers":
            full_chunk_projected_days,
        "projected_days_at_median_model_success_if_speedup_transfers":
            quantiles["0.5"]["completed_chunks"] * full_chunk_projected_days,
        "projected_days_at_95pct_model_success_if_speedup_transfers":
            quantiles["0.95"]["completed_chunks"] * full_chunk_projected_days,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "The success distribution assumes uniform finite-support relation placement; it is not an observed natural-target yield rate.",
            "The native run processes a whole rectangle before reporting a hit, so each first-hit quantile charges whole completed rectangles.",
            "The expected work is conditional on a hit within the 89 disjoint full chunks; the model leaves a positive no-hit probability.",
            "The wall-time projection transfers a 14-versus-8-worker speedup from a smaller filter and has not been measured on a full query chunk.",
            "The operation model is a specified stage boundary, not complete end-to-end IC work or a calibrated field-operation equivalent for rho.",
        ],
        "input_screen_sha256": hashlib.sha256(SCREEN.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "median_chunks": quantiles["0.5"]["completed_chunks"],
        "median_work_log2": quantiles["0.5"][
            "cumulative_field_calls_log2"],
        "p95_chunks": quantiles["0.95"]["completed_chunks"],
        "p95_work_log2": quantiles["0.95"][
            "cumulative_field_calls_log2"],
        "maximum_success_probability": success_by_exhaustion,
    }))


if __name__ == "__main__":
    main()
