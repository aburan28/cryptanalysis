#!/usr/bin/env python3
"""Exact finite cover and scalar recoding for the radix-384 tau matching atlas."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
V = (-238911465918039986966665730306072050094,
     303414439467246543595250775667605759171)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
RADIX = 384
WINDOWS = 15
DIGIT_LENGTH_BOUND = 253
EMPTY = 0xFFFFFFFF


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def units(pair):
    out = []
    for _ in range(3):
        out.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return out


def index(pair):
    return pair[0] % RADIX * RADIX + pair[1] % RADIX


def nearest_digit(pair):
    a, b = pair
    u, v = a + b, -b
    fu, fv = u // RADIX, v // RADIX
    return min((norm((u - m * RADIX + v - n * RADIX, n * RADIX - v)),
                u - m * RADIX + v - n * RADIX, n * RADIX - v)
               for m in (fu, fu + 1) for n in (fv, fv + 1))[1:]


def nearest_representative(scalar):
    fw = scalar * V[1] // ORDER
    fv = -(scalar * W[1]) // ORDER
    candidates = []
    for i in (fw, fw + 1):
        for j in (fv, fv + 1):
            a = scalar - i * W[0] - j * V[0]
            b = -i * W[1] - j * V[1]
            candidates.append((norm((a, b)), max(abs(a), abs(b)), a, b))
    _, _, a, b = min(candidates)
    return a, b


def canonical_classes():
    canonical = [EMPTY] * (RADIX * RADIX)
    nodes = []
    for residue in range(len(canonical)):
        if canonical[residue] != EMPTY:
            continue
        orbit = [index(pair) for pair in units(divmod(residue, RADIX))]
        assert min(orbit) == residue
        for member in orbit:
            assert canonical[member] in (EMPTY, residue)
            canonical[member] = residue
        nodes.append(residue)
    assert len(nodes) == 24_578 and EMPTY not in canonical
    return canonical, nodes


def matching_forest(nodes, canonical):
    graph = defaultdict(set)
    directed = set()
    for node in nodes:
        digit = nearest_digit(divmod(node, RADIX))
        target = canonical[index(tau(digit))]
        if target != node and 3 * norm(digit) <= DIGIT_LENGTH_BOUND ** 2:
            graph[node].add(target)
            graph[target].add(node)
            directed.add((node, target))

    # Any cycle would invalidate the tree-DP optimality certificate.
    parent, order, roots = {}, [], []
    for root in sorted(graph):
        if root in parent:
            continue
        roots.append(root)
        parent[root] = None
        stack = [root]
        while stack:
            vertex = stack.pop()
            order.append(vertex)
            for child in sorted(graph[vertex], reverse=True):
                if child == parent[vertex]:
                    continue
                assert child not in parent, ("cycle", vertex, child)
                parent[child] = vertex
                stack.append(child)

    # free[v]: parent edge absent; used[v]: parent edge occupies v.
    free, used, selected_child = {}, {}, {}
    for vertex in reversed(order):
        children = sorted(child for child in graph[vertex]
                          if parent.get(child) == vertex)
        base = sum(free[child] for child in children)
        used[vertex] = base
        best_gain, best_child = 0, None
        for child in children:
            gain = 1 + used[child] - free[child]
            if gain > best_gain:
                best_gain, best_child = gain, child
        free[vertex] = base + best_gain
        selected_child[vertex] = best_child

    matching = []
    stack = [(root, False) for root in reversed(roots)]
    while stack:
        vertex, occupied = stack.pop()
        chosen = None if occupied else selected_child[vertex]
        if chosen is not None:
            matching.append((vertex, chosen))
        for child in sorted(graph[vertex], reverse=True):
            if parent.get(child) == vertex:
                stack.append((child, child == chosen))
    assert len(matching) == sum(free[root] for root in roots)
    assert len({v for edge in matching for v in edge}) == 2 * len(matching)

    oriented = []
    for a, b in matching:
        first, second = sorted((a, b))
        source, target = ((first, second) if (first, second) in directed
                          else (second, first))
        assert (source, target) in directed
        oriented.append((source, target))
    return oriented, {
        "edges": sum(len(adjacency) for adjacency in graph.values()) // 2,
        "directed_edges": len(directed),
        "vertices_with_edges": len(graph),
        "components_with_edges": len(roots),
        "maximum_matching": len(matching),
    }


def build_atlas():
    canonical, nodes = canonical_classes()
    matching, graph_receipt = matching_forest(nodes, canonical)
    assigned = {0: (0, 0)}
    seeds = [(0, 0)]
    for source, target in sorted(matching):
        seed_id = len(seeds)
        seeds.append(nearest_digit(divmod(source, RADIX)))
        assigned[source] = (seed_id, 0)
        assigned[target] = (seed_id, 1)
    for node in nodes:
        if node not in assigned:
            seed_id = len(seeds)
            seeds.append(nearest_digit(divmod(node, RADIX)))
            assigned[node] = (seed_id, 0)
    assert len(seeds) == len(nodes) - len(matching)

    codes = [EMPTY] * (RADIX * RADIX)
    exponent_hist = Counter()
    max_norm = 0
    for node in nodes:
        seed_id, exponent = assigned[node]
        digit = seeds[seed_id] if exponent == 0 else tau(seeds[seed_id])
        assert canonical[index(digit)] == node
        max_norm = max(max_norm, norm(digit))
        assert norm(digit) <= DIGIT_LENGTH_BOUND ** 2
        exponent_hist[exponent] += 1
        for unit_code, image in enumerate(units(digit)):
            slot = index(image)
            assert canonical[slot] == node
            if codes[slot] == EMPTY:
                codes[slot] = (seed_id << 4) | (exponent << 3) | unit_code
    assert EMPTY not in codes
    for residue, code in enumerate(codes):
        digit, _ = digit_from_code(code, seeds)
        assert index(digit) == residue
        assert norm(digit) <= DIGIT_LENGTH_BOUND ** 2
    return codes, seeds, graph_receipt, dict(exponent_hist), max_norm


def digit_from_code(code, seeds):
    seed = seeds[code >> 4]
    exponent = (code >> 3) & 1
    unit_code = code & 7
    assert unit_code < 6
    digit = seed if exponent == 0 else tau(seed)
    return units(digit)[unit_code], exponent


def check_panel(path, codes, seeds):
    raw = path.read_bytes()
    panel = json.loads(raw)
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == panel["count"] == 4096
    assert len(set(scalars)) == len(scalars)
    assert sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest() == panel["scalar_sha256"]
    selected = Counter()
    maximum = 0
    for scalar in scalars:
        representative = nearest_representative(scalar)
        assert 3 * norm(representative) <= ORDER
        a, b = representative
        reconstruction = [0, 0]
        power = 1
        for _ in range(WINDOWS):
            digit, exponent = digit_from_code(codes[index((a, b))], seeds)
            assert (a - digit[0]) % RADIX == (b - digit[1]) % RADIX == 0
            assert norm(digit) <= DIGIT_LENGTH_BOUND ** 2
            reconstruction[0] += power * digit[0]
            reconstruction[1] += power * digit[1]
            selected[exponent] += int(digit != (0, 0))
            a, b = (a - digit[0]) // RADIX, (b - digit[1]) // RADIX
            power *= RADIX
        assert (a, b) == (0, 0)
        assert tuple(reconstruction) == representative
        maximum = max(maximum, norm(representative))
    return {"file_sha256": sha256(raw).hexdigest(), "scalar_sha256": panel["scalar_sha256"],
            "cases": len(scalars), "nonidentity_by_bucket": dict(selected),
            "maximum_representative_norm": maximum}


def main():
    assert U[0] * V[1] - U[1] * V[0] == ORDER
    assert norm(W) == norm(V) == norm((W[0] + V[0], W[1] + V[1])) == ORDER
    power = RADIX ** WINDOWS
    geometric = (power - 1) // (RADIX - 1)
    margin = 3 * (power - DIGIT_LENGTH_BOUND * geometric) ** 2 - ORDER
    assert margin > 0
    assert 3 * (power - (DIGIT_LENGTH_BOUND + 1) * geometric) ** 2 < ORDER

    codes, seeds, graph, exponents, maximum = build_atlas()
    binary = bytearray(b"T384" + struct.pack("<I", len(seeds)))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for seed in seeds:
        binary.extend(struct.pack("<hh", *seed))
    atlas_path = HERE / "atlas.bin"
    atlas_path.write_bytes(binary)
    panels = {}
    for name in ("prime-j0-radix384-20261010", "prime-j0-radix384-fast-20261010"):
        path = ROOT / "experiments" / name / "fresh-inputs.json"
        panels[name] = check_panel(path, codes, seeds)
    result = {
        "schema": "prime-j0-tau384-matching-screen-v1",
        "radix": RADIX, "windows": WINDOWS, "digit_length_bound": DIGIT_LENGTH_BOUND,
        "termination_margin": str(margin), "residue_classes": RADIX * RADIX,
        "unit_classes": 24_578, "graph": graph, "seed_count": len(seeds),
        "class_exponents": exponents, "maximum_digit_norm": maximum,
        "atlas_bytes": len(binary), "atlas_sha256": sha256(binary).hexdigest(),
        "point_payload_bytes": WINDOWS * len(seeds) * 64,
        "screen_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "panels": panels,
    }
    (HERE / "screen-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
