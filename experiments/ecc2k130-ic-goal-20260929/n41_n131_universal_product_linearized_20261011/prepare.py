"""Freeze diverse W18 pair-output positives and trace-zero field controls."""

import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
N = 131
MOD = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
MASK = (1 << N) - 1
ROTATIONS = (0, 13, 26, 39, 52, 65)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a, b):
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
    return mul(a, a)


def inverse(value):
    assert 0 < value < (1 << N)
    a, b, x, y = value, MOD, 1, 0
    while a != 1:
        shift = a.bit_length() - b.bit_length()
        if shift < 0:
            a, b = b, a
            x, y = y, x
            shift = -shift
        a ^= b << shift
        x ^= y << shift
    while x.bit_length() > N:
        x ^= MOD << (x.bit_length() - N - 1)
    assert mul(value, x) == 1
    return x


def halftrace(value):
    result = value
    power = value
    for _ in range(65):
        power = square(square(power))
        result ^= power
    return result


def rotate(value, exponent):
    for _ in range(exponent):
        value = square(value)
    return value


def main():
    protocol = json.loads((HERE / "prepare_protocol.json").read_text())
    assert protocol["status"] == "frozen"
    assert protocol["prepare_sha256"] == digest(HERE / "prepare.py")
    assert protocol["support_sha256"] == digest(SOURCE)
    assert not (HERE / "panel.json").exists()
    support = {}
    for line in SOURCE.read_text().splitlines():
        mask, column = map(int, line.split())
        assert mask not in support and 0 < mask < (1 << 18)
        support[mask] = column
    assert len(support) == 131307
    masks = sorted(support)
    rng = random.Random(protocol["rng_seed"])
    archived_path = BASE / "n131_w18_allseed_pair_inverse_20261011/protocol.json"
    assert protocol["archived_protocol_sha256"] == digest(archived_path)
    archived = json.loads(archived_path.read_text())
    cases = [{**case, "law": "archived_exact_control"} for case in archived["cases"]]
    selected_seeds = set()
    positive_coordinates = set()
    for pair_index in range(protocol["positive_pairs"]):
        while True:
            a, b = sorted(rng.sample(masks, 2))
            seedmask = a ^ b
            if support[a] != support[b] and seedmask not in selected_seeds:
                selected_seeds.add(seedmask)
                break
        wa, wb, seed = a << 1, b << 1, seedmask << 1
        product = mul(wa, wb)
        assert product not in (0, 1)
        coefficient = 1 ^ square(product)
        rhs = mul(mul(coefficient, square(seed)), inverse(square(product)))
        h = halftrace(rhs)
        assert square(h) ^ h ^ rhs == 0
        scale = mul(product, inverse(coefficient))
        rotation = ROTATIONS[pair_index % len(ROTATIONS)]
        for branch, root in enumerate((h, h ^ 1)):
            unrotated = mul(scale, root)
            assert unrotated != 0
            assert mul(coefficient, square(unrotated)) ^ mul(product, unrotated) ^ square(seed) == 0
            coordinate = rotate(unrotated, rotation)
            assert coordinate not in positive_coordinates
            positive_coordinates.add(coordinate)
            cases.append({"name": f"selected_pair_{pair_index:03d}_branch_{branch}",
                          "law": "uniform_distinct_support_pair_unique_seed_two_quadratic_roots",
                          "coordinate": coordinate, "rotation": rotation,
                          "expected_pair": [a, b], "source_seed": seedmask,
                          "unrotated_coordinate": unrotated})
    negatives = set()
    while len(negatives) < protocol["trace_zero_controls"]:
        value = rng.getrandbits(N)
        coordinate = square(value) ^ value
        if coordinate and coordinate not in positive_coordinates and coordinate not in negatives:
            negatives.add(coordinate)
    for index, coordinate in enumerate(sorted(negatives)):
        cases.append({"name": f"trace_zero_control_{index:03d}",
                      "law": "uniform_v_square_plus_v_distinct",
                      "coordinate": coordinate, "rotation": ROTATIONS[index % len(ROTATIONS)],
                      "expected_pair": None})
    panel = {"status": "frozen", "curve_id": archived["curve_id"],
             "prepare_protocol_sha256": digest(HERE / "prepare_protocol.json"),
             "source_support_sha256": digest(SOURCE), "cases": cases}
    (HERE / "panel.json").write_text(json.dumps(panel, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "positive_pairs": len(selected_seeds),
                      "trace_zero_controls": len(negatives),
                      "panel_sha256": digest(HERE / "panel.json")}))


if __name__ == "__main__":
    main()
