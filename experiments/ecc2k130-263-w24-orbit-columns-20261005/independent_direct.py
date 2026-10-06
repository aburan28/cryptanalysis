#!/usr/bin/env python3
"""Replay every direct W24 Frobenius overlap using GF(2) linear algebra.

This does not call the native field routines or traverse all eight million
source masks.  Each power restricts to a 24-dimensional binary linear map;
its intersection with W24 is a nullspace that can be enumerated exactly.
The reciprocal-overlap channel is checked by the two native backends, not by
this verifier.
"""

import argparse
import gzip
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "CONFIG.json"
MODULUS = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
DIMENSION = 24


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def square(value):
    product = 0
    while value:
        bit = value & -value
        product ^= 1 << (2 * (bit.bit_length() - 1))
        value ^= bit
    while product.bit_length() > 131:
        product ^= MODULUS << (product.bit_length() - 132)
    return product


def trace(value):
    start = value
    total = 0
    for _ in range(131):
        total ^= value
        value = square(value)
    assert value == start and total in (0, 1)
    return total


def nullspace(rows, width):
    rows = [row for row in rows if row]
    pivot_cols = []
    rank = 0
    for col in range(width):
        pivot = next((index for index in range(rank, len(rows))
                      if rows[index] & (1 << col)), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for index in range(len(rows)):
            if index != rank and rows[index] & (1 << col):
                rows[index] ^= rows[rank]
        pivot_cols.append(col)
        rank += 1
    assert all(row == 0 for row in rows[rank:])
    free_cols = [col for col in range(width) if col not in pivot_cols]
    vectors = []
    for free in free_cols:
        vector = 1 << free
        for pivot, row in zip(pivot_cols, rows[:rank]):
            if row & (1 << free):
                vector ^= 1 << pivot
        assert all((row & vector).bit_count() % 2 == 0 for row in rows)
        vectors.append(vector)
    return vectors


def span(vectors):
    values = [0]
    for vector in vectors:
        values += [value ^ vector for value in values]
    assert len(values) == 1 << len(vectors)
    assert len(values) == len(set(values))
    return values


def read_base(path, expected_gzip_hash, expected_raw_hash, expected_count):
    assert sha256(path) == expected_gzip_hash
    digest = hashlib.sha256()
    bitset = bytearray(1 << DIMENSION)
    previous = 0
    count = 0
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
            assert len(chunk) % 4 == 0
            for (mask,) in struct.iter_unpack("<I", chunk):
                assert 0 < mask < (1 << DIMENSION) and mask > previous
                bitset[mask] = 1
                previous = mask
                count += 1
    assert digest.hexdigest() == expected_raw_hash
    assert count == expected_count
    return bitset


def read_pairs(path):
    data = path.read_bytes()
    assert len(data) % 8 == 0
    return list(struct.iter_unpack("<II", data))


def partition_from_edges(edges):
    parent = {}

    def find(value):
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for a, b in edges:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a
    groups = defaultdict(list)
    for mask in parent:
        groups[find(mask)].append(mask)
    labels = []
    sizes = Counter()
    for masks in groups.values():
        minimum = min(masks)
        sizes[len(masks)] += 1
        labels.extend((mask, minimum) for mask in masks)
    return sorted(labels), sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    config = json.loads(CONFIG.read_text())
    assert config["w_dimension"] == DIMENSION
    assert config["field_modulus_exponents"] == [131, 13, 2, 1, 0]
    source = (HERE / config["source_masks_gzip"]).resolve()
    base = read_base(source, config["source_masks_gzip_sha256"],
                     config["source_masks_raw_sha256"],
                     config["source_signed_columns"])
    basis = [(1 << j) ^ trace(1 << j) for j in range(1, DIMENSION + 1)]
    assert all(trace(value) == 0 for value in basis)
    trace_bits = sum(trace(1 << j) << (j - 1)
                     for j in range(1, DIMENSION + 1))
    images = basis[:]
    triples = []
    per_power = []
    for power in range(1, 66):
        images = [square(value) for value in images]
        rows = [sum(((images[j] >> bit) & 1) << j
                    for j in range(DIMENSION)) for bit in range(25, 131)]
        vectors = nullspace(rows, DIMENSION)
        hits = 0
        for mask in span(vectors)[1:]:
            if not base[mask]:
                continue
            image = 0
            for j, value in enumerate(images):
                if mask & (1 << j):
                    image ^= value
            assert image < (1 << 25)
            other = image >> 1
            assert 0 < other < (1 << DIMENSION)
            assert (image & 1) == ((other & trace_bits).bit_count() & 1)
            assert base[other], "Frobenius failed to preserve rationality"
            triples.append((power, mask, other))
            hits += 1
        per_power.append({"power": power,
                          "W_intersection_dimension": len(vectors),
                          "W_intersection_nonzero_masks": (1 << len(vectors)) - 1,
                          "rational_direct_hits": hits})
    native_dir = HERE / "runs/w24-native"
    native = json.loads((native_dir / "native.json").read_text())
    assert len(triples) == native["direct_hits"]
    assert native["reciprocal_hits"] == 0
    direct_edges = [(a, b) for _, a, b in triples]
    labels, sizes = partition_from_edges(direct_edges)
    assert labels == read_pairs(native_dir / "nontrivial-components.bin")
    assert len(labels) == native["nontrivial_masks"]
    nontrivial_components = sum(sizes.values())
    assert nontrivial_components + config["source_signed_columns"] - len(labels) == \
        native["orbit_representatives"]
    assert config["source_signed_columns"] - native[
        "orbit_representatives"] == native["saved_columns"]
    output = {
        "schema": "ecc2k130-w24-independent-direct-overlap-v1",
        "status": "PASS_INDEPENDENT_DIRECT_AND_PARTITION_GIVEN_RECIPROCAL_ZERO",
        "candidate_id": None,
        "dimension": DIMENSION,
        "basis_trace_bits": trace_bits,
        "checked_powers": 65,
        "direct_hits": len(triples),
        "orbit_representatives_from_direct_edges": native["orbit_representatives"],
        "nontrivial_component_masks": len(labels),
        "nontrivial_component_histogram": {
            str(size): count for size, count in sorted(sizes.items())},
        "reciprocal_hits_independently_checked": False,
        "per_power": per_power,
        "source_masks_gzip_sha256": sha256(source),
        "native_component_map_sha256": sha256(
            native_dir / "nontrivial-components.bin"),
        "native_receipt_sha256": sha256(native_dir / "native.json"),
        "verifier_source_sha256": sha256(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: output[key] for key in (
        "status", "direct_hits", "orbit_representatives_from_direct_edges",
        "nontrivial_component_masks")}, indent=2))


if __name__ == "__main__":
    main()
