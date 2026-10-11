"""Construct and independently group-replay a 16-source N41 circuit witness."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "n41_transport_cubic_s8_20261011" / "fixture.json"
RUNTIME = HERE / "sage_runtime_info.json"
ROTATIONS = (0, 5, 10, 15, 20, 25, 30, 35)
SEEDS = (32, 33, 34, 35)
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    prior = json.loads(UPSTREAM.read_text())
    columns = {int(k): int(v) for k, v in prior["mask_columns"].items()}
    options = {seed: [(a, a ^ seed) for a in sorted(columns)
                      if a < (a ^ seed) and (a ^ seed) in columns
                      and columns[a] != columns[a ^ seed]] for seed in SEEDS}

    def choose(slot, used, selected):
        if slot == 8:
            return selected
        for a, b in options[SEEDS[slot % 4]]:
            if columns[a] not in used and columns[b] not in used:
                found = choose(slot+1, used | {columns[a], columns[b]},
                               selected + [a, b])
                if found:
                    return found
        return None

    masks = choose(0, set(), [])
    assert masks is not None and len(masks) == 16
    assert len({columns[mask] for mask in masks}) == 16
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, "t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def enc(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def coords(point):
        assert point != zero
        return [enc(point[0]), enc(point[1])]

    def pi(point):
        return curve(point[0]**2, point[1]**2)

    def halftrace(value):
        original = value
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        assert result**2+result == original
        return result

    def branch(a, b, c):
        value = a*b*c + halftrace((a+b+c)**2)
        assert value in (field.zero(), field.one())
        return int(value)

    points = []
    for index, mask in enumerate(masks):
        w = field(sum((t**(bit+1) for bit in range(6)
                       if mask >> bit & 1), ring.zero()))
        w = w**(2**ROTATIONS[index//2])
        u = halftrace(w)
        source = curve.lift_x(1+1/u, all=True)[0]
        transported = source + pi(source)
        assert transported != zero and transported[0] == 1/w
        assert R*(4*transported) == zero
        points.append(transported)
    pair = [points[2*i] + points[2*i+1] for i in range(8)]
    middle = [pair[2*i] + pair[2*i+1] for i in range(4)]
    upper = [middle[2*i] + middle[2*i+1] for i in range(2)]
    raw = upper[0] + upper[1]
    assert raw == sum(points, zero)
    assert all(point != zero and point[0] != 0 for point in
               [*points, *pair, *middle, *upper, raw])
    target = 4*raw
    assert R*target == zero
    reciprocal = lambda point: 1/point[0]
    branch_bits = []
    for i in range(8):
        branch_bits.append(branch(reciprocal(points[2*i]),
                                  reciprocal(points[2*i+1]), reciprocal(pair[i])))
    for i in range(4):
        branch_bits.append(branch(reciprocal(pair[2*i]),
                                  reciprocal(pair[2*i+1]), reciprocal(middle[i])))
    for i in range(2):
        branch_bits.append(branch(reciprocal(middle[2*i]),
                                  reciprocal(middle[2*i+1]), reciprocal(upper[i])))
    branch_bits.append(branch(reciprocal(upper[0]), reciprocal(upper[1]),
                              reciprocal(raw)))
    record = {"status": "PASS_N41_AFFINE_FOUR_SEED_M16_GROUP_CONTROL",
              "candidate_id": None, "masks": masks,
              "source_columns": [columns[mask] for mask in masks],
              "source_points": [coords(point) for point in points],
              "pair_points": [coords(point) for point in pair],
              "middle_points": [coords(point) for point in middle],
              "upper_points": [coords(point) for point in upper],
              "raw_sum": coords(raw), "projected_target": coords(target),
              "raw_reciprocal": enc(reciprocal(raw)),
              "pair_reciprocals": [enc(reciprocal(point)) for point in pair],
              "middle_reciprocals": [enc(reciprocal(point)) for point in middle],
              "upper_reciprocals": [enc(reciprocal(point)) for point in upper],
              "branch_bits": branch_bits,
              "source_sha256": {"prepare_sage.py": sha(__file__),
                                "upstream_fixture": sha(UPSTREAM),
                                "sage_runtime_info": sha(RUNTIME)}}
    with (HERE / "control_fixture.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": record["status"],
                      "projected_target": record["projected_target"]}))


if __name__ == "__main__":
    main()
