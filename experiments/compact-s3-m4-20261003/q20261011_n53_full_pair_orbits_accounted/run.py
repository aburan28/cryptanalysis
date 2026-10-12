#!/usr/bin/env python3
"""Enumerate complete N53 signed-Frobenius pair-orbit states and relations."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PRIOR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PRIOR))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
from chain_s3 import square_destinations  # noqa: E402
from enumerate_weight_base import orbit  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from probe_n53_relation import base_and_columns  # noqa: E402
from probe_n53_table import pair_sample, witness  # noqa: E402
from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
FREEZE = HERE / "freeze.json"
OUT = HERE / "measurement.json"
STAGE = PARENT / "runs/n53_ordinary_frozen.json"
ARCHIVE = PARENT / "bases/n53_weight3_orbits.json.gz"
REFERENCE = PARENT / "runs/n53_ordinary_matched_pair_table.json"
PREVIOUS = PARENT / "q20261011_n53_table2m/measurement.json"
INTERRUPTED = PARENT / "q20261011_n53_full_pair_orbits/attempt_status.json"
CANDIDATE = PRIOR / "candidates/IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirectISO0h7c80ef394c64.json"
SOURCES = [
    Path(__file__),
    HERE / "indexcalc.py",
    HERE / "launch.sh",
    PRIOR / "probe_n53_table.py",
    PRIOR / "probe_n53_relation.py",
    PRIOR / "orbit_key.py",
    PARENT / "run_probe.py",
    PARENT / "enumerate_weight_base.py",
    PARENT / "chain_s3.py",
    Path(field.__file__),
    Path(curves.__file__),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_inputs() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    stage = json.loads(STAGE.read_text())
    reference = json.loads(REFERENCE.read_text())
    previous = json.loads(PREVIOUS.read_text())
    interrupted = json.loads(INTERRUPTED.read_text())
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    candidate = json.loads(CANDIDATE.read_text())
    assert protocol["curve_id"] == stage["curve_id"] == reference["curve_id"] == archive[
        "curve"]["curve_id"]
    assert protocol["workload_id"] == stage["workload_id"] == reference["workload_id"]
    assert protocol["isogeny"] == reference["isogeny"] == archive["isogeny"] == "none"
    assert protocol["factor_base_actual_B"] == reference["factor_base_actual_B"] == archive[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert protocol["factor_base_folded_columns_K"] == reference[
        "factor_base_folded_columns"] == archive["factor_base"]["signed_frobenius_columns"]
    assert protocol["factor_base_enumerated_set_sha256"] == reference[
        "factor_base_enumerated_set_sha256"] == archive["factor_base"]["enumerated_set_sha256"]
    assert candidate["factor_base"]["frobenius_eigenvalue_mod_r"] == protocol[
        "rank_accounting"]["frobenius_eigenvalue_mod_r"]
    assert candidate["curve"]["subgroup_order"] == protocol[
        "rank_accounting"]["modulus"]
    pdp = protocol["point_decomposition"]
    assert pdp["table_states"] == (
        protocol["factor_base_folded_columns_K"] *
        (protocol["factor_base_folded_columns_K"] + 1) // 2 * 2 * 53)
    assert pdp["query_seed"] == reference["query_seed"]
    assert pdp["query_sample_cap"] == reference["query_sample_cap"]
    assert previous["curve_id"] == protocol["curve_id"]
    assert previous["workload_id"] == protocol["workload_id"]
    assert previous["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    assert interrupted["attempt_status"] == "PRODUCER_INTERRUPTED_NO_RECEIPT"
    return {
        "protocol_sha256": sha(PROTOCOL),
        "stage_sha256": sha(STAGE),
        "archive_sha256": sha(ARCHIVE),
        "reference_sha256": sha(REFERENCE),
        "previous_sha256": sha(PREVIOUS),
        "interrupted_attempt_status_sha256": sha(INTERRUPTED),
        "candidate_sha256": sha(CANDIDATE),
        "sources_sha256": {str(path.relative_to(ROOT)): sha(path) for path in SOURCES},
        "public_target": stage["public_subgroup_target"],
        "python_version": platform.python_version(),
    }


class IncrementalRank:
    def __init__(self, modulus: int):
        self.modulus = modulus
        self.pivots: dict[int, dict[int, int]] = {}

    def add(self, row: dict[int, int]) -> bool:
        p = self.modulus
        vector = {c: value % p for c, value in row.items() if value % p}
        while vector:
            pivot = min(vector)
            old = self.pivots.get(pivot)
            if old is None:
                inverse = pow(vector[pivot], -1, p)
                self.pivots[pivot] = {c: value * inverse % p
                                      for c, value in vector.items()}
                return True
            multiplier = vector[pivot]
            for col, value in old.items():
                updated = (vector.get(col, 0) - multiplier * value) % p
                if updated:
                    vector[col] = updated
                else:
                    vector.pop(col, None)
        return False

    @property
    def rank(self) -> int:
        return len(self.pivots)


def factor_base_digest(onb, representatives) -> str:
    destinations = square_destinations(onb)
    keys = set()
    for representative in representatives:
        key = min(orbit(onb.toCoords(representative[0]), destinations))
        assert key not in keys
        keys.add(key)
    return hashlib.sha256(b"".join(
        key.to_bytes(7, "little") for key in sorted(keys))).hexdigest()


def row_from_relation(relation: dict, orbit_key: OrbitKey,
                      key_to_column: dict[int, int], curve,
                      eigen: int, modulus: int) -> dict[int, int]:
    row = {len(key_to_column): modulus - 1}
    for encoded in relation["points"]:
        point = tuple(encoded)
        key, exponent, sign = orbit_key.canonical(point)
        assert key in key_to_column
        canonical_point = curve.frob(point, exponent)
        if sign < 0:
            canonical_point = curve.neg(canonical_point)
        assert canonical_point == orbit_key.point_from_key(key)
        coefficient = sign * pow(eigen, -exponent, modulus)
        col = key_to_column[key]
        row[col] = (row.get(col, 0) + coefficient) % modulus
        if not row[col]:
            del row[col]
    return row


def run() -> dict:
    frozen = json.loads(FREEZE.read_text())
    assert frozen == frozen_inputs()
    protocol = json.loads(PROTOCOL.read_text())
    stage = json.loads(STAGE.read_text())
    reference = json.loads(REFERENCE.read_text())
    previous = json.loads(PREVIOUS.read_text())
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    candidate = json.loads(CANDIDATE.read_text())
    pdp = protocol["point_decomposition"]
    rank_record = protocol["rank_accounting"]
    r = rank_record["modulus"]
    eigen = rank_record["frobenius_eigenvalue_mod_r"]
    started = time.perf_counter_ns()
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    target = tuple(int(value) for value in stage["public_subgroup_target"])
    generator = tuple(int(value) for value in candidate["curve"]["generator"])
    assert curve.onCurve(target) and curve.mul(target, r) is None
    assert curve.mul(generator, eigen) == curve.frob(generator)
    base, representatives, _ = base_and_columns(
        curve, onb, r, int(archive["curve"]["cofactor"]))
    assert len(base) == protocol["factor_base_actual_B"]
    assert len(representatives) == protocol["factor_base_folded_columns_K"]
    assert factor_base_digest(onb, representatives) == protocol[
        "factor_base_enumerated_set_sha256"]
    base_set = set(base)
    quotient = OrbitKey(onb)
    key_to_column = {quotient.canonical(rep)[0]: i
                     for i, rep in enumerate(representatives)}
    assert len(key_to_column) == len(representatives)
    setup_ns = time.perf_counter_ns() - started

    orbit_lift_started = time.perf_counter_ns()
    table: dict[int, list[tuple[int, int, int, int]]] = {}
    table_repeats = skipped_table_identity = 0
    base_index = {point: index for index, point in enumerate(base)}
    assert len(base_index) == len(base)
    lifted = []
    covered_base = set()
    for representative in representatives:
        positive = representative
        orbit_lifts = []
        for _ in range(53):
            negative = curve.neg(positive)
            assert positive in base_index and negative in base_index
            orbit_lifts.append((positive, negative))
            covered_base.add(positive)
            covered_base.add(negative)
            positive = curve.frob(positive)
        assert positive == representative
        lifted.append(orbit_lifts)
    assert covered_base == base_set
    orbit_lift_ns = time.perf_counter_ns() - orbit_lift_started
    generated_states = 0
    table_started = time.perf_counter_ns()
    for i, first_point in enumerate(representatives):
        first = base_index[first_point]
        for j in range(i, len(representatives)):
            for positive, negative in lifted[j]:
                for second_point in (positive, negative):
                    generated_states += 1
                    pair = curve.add(first_point, second_point)
                    if pair is None:
                        skipped_table_identity += 1
                        continue
                    key, exponent, sign = quotient.canonical(pair)
                    descriptions = table.setdefault(key, [])
                    table_repeats += bool(descriptions)
                    descriptions.append((first, base_index[second_point],
                                         exponent, sign))
    table_ns = time.perf_counter_ns() - table_started
    assert generated_states == pdp["table_states"]
    assert len(table) + table_repeats + skipped_table_identity == generated_states

    query_rng = random.Random(pdp["query_seed"])
    query_started = time.perf_counter_ns()
    verification_ns = 0
    skipped_query_identity = candidate_descriptors = proper_rejections = 0
    matched_query_positions = 0
    verified_occurrences = 0
    multi_output_positions = 0
    max_verified_per_query = 0
    unique_points: set[tuple] = set()
    unique_rows: set[tuple] = set()
    relations = []
    rank = IncrementalRank(r)
    first_only_query = None
    first_only_relation = None
    stop = "completed_query_cap"
    processed = 0
    for query_number in range(1, pdp["query_sample_cap"] + 1):
        processed = query_number
        if (time.perf_counter_ns() - started) / 1e9 >= protocol[
                "limits"]["external_wall_seconds"]:
            stop = "wall_cap"
            break
        first, second = pair_sample(query_rng, base)
        pair = curve.add(base[first], base[second])
        if pair is None:
            skipped_query_identity += 1
            continue
        complement = curve.add(target, curve.neg(pair))
        key, exponent, sign = quotient.canonical(complement)
        descriptions = table.get(key)
        if not descriptions:
            continue
        matched_query_positions += 1
        check_started = time.perf_counter_ns()
        query_descriptor = (first, second, exponent, sign)
        verified_at_query = 0
        for index, descriptor in enumerate(descriptions):
            candidate_descriptors += 1
            relation = witness(curve, base, base_set, target, quotient,
                               descriptor, query_descriptor)
            if relation is None:
                proper_rejections += 1
                continue
            if first_only_query is None:
                first_only_query, first_only_relation = query_number, relation
            verified_occurrences += 1
            verified_at_query += 1
            point_signature = tuple(sorted(tuple(point) for point in relation["points"]))
            unique_points.add(point_signature)
            row = row_from_relation(relation, quotient, key_to_column,
                                    curve, eigen, r)
            signature = tuple(sorted(row.items()))
            unique_rows.add(signature)
            novel = rank.add(row)
            relations.append({"query_number": query_number,
                              "table_descriptor_index_for_key": index,
                              "relation": relation,
                              "row": [[col, value] for col, value in signature],
                              "novel_augmented_rank": novel,
                              "augmented_rank_after": rank.rank})
            if verified_occurrences >= pdp["verified_occurrence_cap"]:
                stop = "verified_occurrence_cap"
                break
        verification_ns += time.perf_counter_ns() - check_started
        if verified_at_query > 1:
            multi_output_positions += 1
        max_verified_per_query = max(max_verified_per_query,
                                     verified_at_query)
        if stop == "verified_occurrence_cap":
            break
    total_query_ns = time.perf_counter_ns() - query_started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak *= 1024
    return {
        "kind": "q1452_n53_ordinary_complete_quotient_pair_orbit_stage",
        "proposal_id": "Q1452", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": len(base),
        "factor_base_folded_columns_K": len(representatives),
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "status": stop,
        "table_states_generated": generated_states,
        "table_pair_add_attempts": generated_states,
        "table_base_orbit_lifts_covered": len(covered_base),
        "table_distinct_keys": len(table),
        "table_same_key_repeats": table_repeats,
        "table_skipped_identity_pairs": skipped_table_identity,
        "query_samples_processed": processed,
        "query_skipped_identity_pairs": skipped_query_identity,
        "query_matched_key_positions": matched_query_positions,
        "candidate_table_descriptors_checked": candidate_descriptors,
        "proper_rejections": proper_rejections,
        "verified_relation_occurrences": verified_occurrences,
        "queries_with_multiple_verified_relations": multi_output_positions,
        "maximum_verified_relations_per_query": max_verified_per_query,
        "distinct_point_multisets": len(unique_points),
        "distinct_quotient_rows": len(unique_rows),
        "augmented_rank": rank.rank,
        "same_target_homogeneous_difference_rank": max(0, rank.rank - 1),
        "first_verified_query": first_only_query,
        "first_verified_relation": first_only_relation,
        "relations": relations,
        "phase_wall_ns": {
            "base_and_column_setup": setup_ns,
            "quotient_orbit_lift_index": orbit_lift_ns,
            "table_build": table_ns,
            "target_query_and_lookup": total_query_ns - verification_ns,
            "relation_verification_and_rank": verification_ns,
        },
        "peak_rss_bytes": peak,
        "prior_same_point_q1301_table_samples": reference["table_samples"],
        "prior_same_point_q1301_query_samples": reference[
            "ordinary_query"]["query_samples"],
        "prior_same_point_q1451_table_states": previous["table_samples"],
        "prior_same_point_q1451_query_samples": previous[
            "query_samples_processed"],
        "cumulative_same_point_pair_lane_table_samples": (
            previous["cumulative_same_point_pair_lane_table_samples"] +
            generated_states),
        "cumulative_same_point_pair_lane_query_samples": (
            previous["cumulative_same_point_pair_lane_query_samples"] +
            processed),
        "freeze_sha256": sha(FREEZE),
        "source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        assert not FREEZE.exists()
        FREEZE.write_text(json.dumps(frozen_inputs(), indent=2, sort_keys=True) + "\n")
        print(f"FROZEN {FREEZE}")
        return
    assert args.run and not OUT.exists()
    result = run()
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "query_samples": result["query_samples_processed"],
                      "relations": result["verified_relation_occurrences"],
                      "rank": result["augmented_rank"],
                      "rss_mib": result["peak_rss_bytes"] / 1048576}))


if __name__ == "__main__":
    main()
