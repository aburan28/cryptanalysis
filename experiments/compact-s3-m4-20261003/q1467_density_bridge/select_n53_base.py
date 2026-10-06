#!/usr/bin/env python3
"""Select an exact 26-orbit N53 base with N131-like four-sum supply."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from enumerate_n83_weight5_full import necklaces  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from q1438_dense_base.enumerate_base import n53_reference  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "n53_w3_26_orbits.json"
N = 53
ORBIT_COUNT = 26
WIDTH = (N + 7) // 8


def digest(values: list[int]) -> str:
    h = hashlib.sha256()
    for value in values:
        h.update(value.to_bytes(WIDTH, "little"))
    return h.hexdigest()


def generate() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1467"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["n53_selection_rule"] == (
        "first 26 sorted canonical projected x-orbit keys from the "
        "complete N53 W<=3 base; include every rational W<=3 raw x "
        "Frobenius orbit projecting to a selected key")
    assert protocol["selected_n53_projected_orbits_K"] == ORBIT_COUNT
    assert protocol["input_sha256"] == {
        path: sha(ROOT / path) for path in protocol["input_sha256"]}
    assert protocol["source_sha256"]["select_n53_base.py"] == sha(
        Path(__file__))
    assert protocol["sage_runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    parent = json.loads((PARENT / "protocol.json").read_text())
    profile = next(p for p in parent["profiles"] if p["field"]["n"] == N)
    assert profile["curve"]["curve_id"] == protocol["curve_id"]
    cofactor = int(profile["curve"]["cofactor"])
    subgroup_order = int(profile["curve"]["subgroup_order"])
    assert cofactor == 428
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    raw_orbits: dict[int, list[tuple[int, object]]] = {}
    raw_orbit_count = 0
    for cycle_mask in necklaces(N, 3):
        raw_orbit_count += 1
        coordinates = sum(1 << orbit.coordinate_cycle[j]
                          for j in range(N) if cycle_mask >> j & 1)
        x = onb.fromCoords(coordinates)
        raw_point = curve.pointFromX(x)
        if raw_point is None:
            continue
        projected = curve.mul(raw_point, cofactor)
        if projected is None:
            continue
        key = canonical_rotation(orbit.cycle_bits(projected[0]), N)
        raw_orbits.setdefault(key, []).append((cycle_mask, x))
    full_keys = sorted(raw_orbits)
    assert set(full_keys) == n53_reference(onb, orbit)
    assert len(full_keys) == 227
    selected = full_keys[:ORBIT_COUNT]
    allowed = set()
    raw_orbit_counts = []
    for key in selected:
        raw_orbit_counts.append(len(raw_orbits[key]))
        for cycle_mask, x in raw_orbits[key]:
            seen = set()
            current = x
            bits = cycle_mask
            for _ in range(N):
                assert orbit.cycle_bits(current) == bits
                mask = int(onb.toCoords(current))
                assert mask.bit_count() <= 3 and mask != 0
                seen.add(mask)
                allowed.add(mask)
                current = current * current
                bits = ((bits << 1) | (bits >> (N - 1))) & ((1 << N) - 1)
            assert len(seen) == N
    allowed = sorted(allowed)
    assert len(allowed) == N * sum(raw_orbit_counts)
    actual_B = 2 * N * ORBIT_COUNT
    with localcontext() as context:
        context.prec = 60
        mean = Decimal(math.comb(actual_B + 3, 4)) / Decimal(
            subgroup_order - 1)
    return {
        "kind": "q1467_density_matched_n53_frobenius_base",
        "proposal_id": "Q1467", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": protocol["curve_id"], "field_degree_n": N,
        "normal_basis_weight_bound": 3,
        "cofactor": cofactor, "subgroup_order": subgroup_order,
        "selection_rule": protocol["n53_selection_rule"],
        "complete_w3_projected_columns": len(full_keys),
        "enumerated_raw_x_orbits": raw_orbit_count,
        "selected_projected_columns_K": ORBIT_COUNT,
        "actual_usable_points_B_before_folding": actual_B,
        "selected_projected_orbit_keys_digest_sha256": digest(selected),
        "selected_projected_orbit_keys_onb_hex": [format(k, "x")
                                                  for k in selected],
        "selected_raw_x_orbits_per_projected_key": raw_orbit_counts,
        "allowed_raw_x_mask_count": len(allowed),
        "allowed_raw_x_masks_digest_sha256": digest(allowed),
        "allowed_raw_x_masks_onb_hex": [format(mask, "x")
                                           for mask in allowed],
        "uniform_nonidentity_target_mean_multisets_upper_decimal": str(mean),
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "challenge_run_admitted": False,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = generate()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1467 exact N53 density-matched base: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"proposal_id": "Q1467",
                          "B": result["actual_usable_points_B_before_folding"],
                          "K": result["selected_projected_columns_K"],
                          "allowed_raw_x_masks": result[
                              "allowed_raw_x_mask_count"]}))


if __name__ == "__main__":
    main()
