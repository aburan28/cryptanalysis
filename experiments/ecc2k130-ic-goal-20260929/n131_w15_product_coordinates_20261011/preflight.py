#!/usr/bin/env python3
"""Exact product coordinates for the two fixed-seed N131 W15 pair domains."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SUPPORT = PARENT / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
PREVIOUS = PARENT / "n131_w15_two_fixed_seeds_public_20261010" / "support_count.json"
N = 131
MASK = (1 << N) - 1
REDUCTION = (1 << 13) | (1 << 2) | (1 << 1) | 1
CASES = ((12004, 0, 4088), (9022, 13, 4170))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def multiply(a, b):
    answer = 0
    while b:
        if b & 1:
            answer ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a = (a & MASK) ^ REDUCTION
    return answer


def rotated_basis(rotation):
    result = [1 << (i + 1) for i in range(15)]
    for _ in range(rotation):
        result = [multiply(x, x) for x in result]
    return result


def build_case(seed_code, rotation, expected_count, columns):
    basis = rotated_basis(rotation)
    seed = 0
    for i in range(15):
        if seed_code >> i & 1:
            seed ^= basis[i]
    images = [multiply(w, w) ^ multiply(seed, w) for w in basis]
    vectors = {}
    selected = []
    for i, image in enumerate(images):
        value = image
        while value:
            pivot = value.bit_length() - 1
            if pivot not in vectors:
                vectors[pivot] = value
                selected.append(i)
                break
            value ^= vectors[pivot]
    missing = next(i for i in range(15) if i not in selected)
    assert len(selected) == 14 and seed_code >> missing & 1
    assert images[missing] == _xor(
        images[i] for i in selected if seed_code >> i & 1)

    accepted = set()
    checked = 0
    for code in range(1 << 14):
        a = sum((code >> j & 1) << i for j, i in enumerate(selected))
        b = a ^ seed_code
        assert a < b if seed_code >> missing & 1 else a != b
        w = _xor(basis[i] for i in range(15) if a >> i & 1)
        sw = _xor(basis[i] for i in range(15) if b >> i & 1)
        product = _xor(images[i] for i in range(15) if a >> i & 1)
        assert w ^ sw == seed and multiply(w, sw) == product
        checked += 1
        if a in columns and b in columns and columns[a] != columns[b]:
            accepted.add(code)
    assert checked == 16384 and len(accepted) == expected_count

    # Reduced ordered BDD over the product-coordinate bits.  This is a
    # target-independent exact membership certificate, not a solver result.
    nodes = [int(code in accepted) for code in range(1 << 14)]
    unique = {}
    graph = {}
    for bit in range(14):
        next_level = []
        for i in range(0, len(nodes), 2):
            lo, hi = nodes[i], nodes[i + 1]
            if lo == hi:
                next_level.append(lo)
                continue
            key = (bit, lo, hi)
            if key not in unique:
                node = len(graph) + 2
                unique[key] = node
                graph[node] = key
            next_level.append(unique[key])
        nodes = next_level
    root = nodes[0]
    assert root >= 2
    for code in range(1 << 14):
        node = root
        while node >= 2:
            bit, lo, hi = graph[node]
            node = hi if code >> bit & 1 else lo
        assert bool(node) == (code in accepted)
    implications = sum(int(lo != 1) + int(hi != 1)
                       for _, lo, hi in graph.values()) + 1
    return {"seed_code": seed_code, "rotation": rotation,
            "product_rank": len(selected), "selected_source_bit_positions": selected,
            "canonical_zero_bit": missing, "valid_unordered_pairs": len(accepted),
            "bdd_nodes": len(graph), "bdd_forward_clauses": implications,
            "accepted_codes_sha256": hashlib.sha256(
                b"".join(code.to_bytes(2, "little") for code in sorted(accepted))).hexdigest(),
            "product_basis": [images[i] for i in selected]}


def _xor(values):
    value = 0
    for item in values:
        value ^= item
    return value


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_N131_W15_PRODUCT_COORDINATE_PREFLIGHT"
    assert protocol["source_sha256"] == {
        "preflight": sha(Path(__file__)), "support": sha(SUPPORT),
        "previous_count": sha(PREVIOUS)}
    columns = {int(a): int(b) for a, b in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    assert len(columns) == 16441
    previous = json.loads(PREVIOUS.read_text())
    assert previous["unordered_distinct_column_pairs_by_seed"] == [4088, 4170]
    cases = [build_case(*case, columns) for case in CASES]
    result = {"status": "PASS_EXACT_PRODUCT_COORDINATE_SOURCE_BIJECTION",
              "curve_id": protocol["curve_id"], "source_sha256": protocol["source_sha256"],
              "cases": cases, "candidate_id": None, "target_count": 0}
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "cases": [
        {key: row[key] for key in ("seed_code", "product_rank", "valid_unordered_pairs", "bdd_nodes", "bdd_forward_clauses")}
        for row in cases]}))


if __name__ == "__main__":
    main()
