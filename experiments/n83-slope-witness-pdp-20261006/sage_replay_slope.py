#!/usr/bin/env python3
"""Independent checked-Sage replay of one SAT slope-witness N83 branch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
REPS = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_full_w4_geometry_v1/representatives.json"
PROTOCOL = HERE / "protocol.json"
R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(folder: Path) -> None:
    folder = folder.resolve()
    runtime = folder / "sage_replay_runtime_info.json"
    output = folder / "sage_replay.json"
    if not runtime.is_file() or output.exists():
        raise FileExistsError("save checked Sage runtime before immutable replay")
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(PUBLIC.read_text())
    reps_record = json.loads(REPS.read_text())
    assert sha(PUBLIC) == protocol["source_public_fixture_sha256"]
    assert sha(REPS) == protocol["full_w34_representatives_sha256"]
    assert public["curve_id"] == reps_record["curve_id"] == protocol["curve_id"]
    receipt_path = folder / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"
    private_path = folder / "private_model.json"
    private = json.loads(private_path.read_text())
    assert sha(private_path) == receipt["private_model_sha256_local_only"]
    assert private["verified"] and len(private["masks"]) == 5
    assert len(private["raw_factor_points"]) == 5
    kind = receipt["target_kind"]
    fiber = public[kind]["raw_target_fiber"][receipt["fiber_index"]]
    started = time.perf_counter_ns()
    base = PolynomialRing(GF(2), "u")
    u = base.gen()
    field = GF(2**83, "z", modulus=u**83 + u**7 + u**4 + u**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    assert curve.cardinality() == 4 * R and ZZ(R).is_prime(proof=True)

    def element(bits: int):
        return field(base([(bits >> bit) & 1 for bit in range(83)]))

    def word(value) -> int:
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def point(pair):
        result = curve(element(int(pair[0])), element(int(pair[1])))
        assert result != identity
        return result

    def encoded(value):
        assert value != identity
        return [str(word(value[0])), str(word(value[1]))]

    def orbit_key(value):
        x, y = value[0], value[1]
        keys = []
        for _ in range(83):
            a, b = word(x), word(y)
            keys.extend(((a, b), (a, a ^ b)))
            x, y = x**2, y**2
        return min(keys)

    conjugates = [element(int(value)) for value in
                  public["normal_conjugates_polynomial_bits_decimal"]]
    representatives = {tuple(row) for row in reps_record["representatives"]}
    factors = []
    for mask, pair in zip(private["masks"], private["raw_factor_points"]):
        assert len(mask) in (3, 4) and mask == sorted(set(mask))
        assert all(bit in range(83) for bit in mask)
        x = sum((conjugates[bit] for bit in mask), field(0))
        assert x != 0
        value = point(pair)
        assert value[0] == x
        projected = 4 * value
        assert projected != identity and R * projected == identity
        assert orbit_key(projected) in representatives
        factors.append(value)
    prefix = factors[0]
    for factor in factors[1:]:
        assert prefix[0] != factor[0]
        prefix += factor
        assert prefix != identity
    assert encoded(prefix) == private["raw_sum"] == [fiber["x"], fiber["y"]]
    assert encoded(4 * prefix) == private["projected_sum"] == public[kind]["target_Q"]
    result = {
        "schema_version": 1,
        "kind": "n83_w34_slope_witness_sage_replay",
        "status": "PASS", "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_kind": kind, "fiber_index": receipt["fiber_index"],
        "factor_count": 5,
        "all_masks_exact_weight_three_or_four": True,
        "all_five_points_on_curve": True,
        "all_projected_factors_in_measured_base_orbits": True,
        "all_four_additions_regular": True,
        "raw_fiber_and_subgroup_target_verified": True,
        "solver_cnf_xor_model_verified_by_producer": True,
        "receipt_sha256": sha(receipt_path),
        "private_model_sha256_local_only": sha(private_path),
        "public_fixture_sha256": sha(PUBLIC),
        "representatives_sha256": sha(REPS),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "Independent SAT-model group replay only. Pinned planted models do not estimate unpinned relation yield. No full DLP or speedup follows from this control.",
    }
    save(output, result)
    print(json.dumps({"status": "PASS", "factors": 5}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    main(args.folder)
