#!/usr/bin/env python3
"""Pair a packed two-G witness index against the n83 L32 dictionary path."""

import hashlib
import json
import platform
import random
import resource
import statistics
import time
from pathlib import Path

import numpy as np

import curves
import field
from batch_x_only import batch_add_fixed_left
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_five_sum_batch import batch_add_pairs
from dyadic_n53_five_sum_dlp import build_g_pair_index
from dyadic_n83_compact_index import LOW_MASK, ROW_DTYPE, build_packed
from dyadic_n83_five_sum_stage import replay_hit, run_block
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1027"
WINDOW = 32
BLOCKS = 3
BLOCK_SIZE = 4096
BLOCK_SEEDS = (202609300831, 202609300832, 202609300833)


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


class PackedMapping:
    """Expose PackedIndex through the dictionary protocol used by replay."""

    def __init__(self, packed):
        self.packed = packed

    def __contains__(self, key):
        return self.packed.get(key) is not None

    def __getitem__(self, key):
        value = self.packed.get(key)
        if value is None:
            raise KeyError(key)
        return value


def packed_positions(packed, keys):
    """Vectorized lower-bound lookup; decode witnesses only for actual hits."""
    queries = np.zeros(len(keys), dtype=ROW_DTYPE)
    encoded = [key + 1 for key in keys]
    queries["hi"] = [value >> 64 for value in encoded]
    queries["lo"] = [value & LOW_MASK for value in encoded]
    positions = np.searchsorted(packed.rows, queries, side="left")
    safe = np.minimum(positions, len(packed.rows) - 1)
    hits = (positions < len(packed.rows)) & (
        packed.rows["hi"][safe] == queries["hi"]) & (
        packed.rows["lo"][safe] == queries["lo"])
    return positions, hits


def run_block_vectorized(onb, packed, q_base, labels, generator,
                         target_seed, alpha_g, alpha, order,
                         canonicalize, rng, first_triple=None):
    counted_field = CountingField(onb)
    curve = curves.Curve(counted_field)
    mapping = PackedMapping(packed)
    canonical_counts = {}
    started = time.perf_counter_ns()
    hits = 0
    relations = []
    for batch in range(BLOCK_SIZE // 512):
        triples = [tuple(q_base[rng.randrange(len(q_base))] for _ in range(3))
                   for _ in range(512)]
        if batch == 0 and first_triple is not None:
            triples[0] = first_triple
        first = batch_add_pairs(curve, [(a, b) for a, b, _ in triples])
        sums = batch_add_pairs(curve, list(zip(first, (t[2] for t in triples))))
        complements = batch_add_fixed_left(
            curve, alpha_g, [curve.neg(total) for total in sums])
        keys_and_shifts = [canonicalize.key_and_shift(curve, complement,
                                                      canonical_counts)
                           for complement in complements]
        positions, found = packed_positions(
            packed, [key for key, _ in keys_and_shifts])
        for item in np.flatnonzero(found):
            item = int(item)
            key, shift = keys_and_shifts[item]
            assert packed.get(key) is not None
            hits += 1
            relation = replay_hit(
                curve, mapping, complements[item], triples[item], key, shift,
                canonicalize, labels, generator, target_seed, alpha_g,
                alpha, order)
            relations.append({"attempt": batch * 512 + item + 1,
                              "relation": relation})
    elapsed = time.perf_counter_ns() - started
    return {"status": "bounded_ordinary_triple_queries",
            "attempts_including_failed": BLOCK_SIZE,
            "quotient_hits": hits,
            "verified_relations": relations,
            "batch_size": 512,
            "batches": BLOCK_SIZE // 512,
            "wall_ns": elapsed,
            "field_api_operations": dict(counted_field.counts),
            "canonical_operations": canonical_counts}


def main():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    baseline_path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    baseline = json.loads(baseline_path.read_text())
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target_seed = tuple(reference["workload"]["target"])
    assert baseline["curve_id"] == reference["curve_id"]
    lam = int(baseline["frobenius_eigenvalue_mod_r"])
    assert curve.mul(generator, lam) == curve.frob(generator)
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target_seed], WINDOW, lam, order)
    assert len(labels) == 10624
    assert digests["enumerated_set_sha256"] == baseline[
        "factor_base"]["enumerated_set_sha256"]
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    g_reps = [point for point in sorted(representatives) if labels[point][0] == 0]
    q_base = [point for point in sorted(labels) if labels[point][0] == 1]
    canonicalize = XOnlyCycle(onb)

    packed, packed_build = build_packed(curve, g_reps, g_base, canonicalize)
    packed_only_peak_rss_bytes = peak_rss_bytes()
    dictionary, dict_build = build_g_pair_index(
        curve, g_base, g_reps, canonicalize)
    assert len(packed) == len(dictionary) == baseline["index_build"][
        "quotient_keys"] == 80868
    assert dict_build["index_sha256"] == baseline["index_build"]["index_sha256"]
    dict_key_sha = hashlib.sha256(frozen(sorted(dictionary))).hexdigest()
    assert packed_build["key_sha256"] == dict_key_sha
    rng = random.Random(202609300834)
    sample_keys = [next(iter(dictionary)), *rng.sample(sorted(dictionary), 1000)]
    for key in sample_keys:
        representative, pair = packed.get(key)
        assert curve.add(*pair) == representative
        assert canonicalize.key_and_shift(curve, representative) == (key, 0)
        old_representative, old_pair = dictionary[key]
        assert curve.add(*old_pair) == old_representative
        assert canonicalize.key_and_shift(curve, old_representative) == (key, 0)

    alpha = baseline["workload"]["known_query_scalar_alpha"]
    alpha_g = curve.mul(generator, alpha)
    workload = {
        "curve_id": reference["curve_id"], "target": target_seed,
        "input_law": reference["workload"], "target_count": 1,
        "known_query_scalar_alpha": alpha,
        "doubling_window": WINDOW,
        "block_seeds": BLOCK_SEEDS,
        "block_size": BLOCK_SIZE,
        "batch_size": 512,
        "variants": ["dictionary", "packed_binary", "packed_vectorized"],
        "pairing": "same target and triple sample seed within each alternating-order block",
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    packed_mapping = PackedMapping(packed)
    rows = []
    for block, seed in enumerate(BLOCK_SEEDS, 1):
        order_of_variants = (
            ("dictionary", "packed_binary", "packed_vectorized"),
            ("packed_vectorized", "dictionary", "packed_binary"),
            ("packed_binary", "packed_vectorized", "dictionary"),
        )[block - 1]
        measured = {}
        for variant in order_of_variants:
            if variant == "packed_vectorized":
                measured[variant] = run_block_vectorized(
                    onb, packed, q_base, labels, generator, target_seed,
                    alpha_g, alpha, order, canonicalize, random.Random(seed))
            else:
                index = dictionary if variant == "dictionary" else packed_mapping
                measured[variant] = run_block(
                    onb, index, q_base, labels, generator, target_seed,
                    alpha_g, alpha, order, canonicalize, random.Random(seed))
        assert all(measured[variant]["attempts_including_failed"] == BLOCK_SIZE
                   for variant in order_of_variants)
        assert len({measured[variant]["quotient_hits"]
                    for variant in order_of_variants}) == 1
        assert measured["dictionary"]["verified_relations"] == measured[
            "packed_binary"]["verified_relations"] == measured[
                "packed_vectorized"]["verified_relations"]
        rows.append({"block": block, "triple_sample_seed": seed,
                     "execution_order": order_of_variants,
                     **measured,
                     "dictionary_wall_over_packed_binary_wall": measured[
                         "dictionary"]["wall_ns"] / measured[
                             "packed_binary"]["wall_ns"],
                     "dictionary_wall_over_packed_vectorized_wall": measured[
                         "dictionary"]["wall_ns"] / measured[
                             "packed_vectorized"]["wall_ns"]})
    first_key = next(key for key in packed.keys() if key != -1)
    representative, pair = packed.get(first_key)
    assert curve.add(*pair) == representative
    planted_points = []
    seen_x = set()
    for point in q_base:
        if point[0] not in seen_x:
            planted_points.append(point)
            seen_x.add(point[0])
        if len(planted_points) == 3:
            break
    assert len(planted_points) == 3
    planted_triple = tuple(planted_points)
    planted_sum = curve.add(curve.add(planted_triple[0], planted_triple[1]),
                            planted_triple[2])
    planted_target = curve.add(representative, planted_sum)
    planted_complement = curve.add(planted_target, curve.neg(planted_sum))
    planted_key, planted_shift = canonicalize.key_and_shift(
        curve, planted_complement)
    assert planted_key == first_key
    _, vectorized_planted_hit = packed_positions(packed, [planted_key])
    assert vectorized_planted_hit.tolist() == [True]
    planted_relation = replay_hit(
        curve, packed_mapping, planted_complement, planted_triple,
        planted_key, planted_shift, canonicalize, labels, generator,
        target_seed, planted_target, None, order)
    planted_vectorized_query = run_block_vectorized(
        onb, packed, q_base, labels, generator, target_seed,
        planted_target, None, order, canonicalize,
        random.Random(202609300835), first_triple=planted_triple)
    assert planted_vectorized_query["verified_relations"][0]["attempt"] == 1
    assert planted_vectorized_query["verified_relations"][0]["relation"] == (
        planted_relation)
    report = {
        "kind": "n83_L32_packed_two_G_pair_index_paired_five_sum_query_stage",
        "scope": "exact packed/dictionary G-pair key equality and sampled witness replay; paired bounded ordinary triples, no natural relation yield or DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": {"construction": baseline["factor_base"]["construction"],
                        "nominal_seed_columns": 2,
                        "doubling_window": WINDOW,
                        "actual_usable_points_B_before_folding": len(labels),
                        "signed_frobenius_columns": len(representatives),
                        "effective_unknown_log_columns_after_dyadic_labels": 1,
                        **digests},
        "packed_build": packed_build,
        "packed_only_peak_rss_bytes_before_dictionary_build": packed_only_peak_rss_bytes,
        "dictionary_build": dict_build,
        "full_key_set_sha256": dict_key_sha,
        "sampled_witness_replays": len(sample_keys),
        "planted_positive_control": planted_relation,
        "planted_vectorized_query_control": planted_vectorized_query,
        "paired_blocks": rows,
        "median_dictionary_wall_over_packed_binary_wall": statistics.median(
            row["dictionary_wall_over_packed_binary_wall"] for row in rows),
        "median_dictionary_wall_over_packed_vectorized_wall": statistics.median(
            row["dictionary_wall_over_packed_vectorized_wall"] for row in rows),
        "total_ordinary_triples_per_variant": BLOCKS * BLOCK_SIZE,
        "ordinary_quotient_hits": sum(row["dictionary"]["quotient_hits"]
                                      for row in rows),
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_process_rss_bytes": peak_rss_bytes(),
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_n53_five_sum_dlp.py",
            "dyadic_n83_compact_index.py", "dyadic_n83_five_sum_stage.py",
            "dyadic_five_sum_batch.py", "batch_x_only.py",
            "compare_batch_x_only.py", "x_only_cycle.py", "curves.py",
            "field.py")},
        "reference_sha256": sha(reference_path),
        "baseline_sha256": sha(baseline_path),
    }
    out = HERE / "runs" / "n83_dyadic_five_sum_packed_stage.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"keys": len(packed),
                      "retained_array_bytes": packed_build["retained_array_bytes"],
                      "packed_build_seconds": packed_build["build_seconds"],
                      "dictionary_build_seconds": dict_build["build_seconds"],
                      "median_dictionary_wall_over_packed_binary_wall": report[
                          "median_dictionary_wall_over_packed_binary_wall"],
                      "median_dictionary_wall_over_packed_vectorized_wall": report[
                          "median_dictionary_wall_over_packed_vectorized_wall"],
                      "ordinary_hits": report["ordinary_quotient_hits"],
                      "peak_rss_bytes": report["peak_process_rss_bytes"]}))


if __name__ == "__main__":
    main()
