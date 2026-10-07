#!/usr/bin/env python3
"""Replay a SAT relation with installed Sage arithmetic and exact slot geometry."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "shifted_sat_protocol.json"
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
N = 83
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
        raise FileExistsError("save a fresh checked-Sage replay runtime first")
    receipt_path = folder / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"
    protocol = json.loads(PROTOCOL.read_text())
    label = receipt["label"]
    geometry_path = HERE / "runs" / f"{label}_v1" / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    fixture_path = HERE / "runs" / f"{label}_sat_fixture_v1" / "public_input.json"
    fixture = json.loads(fixture_path.read_text())
    old = json.loads(OLD_PUBLIC.read_text())
    assert sha(geometry_path) == fixture["geometry_sha256"]
    assert sha(OLD_PUBLIC) == protocol["public_ordinary_input_sha256"]
    assert receipt["target_Q"] == fixture[receipt["target_kind"]]["target_Q"]
    started = time.perf_counter_ns()
    f2 = GF(2)
    ring = PolynomialRing(f2, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**7 + u**4 + u**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    assert curve.cardinality() == 4 * R and ZZ(R).is_prime(proof=True)

    def element(bits: int):
        return field(ring([(bits >> bit) & 1 for bit in range(N)]))

    def word(value) -> int:
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def pair(point):
        assert point != identity
        return [str(word(point[0])), str(word(point[1]))]

    conjugates = [element(int(value)) for value in
                  old["normal_conjugates_polynomial_bits_decimal"]]
    masks = [int(value) for value in receipt["model"]["mask_decimal"]]
    xs = [int(value) for value in receipt["model"]["factor_x_decimal"]]
    points = [curve(element(int(row[0])), element(int(row[1])))
              for row in receipt["group_check"]["raw_points"]]
    assert len(masks) == len(xs) == len(points) == geometry["arity"]
    raw_reps = gzip.decompress((geometry_path.parent / "representatives.json.gz").read_bytes())
    assert hashlib.sha256(raw_reps).hexdigest() == geometry["representatives_sha256"]
    reps = {tuple(row) for row in json.loads(raw_reps)["representatives"]}

    def orbit_key(point):
        x, y = point[0], point[1]
        values = []
        for _ in range(N):
            a, b = word(x), word(y)
            values.extend(((a, b), (a, a ^ b)))
            x, y = x**2, y**2
        return min(values)

    prefix = identity
    prior_x = None
    keys = []
    for slot_index, (mask, xword, point) in enumerate(zip(masks, xs, points)):
        slot = geometry["slot_normal_basis_indices"][slot_index]
        assert 1 <= mask < (1 << geometry["dimension"])
        x = sum((conjugates[slot[bit]] for bit in range(len(slot))
                 if mask & (1 << bit)), field(0))
        assert word(x) == xword == word(point[0])
        projected = 4 * point
        assert projected != identity and R * projected == identity
        key = orbit_key(projected)
        assert key in reps
        keys.append(key)
        prefix += point
        assert prefix != identity
        if prior_x is not None:
            e2 = prior_x * point[0] + prior_x * prefix[0] + point[0] * prefix[0]
            assert e2**2 + prior_x * point[0] * prefix[0] + field(1) == 0
        prior_x = prefix[0]
    branch = fixture[receipt["target_kind"]]["raw_target_fiber"][receipt["fiber_index"]]
    target = curve(element(int(receipt["target_Q"][0])),
                   element(int(receipt["target_Q"][1])))
    assert pair(prefix) == [branch["x"], branch["y"]]
    assert 4 * prefix == target and R * target == identity
    assert pair(target) == receipt["target_Q"]
    report = {
        "schema_version": 1, "kind": "n83_shifted_s3_sage_model_replay",
        "status": "PASS", "candidate_id": None,
        "label": label, "target_kind": receipt["target_kind"],
        "fiber_index": receipt["fiber_index"],
        "all_masks_in_exact_slots": True,
        "all_projected_factors_in_measured_base_orbits": True,
        "all_prefixes_nonidentity": True, "all_s3_links_zero": True,
        "raw_fiber_and_subgroup_target_verified": True,
        "distinct_signed_frobenius_orbits": len(set(keys)) == len(keys),
        "branch_receipt_sha256": sha(receipt_path),
        "public_input_sha256": sha(fixture_path),
        "geometry_sha256": sha(geometry_path),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_replay_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "One verified relation only; no factor-base logarithms or target DLP.",
    }
    save(output, report)
    print(json.dumps({"label": label, "kind": receipt["target_kind"],
                      "fiber": receipt["fiber_index"], "status": "PASS"}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    main(args.folder)
