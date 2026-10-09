#!/usr/bin/env python3
"""Exact residue-cover and scalar-recoding screen for two tau buckets."""

from array import array
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INPUTS = ROOT / "experiments/prime-j0-radix943-word-20261009/inputs.json"
ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
LAMBDA_TAU = int("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0", 16)
V = (-238911465918039986966665730306072050094,
     303414439467246543595250775667605759171)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
RADIX = 1021
WINDOWS = 13
DIGIT_LENGTH_BOUND = 840
CAP_BYTES = 90 * (1 << 20)
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
    result = []
    value = pair
    for _ in range(3):
        result.extend((value, (-value[0], -value[1])))
        value = omega(value)
    assert value == pair
    return result


def index(pair):
    return pair[0] % RADIX * RADIX + pair[1] % RADIX


def nearest_digit(pair):
    a, b = pair
    u, v = a + b, -b
    fu, fv = u // RADIX, v // RADIX
    best = None
    for m in (fu, fu + 1):
        for n in (fv, fv + 1):
            x, y = u - m * RADIX, v - n * RADIX
            digit = (x + y, -y)
            candidate = (norm(digit), *digit)
            if best is None or candidate < best:
                best = candidate
    assert best is not None
    return best[1:]


def nearest_representative(scalar):
    fw = scalar * V[1] // ORDER
    fv = -(scalar * W[1]) // ORDER
    choices = []
    for i in (fw, fw + 1):
        for j in (fv, fv + 1):
            a = scalar - i * W[0] - j * V[0]
            b = -i * W[1] - j * V[1]
            choices.append((norm((a, b)), max(abs(a), abs(b)), a, b))
    _, _, a, b = min(choices)
    return a, b


def cycle_plan(cycle, lengths):
    """Minimum circular tiling with segment lengths 1..2, exact integer DP."""
    size = len(cycle)
    cuts = [0] + [size - j for j in (1, 2) if size > j]
    plans = []
    for cut in cuts:
        best = [size + 1] * (size + 1)
        choice = [0] * size
        best[size] = 0
        for pos in range(size - 1, -1, -1):
            maximum = min(lengths[(cut + pos) % size], size - pos)
            for step in range(1, maximum + 1):
                cost = 1 + best[pos + step]
                if cost < best[pos] or (cost == best[pos] and step > choice[pos]):
                    best[pos], choice[pos] = cost, step
        plans.append((best[0], cut, choice))
    cost, cut, choice = min(plans, key=lambda item: (item[0], item[1]))
    segments = []
    pos = 0
    while pos < size:
        step = choice[pos]
        assert 1 <= step <= lengths[(cut + pos) % size]
        segments.append((cut + pos, step))
        pos += step
    assert pos == size and len(segments) == cost
    return segments


def build_atlas():
    classes = RADIX * RADIX
    canonical = array("I", [EMPTY]) * classes
    nodes = []
    for residue in range(classes):
        if canonical[residue] != EMPTY:
            continue
        a, b = divmod(residue, RADIX)
        orbit = [index(pair) for pair in units((a, b))]
        assert min(orbit) == residue
        for member in orbit:
            assert canonical[member] == EMPTY or member == 0
            canonical[member] = residue
        nodes.append(residue)
    assert all(value != EMPTY for value in canonical)
    assert len(nodes) == 1 + (classes - 1) // 6

    visited = bytearray(classes)
    assigned = {}
    seeds = []
    cycle_hist = Counter()
    segment_hist = Counter()
    for origin in nodes:
        if visited[origin]:
            continue
        cycle = []
        current = origin
        while not visited[current]:
            visited[current] = 1
            cycle.append(current)
            a, b = divmod(current, RADIX)
            current = canonical[index(tau((a, b)))]
        assert current == origin
        cycle_hist[len(cycle)] += 1
        lengths = []
        for node in cycle:
            digit = nearest_digit(divmod(node, RADIX))
            assert index(digit) == node
            value = norm(digit)
            length = 1
            for exponent in (1,):
                if 3 ** exponent * value <= DIGIT_LENGTH_BOUND ** 2:
                    length = exponent + 1
            assert value <= DIGIT_LENGTH_BOUND ** 2
            lengths.append(length)
        for start, length in cycle_plan(cycle, lengths):
            node = cycle[start % len(cycle)]
            seed_id = len(seeds)
            seeds.append(nearest_digit(divmod(node, RADIX)))
            segment_hist[length] += 1
            for exponent in range(length):
                covered = cycle[(start + exponent) % len(cycle)]
                assert covered not in assigned
                assigned[covered] = (seed_id, exponent)
    assert len(assigned) == len(nodes)

    codes = array("I", [EMPTY]) * classes
    max_norm = 0
    for node, (seed_id, exponent) in assigned.items():
        digit = seeds[seed_id]
        for _ in range(exponent):
            digit = tau(digit)
        max_norm = max(max_norm, norm(digit))
        assert norm(digit) <= DIGIT_LENGTH_BOUND ** 2
        orbit = units(digit)
        for unit_code, image in enumerate(orbit):
            slot = index(image)
            assert canonical[slot] == node
            code = (seed_id << 5) | (exponent << 3) | unit_code
            if codes[slot] == EMPTY:
                codes[slot] = code
            else:
                assert slot == 0 and codes[slot] == 0
    assert all(code != EMPTY for code in codes)
    assert max_norm <= DIGIT_LENGTH_BOUND ** 2

    digest = hashlib.sha256()
    digest.update(codes.tobytes())
    for a, b in seeds:
        digest.update(a.to_bytes(2, "little", signed=True))
        digest.update(b.to_bytes(2, "little", signed=True))
    return codes, seeds, digest.hexdigest(), cycle_hist, segment_hist, max_norm


def digit_from_code(code, seeds):
    seed = seeds[code >> 5]
    exponent = code >> 3 & 3
    unit_code = code & 7
    assert exponent <= 1 and unit_code < 6
    for _ in range(exponent):
        seed = tau(seed)
    return units(seed)[unit_code], exponent


def main():
    assert sys.byteorder == "little"
    assert U[0] * V[1] - U[1] * V[0] == ORDER
    assert norm(W) == norm(V) == norm((W[0] + V[0], W[1] + V[1])) == ORDER
    assert RADIX % 2 and RADIX % 3
    power = RADIX ** WINDOWS
    geometric = (power - 1) // (RADIX - 1)
    remaining = power - DIGIT_LENGTH_BOUND * geometric
    assert remaining > 0 and ORDER < 3 * remaining * remaining

    codes, seeds, atlas_digest, cycles, segments, max_norm = build_atlas()
    for residue, code in enumerate(codes):
        digit, _ = digit_from_code(code, seeds)
        assert index(digit) == residue
        assert norm(digit) <= DIGIT_LENGTH_BOUND ** 2

    inputs = json.loads(INPUTS.read_text())
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == 519
    assert hashlib.sha256(b"".join(k.to_bytes(32, "big") for k in scalars)).hexdigest() == inputs["scalar_sha256"]
    addition_hist = Counter()
    bucket_hist = Counter()
    max_initial_norm = 0
    for scalar in scalars:
        start = nearest_representative(scalar)
        assert 3 * norm(start) <= ORDER
        max_initial_norm = max(max_initial_norm, norm(start))
        a, b = start
        digits = []
        buckets = [0, 0]
        for _ in range(WINDOWS):
            digit, exponent = digit_from_code(codes[index((a, b))], seeds)
            assert (a - digit[0]) % RADIX == (b - digit[1]) % RADIX == 0
            digits.append(digit)
            if digit != (0, 0):
                buckets[exponent] += 1
            a, b = (a - digit[0]) // RADIX, (b - digit[1]) // RADIX
        assert (a, b) == (0, 0)
        assert tuple(sum(d[j] * RADIX ** i for i, d in enumerate(digits)) for j in (0, 1)) == start
        assert (start[0] + start[1] * LAMBDA_TAU - scalar) % ORDER == 0
        active = sum(buckets)
        addition_hist[max(0, active - 1)] += 1
        bucket_hist[tuple(buckets)] += 1

    entries = WINDOWS * len(seeds)
    retained = entries * 72 + len(codes) * 4 + len(seeds) * 4 + 256
    atlas_bytes = (b"TBP1" + RADIX.to_bytes(4, "little")
                   + len(codes).to_bytes(4, "little")
                   + len(seeds).to_bytes(4, "little") + codes.tobytes()
                   + b"".join(a.to_bytes(2, "little", signed=True)
                              + b.to_bytes(2, "little", signed=True) for a, b in seeds))
    assert len(atlas_bytes) == 16 + len(codes) * 4 + len(seeds) * 4
    atlas_path = HERE / "atlas.bin"
    atlas_path.write_bytes(atlas_bytes)
    result = {
        "schema": 1,
        "format": "tau-pair-buckets",
        "radix": RADIX,
        "windows": WINDOWS,
        "digit_length_bound": DIGIT_LENGTH_BOUND,
        "termination_remaining": str(remaining),
        "termination_strict": True,
        "residue_pairs_checked": len(codes),
        "unit_orbits": 1 + (len(codes) - 1) // 6,
        "tau_cycles_by_length": {str(k): v for k, v in sorted(cycles.items())},
        "segments_by_length": {str(k): v for k, v in sorted(segments.items())},
        "seed_count_per_row": len(seeds),
        "point_entries": entries,
        "declared_retained_bytes": retained,
        "under_90_mib_cap": retained < CAP_BYTES,
        "max_digit_norm": max_norm,
        "atlas_sha256": atlas_digest,
        "atlas_file_sha256": hashlib.sha256(atlas_bytes).hexdigest(),
        "atlas_file_bytes": len(atlas_bytes),
        "screen_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": inputs["scalar_sha256"],
        "scalar_reconstructions": len(scalars),
        "max_initial_norm": str(max_initial_norm),
        "addition_histogram": {str(k): v for k, v in sorted(addition_hist.items())},
        "bucket_histogram": {str(k): v for k, v in sorted(bucket_hist.items())},
        "native_verified": False,
        "controlled_cpu_timing": None,
    }
    (HERE / "screen-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("seed_count_per_row", "point_entries",
                                                "declared_retained_bytes", "under_90_mib_cap",
                                                "scalar_reconstructions")}, sort_keys=True))


if __name__ == "__main__":
    main()
