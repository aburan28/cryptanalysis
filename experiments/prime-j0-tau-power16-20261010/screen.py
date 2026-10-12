#!/usr/bin/env python3
"""Exact two-bucket cycle covers for the mixed-width power-of-two format."""

from collections import Counter
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
WIDTHS = (8,) * 15 + (9,)
LIMITS = {8: 256, 9: 363}
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


def index(pair, radix):
    return pair[0] % radix * radix + pair[1] % radix


def nearest_digit(pair, radix):
    a, b = pair
    u, v = a + b, -b
    fu, fv = u // radix, v // radix
    return min((norm((u - m * radix + v - n * radix, n * radix - v)),
                u - m * radix + v - n * radix, n * radix - v)
               for m in (fu, fu + 1) for n in (fv, fv + 1))[1:]


def representative(scalar):
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


def cycle_plan(cycle, eligible):
    size = len(cycle)
    cuts = (0, size - 1) if size > 1 else (0,)
    candidates = []
    for cut in cuts:
        best = [size + 1] * (size + 1)
        steps = [0] * size
        best[size] = 0
        for pos in range(size - 1, -1, -1):
            maximum = min(2 if eligible[(cut + pos) % size] else 1, size - pos)
            for step in range(1, maximum + 1):
                cost = 1 + best[pos + step]
                if cost < best[pos] or (cost == best[pos] and step > steps[pos]):
                    best[pos], steps[pos] = cost, step
        candidates.append((best[0], cut, steps))
    cost, cut, steps = min(candidates, key=lambda item: (item[0], item[1]))
    segments = []
    pos = 0
    while pos < size:
        step = steps[pos]
        assert step in (1, 2)
        segments.append(((cut + pos) % size, step))
        pos += step
    assert pos == size and len(segments) == cost
    return segments


def build_atlas(width):
    radix = 1 << width
    limit = LIMITS[width]
    class_count = radix * radix
    canonical = [EMPTY] * class_count
    nodes = []
    for residue in range(class_count):
        if canonical[residue] != EMPTY:
            continue
        orbit = [index(pair, radix) for pair in units(divmod(residue, radix))]
        assert min(orbit) == residue
        for member in orbit:
            assert canonical[member] in (EMPTY, residue)
            canonical[member] = residue
        nodes.append(residue)
    assert EMPTY not in canonical
    assert len(nodes) == (class_count + 8) // 6

    successor = {}
    incoming = Counter()
    for node in nodes:
        digit = nearest_digit(divmod(node, radix), radix)
        target = canonical[index(tau(digit), radix)]
        successor[node] = target
        incoming[target] += 1
    assert set(successor.values()) == set(nodes)
    assert all(incoming[node] == 1 for node in nodes)

    seeds = [(0, 0)]
    assigned = {0: (0, 0)}
    visited = set()
    cycles = Counter()
    segments = Counter()
    eligible_count = 0
    for origin in nodes:
        if origin in visited:
            continue
        cycle = []
        current = origin
        while current not in visited:
            visited.add(current)
            cycle.append(current)
            current = successor[current]
        assert current == origin
        cycles[len(cycle)] += 1
        eligibility = []
        for node in cycle:
            direct = nearest_digit(divmod(node, radix), radix)
            flag = 3 * norm(direct) <= limit * limit
            eligibility.append(flag)
            eligible_count += flag
        for start, length in cycle_plan(cycle, eligibility):
            segments[length] += 1
            node = cycle[start]
            if node == 0:
                assert length == 1 and assigned[node] == (0, 0)
                continue
            seed_id = len(seeds)
            seeds.append(nearest_digit(divmod(node, radix), radix))
            for exponent in range(length):
                covered = cycle[(start + exponent) % len(cycle)]
                assert covered not in assigned
                assigned[covered] = (seed_id, exponent)
    assert len(assigned) == len(nodes)
    assert len(seeds) == sum(segments.values())

    codes = [EMPTY] * class_count
    max_norm = 0
    for node in nodes:
        seed_id, exponent = assigned[node]
        seed = seeds[seed_id]
        digit = seed if exponent == 0 else tau(seed)
        assert canonical[index(digit, radix)] == node
        max_norm = max(max_norm, norm(digit))
        assert norm(digit) <= limit * limit
        for unit_code, image in enumerate(units(digit)):
            slot = index(image, radix)
            assert canonical[slot] == node
            if codes[slot] == EMPTY:
                codes[slot] = (seed_id << 4) | (exponent << 3) | unit_code
    assert EMPTY not in codes
    for residue, code in enumerate(codes):
        digit, _ = digit_from_code(code, seeds)
        assert index(digit, radix) == residue
        assert norm(digit) <= limit * limit

    binary = bytearray(b"T2B" + bytes([ord(str(width))])
                       + struct.pack("<I", len(seeds)))
    binary.extend(struct.pack(f"<{len(codes)}I", *codes))
    for seed in seeds:
        binary.extend(struct.pack("<hh", *seed))
    path = HERE / f"atlas-w{width}.bin"
    path.write_bytes(binary)
    receipt = {"width": width, "radix": radix, "digit_length_bound": limit,
               "residues": class_count, "unit_classes": len(nodes),
               "cycle_lengths": dict(cycles), "eligible_classes": eligible_count,
               "segment_lengths": dict(segments), "seed_count": len(seeds),
               "max_digit_norm": max_norm, "atlas_bytes": len(binary),
               "atlas_sha256": sha256(binary).hexdigest()}
    return codes, seeds, receipt


def digit_from_code(code, seeds):
    seed = seeds[code >> 4]
    exponent = (code >> 3) & 1
    unit_code = code & 7
    assert unit_code < 6
    digit = seed if exponent == 0 else tau(seed)
    return units(digit)[unit_code], exponent


def check_panel(path, atlases):
    raw = path.read_bytes()
    panel = json.loads(raw)
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == panel["count"] == 4096
    assert len(set(scalars)) == len(scalars)
    assert sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest() == panel["scalar_sha256"]
    bucket_counts = Counter()
    max_initial_norm = 0
    for scalar in scalars:
        start = representative(scalar)
        assert 3 * norm(start) <= ORDER
        max_initial_norm = max(max_initial_norm, norm(start))
        a, b = start
        reconstruction = [0, 0]
        power = 1
        for width in WIDTHS:
            radix = 1 << width
            codes, seeds = atlases[width]
            digit, exponent = digit_from_code(codes[index((a, b), radix)], seeds)
            assert norm(digit) <= LIMITS[width] ** 2
            assert (a - digit[0]) % radix == (b - digit[1]) % radix == 0
            reconstruction[0] += power * digit[0]
            reconstruction[1] += power * digit[1]
            bucket_counts[exponent] += int(digit != (0, 0))
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
            power *= radix
        assert (a, b) == (0, 0) and tuple(reconstruction) == start
    return {"cases": len(scalars), "file_sha256": sha256(raw).hexdigest(),
            "scalar_sha256": panel["scalar_sha256"],
            "nonidentity_by_bucket": dict(bucket_counts),
            "maximum_representative_norm": max_initial_norm}


def main():
    assert U[0] * V[1] - U[1] * V[0] == ORDER
    assert norm(W) == norm(V) == norm((W[0] + V[0], W[1] + V[1])) == ORDER
    product = 256 ** 15 * 512
    lower_sum = 256 * (256 ** 15 - 1) // 255
    digit_sum = lower_sum + 363 * 256 ** 15
    margin = 3 * (product - digit_sum) ** 2 - ORDER
    assert margin > 0
    assert 3 * (product - digit_sum - 256 ** 15) ** 2 < ORDER

    atlas8 = build_atlas(8)
    atlas9 = build_atlas(9)
    atlases = {8: atlas8[:2], 9: atlas9[:2]}
    panels = {}
    for name in ("prime-j0-cache-window-20261010",
                 "prime-j0-tau384-matching-20261010"):
        path = ROOT / "experiments" / name / "fresh-inputs.json"
        panels[name] = check_panel(path, atlases)
    point_slots = 15 * len(atlas8[1]) + len(atlas9[1])
    result = {"schema": "prime-j0-tau-power16-screen-v1",
              "widths": WIDTHS, "termination_margin": str(margin),
              "atlas8": atlas8[2], "atlas9": atlas9[2],
              "point_slots": point_slots, "point_payload_bytes": 64 * point_slots,
              "screen_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "panels": panels}
    (HERE / "screen-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
