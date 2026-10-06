#!/usr/bin/env python3
"""Exact N83 geometry screen for adding weight-3/4 Hamming masks to shifted slots."""

from __future__ import annotations

import argparse
from decimal import Decimal, getcontext
import hashlib
import itertools
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

HERE = Path(__file__).resolve().parent
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
PROTOCOL = HERE / "shifted_sat_protocol.json"
N = 83
R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(label: str, out: Path) -> None:
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file() or (out / "started.json").exists():
        raise FileExistsError("screen needs a fresh checked-Sage runtime receipt")
    protocol = json.loads(PROTOCOL.read_text())
    option = next(item for item in protocol["geometry"] if item["label"] == label)
    geometry_path = HERE / "runs" / f"{label}_v1" / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    public = json.loads(OLD_PUBLIC.read_text())
    assert sha(geometry_path) == option["geometry_sha256"]
    assert sha(OLD_PUBLIC) == protocol["public_ordinary_input_sha256"]
    assert geometry["curve_id"] == protocol["curve_id"] == public["curve_id"]
    save(out / "started.json", {
        "kind": "n83_shifted_hamming_transfer_start", "candidate_id": None,
        "label": label, "protocol_sha256": sha(PROTOCOL),
        "geometry_sha256": sha(geometry_path),
        "old_public_sha256": sha(OLD_PUBLIC),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime)})
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

    conjugates = [element(int(value)) for value in
                  public["normal_conjugates_polynomial_bits_decimal"]]
    slots = geometry["slot_normal_basis_indices"]
    d = geometry["dimension"]
    assert len(slots) == geometry["arity"] and all(len(slot) == d for slot in slots)
    rows = []
    for slot_index, slot in enumerate(slots):
        projected = set()
        rational_masks = 0
        projected_identity_masks = 0
        for weight in (3, 4):
            for indices in itertools.combinations(range(d), weight):
                x = sum((conjugates[slot[index]] for index in indices), field(0))
                assert x != 0
                lifts = tuple(curve.lift_x(x, all=True))
                if not lifts:
                    continue
                assert len(lifts) == 2
                rational_masks += 1
                images = tuple(4 * point for point in lifts)
                if images[0] == identity:
                    assert images[1] == identity
                    projected_identity_masks += 1
                    continue
                assert images[0] != images[1]
                projected.update((word(point[0]), word(point[1])) for point in images)
        # x masks in a basis are distinct, and [4] is injective across x modulo
        # possible 4-torsion fibers; use the set size rather than assuming it.
        rows.append({"slot_index": slot_index,
                     "weight_3_or_4_mask_count": sum(int(ZZ(d).binomial(w)) for w in (3, 4)),
                     "rational_masks": rational_masks,
                     "projected_identity_masks": projected_identity_masks,
                     "actual_usable_projected_points_B": len(projected)})
        save(out / "progress.json", {"completed_slots": len(rows), "rows": rows})
    tuple_count = 1
    for row in rows:
        tuple_count *= row["actual_usable_projected_points_B"]
    getcontext().prec = 45
    quotient = Decimal(tuple_count) / Decimal(R)
    unrestricted = Decimal(str(geometry["ordered_tuples_per_subgroup_element"]))
    report = {
        "schema_version": 1, "kind": "n83_shifted_hamming_transfer_geometry",
        "status": "EXACT_GEOMETRY_PASS", "candidate_id": None,
        "label": label, "curve_id": protocol["curve_id"],
        "mask_policy": "each slot has exact Hamming weight 3 or 4",
        "rows": rows,
        "minimum_slot_usable_points_B": min(row["actual_usable_projected_points_B"] for row in rows),
        "maximum_slot_usable_points_B": max(row["actual_usable_projected_points_B"] for row in rows),
        "ordered_usable_projected_tuples": str(tuple_count),
        "ordered_tuples_per_uniform_subgroup_target": str(quotient),
        "uniform_target_success_probability_upper_bound": str(min(Decimal(1), quotient)),
        "unrestricted_ordered_tuples_per_target": str(unrestricted),
        "restricted_to_unrestricted_tuple_ratio": str(quotient / unrestricted),
        "effective_signed_frobenius_columns_K": None,
        "one_frozen_ordinary_target_yield": None,
        "claim_boundary": "Exact restricted base counts and a counting upper bound for a uniformly random subgroup target. The tuple distribution and SAT cost are not measured; this does not establish N83 natural relation yield or a solver improvement.",
        "protocol_sha256": sha(PROTOCOL), "geometry_sha256": sha(geometry_path),
        "old_public_sha256": sha(OLD_PUBLIC),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
    }
    save(out / "report.json", report)
    print(json.dumps({"label": label, "status": report["status"],
                      "per_target": report["ordered_tuples_per_uniform_subgroup_target"]},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.label, args.out)
