#!/usr/bin/env sage -python
"""Independently count packed W masks and replay selected full curve points."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
PARENT_D10 = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/controls/d10/flags.bin"
CELL_NAMES = ("neither", "source_only", "descendant_only", "both")


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


def cell_at(data, mask):
    zero_based = mask - 1
    return (data[zero_based >> 2] >> (2 * (zero_based & 3))) & 3


def seeded_masks(domain, count, dimension):
    limit = (1 << dimension) - 1
    if count >= limit:
        return list(range(1, limit + 1))
    chosen = set()
    counter = 0
    while len(chosen) < count:
        digest = hashlib.sha256(f"{domain}:{dimension}:{counter}".encode()).digest()
        mask = int.from_bytes(digest[:4], "big") & limit
        if mask:
            chosen.add(mask)
        counter += 1
    return sorted(chosen)


def summarize_membership(data, dimension):
    limit = (1 << dimension) - 1
    assert len(data) == (limit + 3) // 4
    padding = 4 * len(data) - limit
    assert data[-1] >> (2 * (4 - padding)) == 0
    frequencies = Counter(data)
    lookup = [tuple(sum(((byte >> (2 * slot)) & 3) == cell
                        for slot in range(4)) for cell in range(4))
              for byte in range(256)]
    cells = [sum(count * lookup[byte][cell]
                 for byte, count in frequencies.items()) for cell in range(4)]
    cells[0] -= padding
    assert sum(cells) == limit and min(cells) >= 0
    paired = dict(zip(CELL_NAMES, cells))
    rows = {}
    for name, rational in (("source", cells[1] + cells[3]),
                           ("descendant", cells[2] + cells[3])):
        rows[name] = {"rational_w": rational,
                      "reciprocal_partners_in_w": 0,
                      "two_element_reciprocal_pairs": 0,
                      "fixed_reciprocal_points": 0,
                      "sign_folded_columns": rational,
                      "actual_usable_points_B": 2 * rational}
    return paired, rows


def first_by_cell(data, dimension, each):
    found = {cell: [] for cell in range(4)}
    for mask in range(1, 1 << dimension):
        cell = cell_at(data, mask)
        if len(found[cell]) < each:
            found[cell].append(mask)
        if all(len(values) == each for values in found.values()):
            break
    assert all(len(values) == each for values in found.values())
    return found


def replay_points(data, dimension, config, native):
    route = json.loads(ROUTE.read_text())
    assert sha(ROUTE) == config["route_manifest_sha256"]
    assert route["route_id"] == config["curve_route_id"]
    assert route["curve_nodes"]["source"]["curve_id"] == config[
        "source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config[
        "target_curve_id"]
    assert route["curve_nodes"]["source"]["cofactor"] == 4
    assert route["curve_nodes"]["target"]["cofactor"] == 4
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)

    def decode(word):
        word = int(word)
        return field(sum(t**i for i in range(word.bit_length())
                         if (word >> i) & 1))

    a4, a6 = [decode(value) for value in route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"][3:]]
    b = a6 + a4**2
    alpha = b ** (1 << 129)
    assert alpha**4 == b and encode(alpha) == int(config[
        "normalized_descendant_alpha"])
    assert encode(alpha).bit_length() - 1 == config[
        "normalized_descendant_alpha_polynomial_degree"]
    curves = {
        "source": (EllipticCurve(field, [1, 0, 0, 0, 1]), field.one(), field.one()),
        "descendant": (EllipticCurve(field, [1, 0, 0, 0, b]), alpha, b),
    }
    torsion = {}
    for name, (curve, coefficient_alpha, _) in curves.items():
        assert int(coefficient_alpha.trace()) == 1
        torsion[name] = curve([coefficient_alpha, coefficient_alpha**2])
        assert not (2 * torsion[name]).is_zero()
        assert (4 * torsion[name]).is_zero()
    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, dimension + 1)]
    assert all(int(value.trace()) == 0 for value in basis)

    def w_value(mask):
        value = field.zero()
        for j, basis_value in enumerate(basis):
            if (mask >> j) & 1:
                value += basis_value
        return value

    def member_mask(value):
        bits = encode(value)
        mask = bits >> 1
        if not 1 <= mask < (1 << dimension):
            return 0
        return mask if w_value(mask) == value else 0

    predicate_masks = seeded_masks(config["predicate_seed_domain"],
                                   config["predicate_controls_uniform_sha256"],
                                   dimension)
    if dimension <= 10:
        point_masks = predicate_masks
        first_cells = {cell: [] for cell in range(4)}
    else:
        first_cells = first_by_cell(data, dimension, config[
            "full_point_controls_per_rationality_cell"])
        point_masks = sorted(set(seeded_masks(config["full_point_seed_domain"],
                                              config["full_point_controls_uniform_sha256"],
                                              dimension)).union(*first_cells.values()))
    cache = {}
    for mask in set(predicate_masks).union(point_masks):
        w = w_value(mask)
        assert w != 0 and int(w.trace()) == 0
        inverse = 1 / w
        source_ok = int(inverse.trace()) == 0
        descendant_ok = int((alpha * inverse).trace()) == 0
        assert cell_at(data, mask) == int(source_ok) + 2 * int(descendant_ok), mask
        cache[mask] = (w, inverse)

    subgroup_order = ZZ(route["curve_nodes"]["source"]["subgroup_order"])
    assert subgroup_order == ZZ(route["curve_nodes"]["target"]["subgroup_order"])
    projected = {name: set() for name in curves}
    rational_point_replays = {name: 0 for name in curves}
    for mask in point_masks:
        w, inverse = cache[mask]
        u = half_trace(w)
        assert u not in (0, 1)
        code = cell_at(data, mask)
        for name, (curve, coefficient_alpha, coefficient_b) in curves.items():
            rational = bool(code & (1 if name == "source" else 2))
            partner = coefficient_alpha * inverse
            assert member_mask(partner) == 0
            x = coefficient_alpha * (1 + 1 / u)
            rhs = x + coefficient_b / (x*x)
            assert (int(rhs.trace()) == 0) == rational
            if not rational:
                continue
            point = curve([x, x * half_trace(rhs)])
            translated = point + torsion[name]
            assert translated[0] != coefficient_alpha
            next_u = coefficient_alpha / (translated[0] + coefficient_alpha)
            assert next_u**2 + next_u == partner
            image = 4 * point
            assert not image.is_zero() and 4 * translated == image
            assert subgroup_order * image == curve(0)
            key = (encode(image[0]),
                   min(encode(image[1]), encode(image[1] + image[0])))
            assert key not in projected[name]
            projected[name].add(key)
            rational_point_replays[name] += 1
    if dimension <= 10:
        for name in curves:
            assert len(projected[name]) == native[name]["sign_folded_columns"]
        prior_flags = PARENT_D10.read_bytes()
        assert sha(PARENT_D10) == json.loads((PARENT_D10.parent / "summary.json").read_text())[
            "artifacts_sha256"]["flags.bin"]
        assert len(prior_flags) == len(data) * 4 - 1
        for mask, flag in enumerate(prior_flags, 1):
            expected = (flag & 1) | (((flag >> 4) & 1) << 1)
            assert cell_at(data, mask) == expected
    return {
        "predicate_control_masks": len(predicate_masks),
        "point_control_masks": len(point_masks),
        "first_masks_per_cell": {CELL_NAMES[cell]: values
                                 for cell, values in first_cells.items()},
        "rational_point_replays": rational_point_replays,
        "distinct_projected_signed_points":
            {name: len(values) for name, values in projected.items()},
        "parent_d10_flags_sha256": sha(PARENT_D10) if dimension <= 10 else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("verification output already exists")
    config = json.loads(CONFIG.read_text())
    summary = json.loads((args.run_dir / "summary.json").read_text())
    assert summary["status"] == "completed_unverified"
    for name, expected in summary["artifacts_sha256"].items():
        assert sha(args.run_dir / name) == expected, name
    for name, expected in summary["inputs_sha256"].items():
        assert sha(ROOT / name) == expected, name
    native = json.loads((args.run_dir / "native.json").read_text())
    dimension = native["dimension"]
    data = (args.run_dir / "membership.bin").read_bytes()
    paired, rows = summarize_membership(data, dimension)
    assert paired == summary["paired_rationality"] == native["paired_rationality"]
    for name in ("source", "descendant"):
        for key, value in rows[name].items():
            assert value == summary[name][key] == native[name][key], (name, key)
    controls = replay_points(data, dimension, config, native)
    result = {
        "schema": "ecc2k130-263-w28-exact-base-verification-v1",
        "status": "PASS_PACKED_COUNT_AND_GROUP_CONTROLS",
        "verified": True,
        "summary_sha256": sha(args.run_dir / "summary.json"),
        "membership_sha256": sha(args.run_dir / "membership.bin"),
        "native_sha256": sha(args.run_dir / "native.json"),
        "verifier_sha256": sha(Path(__file__)),
        "checked_nonzero_masks": (1 << dimension) - 1,
        "independent_paired_rationality": paired,
        "independent_counts": rows,
        **controls,
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True,
                      "masks": result["checked_nonzero_masks"],
                      "predicate_controls": controls["predicate_control_masks"],
                      "point_controls": controls["point_control_masks"]}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python disables required assertions")
    main()
