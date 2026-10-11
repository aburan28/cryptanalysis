#!/usr/bin/env sage -python
"""Independently replay W-mask flags and selected group-law projections."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
CONFIG = HERE / "CONFIG.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def half_trace(value):
    term = value
    total = value
    for _ in range(65):
        term = term**4
        total += term
    assert total**2 + total == value
    return total


def selected_masks(dimension, receipt, flags):
    if dimension <= 10:
        return list(range(1, (1 << dimension)))
    chosen = set()
    for name in ("source", "descendant"):
        chosen.update(receipt[name]["first_representative_masks"])
        chosen.update(receipt[name]["first_paired_masks"])
    counter = 0
    while len(chosen) < 160:
        payload = f"ecc2k130-w24-point-control-v1:{dimension}:{counter}".encode()
        mask = 1 + int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % (
            (1 << dimension) - 1)
        chosen.add(mask)
        counter += 1
    # Include a bounded sample of each rationality status without changing
    # the frozen exhaustive count or choosing on any solver outcome.
    for name, shift in (("source", 0), ("descendant", 4)):
        found = 0
        for mask, byte in enumerate(flags, 1):
            if (byte >> shift) & 1:
                chosen.add(mask)
                found += 1
                if found == 32:
                    break
    return sorted(chosen)


def summarize_flags(run_dir, receipt, flags):
    dimension = receipt["dimension"]
    assert len(flags) == (1 << dimension) - 1
    counts = {name: {"rational_w": 0, "reciprocal_partners_in_w": 0,
                     "fixed_reciprocal_points": 0, "sign_folded_columns": 0}
              for name in ("source", "descendant")}
    expected = {name: bytearray() for name in counts}
    for mask, byte in enumerate(flags, 1):
        for name, shift in (("source", 0), ("descendant", 4)):
            nibble = (byte >> shift) & 15
            rational = bool(nibble & 1)
            inside = bool(nibble & 2)
            canonical = bool(nibble & 4)
            fixed = bool(nibble & 8)
            assert not (inside or canonical or fixed) or rational
            assert not fixed or inside
            assert not (rational and not inside) or canonical
            row = counts[name]
            row["rational_w"] += int(rational)
            row["reciprocal_partners_in_w"] += int(inside)
            row["fixed_reciprocal_points"] += int(fixed)
            row["sign_folded_columns"] += int(canonical)
            if canonical:
                expected[name].extend(struct.pack("<I", mask))
    for name in counts:
        row = counts[name]
        assert (row["reciprocal_partners_in_w"] - row[
            "fixed_reciprocal_points"]) % 2 == 0
        row["two_element_reciprocal_pairs"] = (
            row["reciprocal_partners_in_w"] - row["fixed_reciprocal_points"]) // 2
        row["actual_usable_points_B"] = 2 * row["sign_folded_columns"]
        assert row["sign_folded_columns"] == row["rational_w"] - row[
            "two_element_reciprocal_pairs"]
        mask_path = run_dir / f"{name}-masks.bin"
        assert mask_path.read_bytes() == expected[name]
        for key, value in row.items():
            assert receipt[name][key] == value, (name, key, value)
    return counts


def replay_points(dimension, receipt, flags):
    config = json.loads(CONFIG.read_text())
    route = json.loads(ROUTE.read_text())
    assert sha(ROUTE) == config["route_manifest_sha256"]
    assert route["route_id"] == config["curve_route_id"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)

    def decode(word):
        word = int(word)
        return field(sum(t**i for i in range(word.bit_length()) if (word >> i) & 1))

    a4, a6 = [decode(value) for value in route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"][3:]]
    b = a6 + a4**2
    alpha = b ** (1 << 129)
    assert alpha**4 == b and encode(alpha) == int(config[
        "normalized_descendant_alpha"])
    curves = {
        "source": (EllipticCurve(field, [1, 0, 0, 0, 1]), field.one(), field.one()),
        "descendant": (EllipticCurve(field, [1, 0, 0, 0, b]), alpha, b),
    }
    for curve, a, _ in curves.values():
        assert int(a.trace()) == 1
        torsion = curve([a, a**2])
        assert (4 * torsion).is_zero() and not (2 * torsion).is_zero()
    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, dimension + 1)]
    assert all(int(v.trace()) == 0 for v in basis)

    def member_mask(value):
        bits = encode(value)
        mask = bits >> 1
        if mask <= 0 or mask >= (1 << dimension):
            return 0
        rebuilt = field.zero()
        for j, v in enumerate(basis):
            if (mask >> j) & 1:
                rebuilt += v
        return mask if rebuilt == value else 0

    controls = selected_masks(dimension, receipt, flags)
    projected = {name: set() for name in curves}
    subgroup_order = ZZ(route["curve_nodes"]["source"]["subgroup_order"])
    for mask in controls:
        w = field.zero()
        for j, value in enumerate(basis):
            if (mask >> j) & 1:
                w += value
        assert w != 0 and int(w.trace()) == 0
        u = half_trace(w)
        assert u not in (0, 1)
        for name, (curve, a, coefficient) in curves.items():
            nibble = (flags[mask - 1] >> (0 if name == "source" else 4)) & 15
            partner = a / w
            rational = int(partner.trace()) == 0
            assert bool(nibble & 1) == rational, (mask, name)
            if not rational:
                assert nibble == 0
                continue
            other_mask = member_mask(partner)
            assert bool(nibble & 2) == bool(other_mask)
            assert bool(nibble & 4) == (not other_mask or mask <= other_mask)
            assert bool(nibble & 8) == (other_mask == mask)
            x = a * (1 + 1 / u)
            rhs = x + coefficient / (x*x)
            assert int(rhs.trace()) == 0
            point = curve([x, x * half_trace(rhs)])
            torsion = curve([a, a**2])
            translated = point + torsion
            assert translated[0] != a
            next_u = a / (translated[0] + a)
            assert next_u**2 + next_u == partner
            image = 4 * point
            assert not image.is_zero() and 4 * translated == image
            assert subgroup_order * image == curve(0)
            key = (encode(image[0]),
                   min(encode(image[1]), encode(image[1] + image[0])))
            projected[name].add(key)
    if dimension <= 10:
        for name in curves:
            assert len(projected[name]) == receipt[name]["sign_folded_columns"]
    return {"point_control_masks": len(controls),
            "distinct_projected_signed_points":
                {name: len(values) for name, values in projected.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("verification output already exists")
    summary = json.loads((args.run_dir / "summary.json").read_text())
    assert summary["status"] == "completed_unverified"
    for name, expected in summary["artifacts_sha256"].items():
        assert sha(args.run_dir / name) == expected, name
    for name, expected in summary["inputs_sha256"].items():
        assert sha(ROOT / name) == expected, name
    native = json.loads((args.run_dir / "native.json").read_text())
    flags = (args.run_dir / "flags.bin").read_bytes()
    counts = summarize_flags(args.run_dir, native, flags)
    controls = replay_points(native["dimension"], native, flags)
    result = {"schema": "ecc2k130-263-exact-w-base-verification-v1",
              "status": "PASS_EXACT_BASE_AND_GROUP_CONTROLS",
              "verified": True,
              "summary_sha256": sha(args.run_dir / "summary.json"),
              "flags_sha256": sha(args.run_dir / "flags.bin"),
              "native_sha256": sha(args.run_dir / "native.json"),
              "verifier_sha256": sha(Path(__file__)),
              "checked_nonzero_masks": len(flags),
              "independent_counts": counts,
              **controls,
              "natural_pdp_yield": None,
              "verified_relation_rank": None,
              "verified_logarithm": None,
              "online_wall_time": None,
              "rho_ratio": None}
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "masks": len(flags), **controls}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python disables required assertions")
    main()
