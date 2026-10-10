#!/usr/bin/env python3
"""Check whether one zero-sum triple block admits a compact output signature."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def binary_rank(values):
    pivots = {}
    for value in values:
        while value:
            pivot = value.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = value
                break
            value ^= pivots[pivot]
    return len(pivots)


def degree_two_evaluation(value, n):
    row = 1 | (value << 1)
    offset = n + 1
    for j in range(1, n):
        if (value >> j) & 1:
            row |= (value & ((1 << j) - 1)) << offset
        offset += j
    return row


def main():
    output = HERE / "signature_result.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "signature_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(polynomial([(int(value) >> i) & 1 for i in range(41)]))

    def half_trace(value):
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        return result

    lines = (HERE / "input_public.txt").read_text().splitlines()
    rotation, count = map(int, lines[1].split())
    assert rotation == 0 and count == 126
    seeds = {}
    for line in lines[2:2 + count]:
        mask, sign, column, x, y = map(int, line.split())
        w = sum((field(t**(i + 1)) for i in range(7) if mask >> i & 1),
                field.zero())
        u = half_trace(w)
        raw = curve.lift_x(1 + 1/u, all=True)
        projected = curve(decode(x), decode(y))
        matching = [point for point in raw if 4*point == projected]
        assert len(matching) == 1
        seeds[(mask, sign)] = (matching[0], projected, column)
    masks = sorted({mask for mask, _ in seeds})
    assert len(masks) == 63
    shapes = [(a, b, a ^ b) for a in masks for b in masks
              if a < b < (a ^ b) and (a ^ b) in masks]
    assert len(shapes) == 317

    output_points = []
    z_values = []
    z_as_w_values = []
    exceptional = 0
    rejected = 0
    for shape in shapes:
        for branch in range(8):
            selected = [seeds[(mask, (branch >> i) & 1)]
                        for i, mask in enumerate(shape)]
            if len({item[2] for item in selected}) < 3:
                rejected += 1
                continue
            raw_sum = sum((item[0] for item in selected), curve(0))
            group_sum = sum((item[1] for item in selected), curve(0))
            assert 4*raw_sum == group_sum
            output_points.append(group_sum)
            if raw_sum == curve(0) or raw_sum[0] == 1:
                exceptional += 1
                continue
            z = 1 / (raw_sum[0] + 1)
            z_values.append(encode(z))
            z_as_w_values.append(encode(z*z + z))

    assert len(output_points) == 2520 and rejected == 16
    source_w = {encode(sum((field(t**(i + 1)) for i in range(7)
                            if mask >> i & 1), field.zero()))
                for mask in range(128)}
    source_u = {encode(half_trace(decode(w))) for w in source_w}
    source_u |= {encode(decode(u) + 1) for u in tuple(source_u)}
    point_keys = {(encode(point[0]), encode(point[1])) for point in output_points}
    z_degree_two_rank = binary_rank(degree_two_evaluation(z, 41) for z in z_values)
    result = {
        "status": "PASS_EXACT_SIGNATURE_SCREEN",
        "proposal_id": "Q20261009195000",
        "source_states": len(output_points),
        "exceptional_raw_sums": exceptional,
        "unique_projected_group_sums": len(point_keys),
        "unique_z_values": len(set(z_values)),
        "z_binary_linear_rank": binary_rank(z_values),
        "z_boolean_degree_two_rank": z_degree_two_rank,
        "z_boolean_degree_two_dimension": 1 + 41 + 41*40//2,
        "z_in_source_halftrace_fiber_count": sum(z in source_u for z in z_values),
        "z_square_plus_z_in_source_w_count": sum(w in source_w for w in z_as_w_values),
        "scope": "all admissible signed zero-sum triples in rotation zero of the exact N41 W7 base",
        "sha256": {"source": sha(__file__),
                   "input": sha(HERE / "input_public.txt"),
                   "geometry": sha(HERE / "geometry_result.json"),
                   "runtime": sha(HERE / "signature_runtime_info.json")},
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
