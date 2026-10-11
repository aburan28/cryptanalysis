"""Exhaustively compare the variable-seed inverse with raw W6 pairs."""

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
N = 41
D = 6
MOD = (1 << 41) | (1 << 3) | 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def multiply(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a ^= MOD
    return result


def square(a):
    return multiply(a, a)


def inverse(a):
    assert a
    u, v, x, y = a, MOD, 1, 0
    while u != 1:
        shift = u.bit_length() - v.bit_length()
        if shift < 0:
            u, v = v, u
            x, y = y, x
            shift = -shift
        u ^= v << shift
        x ^= y << shift
    while x.bit_length() > N:
        x ^= MOD << (x.bit_length() - N - 1)
    assert multiply(a, x) == 1
    return x


def halftrace(value):
    result = value
    power = value
    for _ in range((N - 1) // 2):
        power = square(square(power))
        result ^= power
    return result


def trace(value):
    h = halftrace(value)
    out = square(h) ^ h ^ value
    assert out in (0, 1)
    return out


def pair_outputs(a, b):
    seed = a ^ b
    product = multiply(a, b)
    assert product not in (0, 1)
    coefficient = 1 ^ square(product)
    rhs = multiply(multiply(coefficient, square(seed)), inverse(square(product)))
    assert trace(rhs) == 0
    h = halftrace(rhs)
    scale = multiply(product, inverse(coefficient))
    roots = [multiply(scale, h), multiply(scale, h ^ 1)]
    for root in roots:
        assert root and multiply(coefficient, square(root)) ^ multiply(product, root) ^ square(seed) == 0
    return roots


def solve(c, half_basis):
    basis = [1 << (index + 1) for index in range(D)]
    inverse_c = inverse(c)
    c2 = square(c)
    hc = halftrace(c2)
    columns = [multiply(h, inverse_c) for h in half_basis] + [inverse_c]
    constant = multiply(hc, inverse_c)
    rows = []
    for coordinate in range(N):
        if 2 <= coordinate <= 2 * D:
            continue
        row = ((constant >> coordinate) & 1) << (D + 1)
        for variable, value in enumerate(columns):
            row ^= ((value >> coordinate) & 1) << variable
        rows.append(row)
    trace_row = trace(c2) << (D + 1)
    for variable, basis_element in enumerate(basis):
        trace_row ^= trace(square(basis_element)) << variable
    rows.append(trace_row)
    pivots = {}
    rank = 0
    for variable in range(D + 1):
        found = next((index for index in range(rank, len(rows))
                      if rows[index] & (1 << variable)), None)
        if found is None:
            continue
        rows[rank], rows[found] = rows[found], rows[rank]
        for index in range(len(rows)):
            if index != rank and rows[index] & (1 << variable):
                rows[index] ^= rows[rank]
        pivots[variable] = rank
        rank += 1
    if any(row == (1 << (D + 1)) for row in rows[rank:]):
        return rank, []
    fixed = sum(((rows[row] >> (D + 1)) & 1) << variable
                for variable, row in pivots.items())
    free = [variable for variable in range(D + 1) if variable not in pivots]
    solutions = []
    for choice in range(1 << len(free)):
        value = fixed
        for index, free_variable in enumerate(free):
            if choice & (1 << index):
                value ^= 1 << free_variable
                for pivot_variable, row in pivots.items():
                    value ^= ((rows[row] >> free_variable) & 1) << pivot_variable
        solutions.append(value)
    return rank, solutions


def image_inverse(seedmask, product):
    seed = seedmask << 1
    pivots = {}
    kernel = None
    for index in range(D):
        basis = 1 << (index + 1)
        value = square(basis) ^ multiply(seed, basis)
        represented = 1 << index
        while value:
            leading = value.bit_length() - 1
            if leading not in pivots:
                pivots[leading] = (value, represented)
                break
            pivot, pivot_mask = pivots[leading]
            value ^= pivot
            represented ^= pivot_mask
        if not value:
            assert kernel is None
            kernel = represented
    assert kernel == seedmask and len(pivots) == D - 1
    represented = 0
    for leading in sorted(pivots, reverse=True):
        if product & (1 << leading):
            pivot, pivot_mask = pivots[leading]
            product ^= pivot
            represented ^= pivot_mask
    if product:
        return None
    return tuple(sorted((represented, represented ^ seedmask)))


def main():
    protocol = json.loads((HERE / "n41_protocol.json").read_text())
    assert protocol["status"] == "frozen"
    assert protocol["source_sha256"] == digest(HERE / "n41_control.py")
    assert not (HERE / "n41_result.json").exists()
    support = [mask for mask in range(1, 1 << D)
               if trace((mask << 1) ^ inverse(square(mask << 1))) == 0]
    assert len(support) == 32
    source_pairs = defaultdict(set)
    for first_index, a_mask in enumerate(support):
        for b_mask in support[first_index + 1:]:
            for coordinate in pair_outputs(a_mask << 1, b_mask << 1):
                source_pairs[coordinate].add((a_mask, b_mask))
    support_set = set(support)
    basis = [1 << (index + 1) for index in range(D)]
    half_basis = [halftrace(square(value)) for value in basis]
    rng = random.Random(protocol["rng_seed"])
    controls = set()
    while len(controls) < protocol["trace_zero_controls"]:
        value = rng.getrandbits(N)
        candidate = square(value) ^ value
        if candidate and candidate not in source_pairs:
            controls.add(candidate)
    rank_counts = Counter()
    solved = 0
    candidate_count = 0
    for coordinate in list(source_pairs) + sorted(controls):
        rank, solutions = solve(coordinate, half_basis)
        rank_counts[rank] += 1
        candidate_count += len(solutions)
        found = set()
        for solution in solutions:
            seedmask = solution & ((1 << D) - 1)
            branch = (solution >> D) & 1
            if not seedmask:
                continue
            seed = seedmask << 1
            hc = halftrace(square(coordinate))
            hseed = 0
            for index in range(D):
                if seedmask & (1 << index):
                    hseed ^= half_basis[index]
            product = multiply(hc ^ hseed ^ branch, inverse(coordinate))
            assert product.bit_length() <= 2 * D + 1 and product & 3 == 0
            assert multiply(1 ^ square(product), square(coordinate)) ^ multiply(product, coordinate) ^ square(seed) == 0
            pair = image_inverse(seedmask, product)
            if pair is not None and pair[0] in support_set and pair[1] in support_set:
                found.add(pair)
        assert found == source_pairs.get(coordinate, set())
        solved += bool(found)
    result = {"status": "EXHAUSTIVE_PAIR_SET_MATCH", "curve_id": protocol["curve_id"],
              "protocol_sha256": digest(HERE / "n41_protocol.json"),
              "source_sha256": digest(HERE / "n41_control.py"),
              "rational_masks": len(support),
              "unordered_mask_pairs": len(support) * (len(support) - 1) // 2,
              "distinct_pair_outputs": len(source_pairs),
              "trace_zero_controls": len(controls),
              "coordinates_with_source_pair": solved,
              "linear_candidates": candidate_count,
              "rank_counts": dict(sorted(rank_counts.items()))}
    (HERE / "n41_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "distinct_pair_outputs": len(source_pairs),
                      "trace_zero_controls": len(controls)}))


if __name__ == "__main__":
    main()
