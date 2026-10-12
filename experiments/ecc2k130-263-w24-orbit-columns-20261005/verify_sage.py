#!/usr/bin/env sage -python
"""Independently check frozen W24 orbit forests against ECC point Frobenius."""

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ
from sage.version import version as sage_version


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encoded(value):
    return sum(int(bit) << index for index, bit in
               enumerate(value.polynomial().list()))


def half_trace(value):
    term = value
    total = value
    for _ in range(65):
        term = term**4
        total += term
    assert total**2 + total == value
    return total


def pairs(path):
    data = path.read_bytes()
    assert len(data) % 8 == 0
    return list(struct.iter_unpack("<II", data))


def check_graph(run_dir, input_path, dimension, expected_count):
    native = json.loads((run_dir / "native.json").read_text())
    assert native["status"] == "completed_unverified"
    assert native["dimension"] == dimension
    assert native["source_signed_columns"] == expected_count
    bitset = bytearray(1 << dimension)
    ordered_masks = [] if dimension <= 10 else None
    previous = 0
    count = 0
    with input_path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            assert len(chunk) % 4 == 0
            for (mask,) in struct.iter_unpack("<I", chunk):
                assert previous < mask < (1 << dimension)
                assert bitset[mask] == 0
                bitset[mask] = 1
                if ordered_masks is not None:
                    ordered_masks.append(mask)
                previous = mask
                count += 1
    assert count == expected_count
    edges = pairs(run_dir / "forest.bin")
    assert len(edges) == native["forest_edges"] == native["saved_columns"]
    parent = {}

    def find(value):
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for a, b in edges:
        assert a < b and bitset[a] and bitset[b]
        root_a, root_b = find(a), find(b)
        assert root_a != root_b, "forest contains a cycle"
        parent[root_b] = root_a
    groups = defaultdict(list)
    for mask in parent:
        groups[find(mask)].append(mask)
    expected_labels = {}
    histogram = Counter({1: expected_count - len(parent)})
    for masks in groups.values():
        label = min(masks)
        histogram[len(masks)] += 1
        for mask in masks:
            expected_labels[mask] = label
    actual = pairs(run_dir / "nontrivial-components.bin")
    assert actual == sorted(expected_labels.items())
    assert len(actual) == native["nontrivial_masks"]
    assert native["orbit_representatives"] == sum(histogram.values())
    assert native["component_size_histogram"] == {
        str(size): number for size, number in sorted(histogram.items())}
    assert native["largest_component"] == max(histogram)
    return native, edges, expected_labels, ordered_masks


def source_points(dimension):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, dimension + 1)]
    assert all(int(value.trace()) == 0 for value in basis)

    def w_for(mask):
        value = field.zero()
        for j, element in enumerate(basis):
            if mask & (1 << j):
                value += element
        return value

    def projected(w):
        assert w and int(w.trace()) == 0 and int((1 / w).trace()) == 0
        u = half_trace(w)
        x = 1 + 1 / u
        rhs = x + 1 / (x*x)
        assert int(rhs.trace()) == 0
        point = curve([x, x * half_trace(rhs)])
        result = 4 * point
        assert not result.is_zero()
        return result

    return w_for, projected


def sign_key(x, y):
    return encoded(x), min(encoded(y), encoded(y + x))


def orbit_key(point):
    x, y = point[0], point[1]
    keys = []
    for _ in range(131):
        keys.append(sign_key(x, y))
        x, y = x**2, y**2
    assert x == point[0] and y == point[1]
    return min(keys)


def select_edges(edges, dimension):
    if dimension <= 10 or len(edges) <= 256:
        return edges
    prefix = b"ecc2k130-w24-orbit-edge-v1:"
    return sorted(edges, key=lambda pair: hashlib.sha256(
        prefix + struct.pack("<II", *pair)).digest())[:256]


def check_points(dimension, edges, labels, ordered_masks):
    w_for, projected = source_points(dimension)
    cache = {}

    def get(mask):
        if mask not in cache:
            w = w_for(mask)
            cache[mask] = (w, projected(w))
        return cache[mask]

    selected = select_edges(edges, dimension)
    direct, reciprocal = 0, 0
    for a, b in selected:
        wa, pa = get(a)
        wb, pb = get(b)
        x, y = pa[0], pa[1]
        direct_w, reciprocal_w = wa, 1 / wa
        matched = False
        for _ in range(1, 66):
            direct_w, reciprocal_w = direct_w**2, reciprocal_w**2
            x, y = x**2, y**2
            if direct_w == wb or reciprocal_w == wb:
                assert sign_key(x, y) == sign_key(pb[0], pb[1])
                if direct_w == wb:
                    direct += 1
                else:
                    reciprocal += 1
                matched = True
                break
        assert matched, (a, b)
    if dimension <= 10:
        key_to_label = {}
        label_to_key = {}
        for mask in ordered_masks:
            _, point = get(mask)
            key = orbit_key(point)
            label = labels.get(mask, mask)
            if key in key_to_label:
                assert key_to_label[key] == label
            else:
                key_to_label[key] = label
            if label in label_to_key:
                assert label_to_key[label] == key
            else:
                label_to_key[label] = key
        assert len(key_to_label) == len(label_to_key)
        # Translation by order-four torsion has the reciprocal W coordinate.
        for mask in ordered_masks[:16]:
            w, point = get(mask)
            partner = projected(1 / w)
            assert sign_key(point[0], point[1]) == sign_key(partner[0], partner[1])
        return {"sampled_edges": len(selected), "sampled_direct_edges": direct,
                "sampled_reciprocal_edges": reciprocal,
                "exhaustive_point_orbits": len(ordered_masks),
                "exhaustive_point_orbit_classes": len(key_to_label),
                "reciprocal_point_controls": 16}
    return {"sampled_edges": len(selected), "sampled_direct_edges": direct,
            "sampled_reciprocal_edges": reciprocal,
            "exhaustive_point_orbits": None,
            "exhaustive_point_orbit_classes": None,
            "reciprocal_point_controls": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimension", type=int, choices=(10, 24), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("verification output already exists")
    config = json.loads(CONFIG.read_text())
    assert sha256(ROUTE) == config["route_manifest_sha256"]
    expected_input_sha = (config["small_control_source_masks_sha256"]
                          if args.dimension == 10 else
                          config["source_masks_raw_sha256"])
    assert sha256(args.input) == expected_input_sha
    expected_count = 492 if args.dimension == 10 else config["source_signed_columns"]
    native, edges, labels, ordered_masks = check_graph(
        args.run_dir, args.input, args.dimension, expected_count)
    point_checks = check_points(args.dimension, edges, labels, ordered_masks)
    result = {
        "schema": "ecc2k130-w24-orbit-columns-sage-verification-v1",
        "status": "PASS_EXACT_GRAPH_AND_POINT_CONTROLS",
        "candidate_id": None,
        "dimension": args.dimension,
        "field_backend": native["field_backend"],
        "source_signed_columns": expected_count,
        "orbit_representatives": native["orbit_representatives"],
        "saved_columns": native["saved_columns"],
        "forest_edges_checked": len(edges),
        "point_checks": point_checks,
        "sage_version": sage_version,
        "input_sha256": sha256(args.input),
        "native_sha256": sha256(args.run_dir / "native.json"),
        "forest_sha256": sha256(args.run_dir / "forest.bin"),
        "component_map_sha256": sha256(args.run_dir / "nontrivial-components.bin"),
        "verifier_source_sha256": sha256(Path(__file__)),
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
