#!/usr/bin/env python3
"""Independently replay N53 pair-index witnesses in checked Sage arithmetic."""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, inverse_mod

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE.parent / "ic-ideas-20261007/results/a1_n53_k600_followup_final.json"
CLASSES = [1, 2, 3, 4, 8, 16, 24_316_680_251, 24_854_037_332,
           49_708_074_664, 120_756_896_693]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def from_bits(K, value: int):
    result = K(0)
    term = K(1)
    generator = K.gen()
    while value:
        if value & 1:
            result += term
        term *= generator
        value >>= 1
    return result


def bits(value) -> int:
    return sum(int(coefficient) << i
               for i, coefficient in enumerate(value.polynomial().list()))


def main() -> None:
    output = HERE / "a1_n53_pair_sage_verification.json"
    if output.exists():
        raise FileExistsError(output)
    started = time.perf_counter_ns()
    geometry = json.loads(GEOMETRY.read_text())
    modulus_bits = geometry["field_modulus_bits"]
    F2 = GF(2)
    R = PolynomialRing(F2, "u")
    u = R.gen()
    modulus = sum((u**i for i in range(54) if modulus_bits >> i & 1), R(0))
    K = GF(2**53, "a", modulus=modulus)
    E = EllipticCurve(K, [1, 0, 0, 0, 1])
    r = geometry["subgroup_order"]
    cofactor = geometry["cofactor"]
    records = {}
    for policy in ("seed", "closure"):
        raw_path = HERE / f"a1_n53_pair_{policy}_k600_q64_raw.json"
        receipt_path = HERE / f"a1_n53_pair_{policy}_k600_q64.json"
        raw = json.loads(raw_path.read_text())
        receipt = json.loads(receipt_path.read_text())
        assert receipt["status"] == "completed_verified"
        assert receipt["raw_sha256"] == sha(raw_path)
        records[policy] = (raw, receipt, raw_path, receipt_path)
    seed_rows = records["seed"][0]["rows"]
    closure_rows = records["closure"][0]["rows"]
    assert [(row["scalar"], row["target_point"]) for row in seed_rows] == [
        (row["scalar"], row["target_point"]) for row in closure_rows]

    def point(pair):
        return E(from_bits(K, pair[0]), from_bits(K, pair[1]))

    # The first successful deterministic generator sample fixes the declared
    # subgroup generator up to the two possible y choices at its x-coordinate.
    state = 0x9e37_79b9_7f4a_7c15 ^ 53
    field_mask = (1 << 53) - 1
    generator_candidates = None
    generator_sample_x = None
    for _ in range(1 << 20):
        state = (state * 6364136223846793005 + 1) & ((1 << 64) - 1)
        raw_x = state & field_mask
        for P in E.lift_x(from_bits(K, raw_x), all=True):
            candidate = cofactor * P
            if candidate and r * candidate == E(0):
                generator_candidates = [candidate, -candidate]
                generator_sample_x = raw_x
                break
        if generator_candidates is not None:
            break
    assert generator_candidates is not None
    first = seed_rows[0]
    first_Q = point(first["target_point"])
    valid_generators = [G for G in generator_candidates
                        if first["scalar"] * G == first_Q]
    assert len(valid_generators) == 1
    G = valid_generators[0]
    for row in seed_rows:
        assert row["scalar"] * G == point(row["target_point"])

    seen = set()
    seed_reps = []
    scanned = 0
    raw_x = 1
    while len(seed_reps) < 600:
        scanned += 1
        for P in E.lift_x(from_bits(K, raw_x), all=True):
            candidate = cofactor * P
            if not candidate or bits(candidate[0]) <= 1:
                continue
            x = candidate[0]
            key = bits(x)
            for _ in range(1, 53):
                x *= x
                key = min(key, bits(x))
            if key in seen:
                continue
            seen.add(key)
            seed_reps.append(candidate)
            if len(seed_reps) == 600:
                break
        raw_x += 1
    assert scanned == geometry["extended_scan_end_x"]
    closure_reps = [multiplier * P for P in seed_reps[:60]
                    for multiplier in CLASSES]
    assert len(closure_reps) == 600

    cells = []
    for policy, reps in (("seed", seed_reps), ("closure", closure_reps)):
        raw, receipt, raw_path, receipt_path = records[policy]
        assert raw["scanned_x"] == scanned if policy == "seed" else raw["scanned_x"] < scanned
        verified = []
        for row in raw["rows"]:
            if not row["hit"]:
                continue
            x_values = []
            for index in row["witness_indices"]:
                geometric_column, within = divmod(index, 106)
                shift = within // 2
                x_values.append(reps[geometric_column][0] ** (1 << shift))
            choices = [E.lift_x(x, all=True) for x in x_values]
            assert all(len(options) == 2 for options in choices)
            Q = point(row["target_point"])
            match_count = sum(sum(combo, E(0)) == Q
                              for combo in itertools.product(*choices))
            assert match_count >= 1, (policy, row["query_index"])
            verified.append({"query_index": row["query_index"],
                             "x_bits": [bits(x) for x in x_values],
                             "sign_assignments_matching_target": match_count})
        assert len(verified) == raw["verified_hits"]
        cells.append({"policy": policy, "actual_usable_B": raw["actual_usable_B"],
                      "independent_log_columns": raw["independent_log_columns"],
                      "verified_hits": len(verified),
                      "witnesses": verified,
                      "raw_sha256": sha(raw_path),
                      "receipt_sha256": sha(receipt_path)})
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "curve_id": geometry["curve_id"],
              "field_modulus_bits": modulus_bits,
              "subgroup_order": r, "cofactor": cofactor,
              "generator_sample_x_bits": generator_sample_x,
              "generator_point": [bits(G[0]), bits(G[1])],
              "seed_scanned_x": scanned,
              "all_64_matched_target_scalar_replays": True,
              "cells": cells,
              "stage_wall_ns_exploratory": time.perf_counter_ns() - started,
              "geometry_receipt_sha256": sha(GEOMETRY),
              "source_sha256": sha(Path(__file__))}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"seed_hits": cells[0]["verified_hits"],
                      "closure_hits": cells[1]["verified_hits"],
                      "generator_sample_x": generator_sample_x}))


if __name__ == "__main__":
    main()
