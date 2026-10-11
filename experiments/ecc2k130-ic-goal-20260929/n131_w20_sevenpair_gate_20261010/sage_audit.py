#!/usr/bin/env sage -python
"""Independently replay W20 masks, fixed-seed pairs, and a seven-pair chain."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
R = 680564733841876926932320129493409985129
ROTATIONS = [0, 18, 36, 54, 72, 90, 108]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "sage_audit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "table": HERE / "support_w20.tsv",
             "count": HERE / "count_result_v2.json",
             "bdd": HERE / "bdd_result.json",
             "export": HERE / "export_receipt.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    count = json.loads(paths["count"].read_text())
    seed = count["selected_seed_mask"]
    assert seed == json.loads(paths["bdd"].read_text())["fixed_seed_mask"]
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def coordinate(mask):
        return sum((field(t**(bit+1)) for bit in range(20) if mask >> bit & 1),
                   field.zero())

    def half_trace(value):
        acc, term = field.zero(), value
        for _ in range(66):
            acc += term
            term = term**4
        assert acc**2 + acc == value
        return acc

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def encode_point(point):
        return [encode(point[0]), encode(point[1])]

    def reciprocal(point):
        if point == curve(0) or point[0] == 1:
            return None
        return 1/(point[0]+1)

    def link(u, v, w):
        product = u*v*w
        first = u+v+w
        second = u*v+u*w+v*w
        return (product+first)**2 + product*(second+first+1)

    source = {}
    rows = []
    for line in paths["table"].read_text().splitlines():
        mask, column, shift = map(int, line.split())
        assert mask not in source
        source[mask] = (column, shift)
        rows.append(mask)
    assert len(rows) == 524493
    sample = rows[:8] + rows[len(rows)//2:len(rows)//2+8] + rows[-8:]
    cache = {}

    def point_options(mask):
        if mask not in cache:
            w = coordinate(mask)
            assert w.trace() == 0 and (1/w).trace() == 0
            u = half_trace(w)
            assert u != 0
            x = 1 + 1/u
            options = sorted(curve.lift_x(x, all=True),
                             key=lambda point: encode(point[1]))
            assert len(options) == 2
            assert all(R*(4*point) == curve(0) for point in options)
            cache[mask] = options
        return cache[mask]

    for mask in sample:
        column, shift = source[mask]
        assert coordinate(column)**(1 << shift) == coordinate(mask)
        point_options(mask)

    edges = [(mask, mask ^ seed) for mask, (column, shift) in source.items()
             if mask < (mask ^ seed) and mask ^ seed in source and
             column != source[mask ^ seed][0]]
    assert len(edges) == count["selected_valid_unordered_pairs_per_slot"]
    seed_u = half_trace(coordinate(seed))
    selected = []
    raw_pairs = []
    occupied = set()
    pair_controls = 0
    for slot, rotation in enumerate(ROTATIONS):
        for step in range(len(edges)):
            a, b = edges[(slot*8191+step) % len(edges)]
            pair_columns = {source[a][0], source[b][0]}
            if len(pair_columns) != 2 or pair_columns & occupied:
                continue
            left_options, right_options = point_options(a), point_options(b)
            product = coordinate(a)*coordinate(b)
            for left in left_options:
                for right in right_options:
                    zz = reciprocal(left+right)
                    if zz is None:
                        continue
                    assert zz**2 + seed_u**2 == (zz**2+zz)*product
                    pair_controls += 1
            raw = left_options[slot & 1] + right_options[(slot >> 1) & 1]
            zz = reciprocal(raw)
            if zz is None:
                continue
            selected.append({"slot": slot, "rotation": rotation,
                             "masks": [a, b],
                             "folded_columns": [source[a][0], source[b][0]],
                             "unrotated_pair_output_z": encode(zz),
                             "product_p": encode(product)})
            occupied.update(pair_columns)
            raw_pairs.append(raw)
            break
        else:
            raise AssertionError("no distinct-column source pair for slot")
    assert len(selected) == 7 and len(occupied) == 14
    assert pair_controls == 28

    rotated = [curve(raw[0]**(1 << shift), raw[1]**(1 << shift))
               for raw, shift in zip(raw_pairs, ROTATIONS)]
    running = rotated[0]
    intermediate_z = []
    for index, point in enumerate(rotated[1:], 1):
        next_point = running + point
        ua, ub, uc = reciprocal(running), reciprocal(point), reciprocal(next_point)
        assert ua is not None and ub is not None and uc is not None
        assert link(ua, ub, uc) == 0
        running = next_point
        if index < 6:
            intermediate_z.append(encode(uc))
    assert len(intermediate_z) == 5
    projected_target = 4*running
    assert R*projected_target == curve(0)
    result = {"status": "PASS_SAGE_W20_SEVEN_PAIR_GEOMETRY_AND_CHAIN",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "fixed_seed_mask": seed,
              "sampled_mask_shift_and_lift_checks": len(sample),
              "pair_equation_group_controls": pair_controls,
              "s3_links_verified": 6,
              "selected": selected,
              "intermediate_z": intermediate_z,
              "constructed_raw_target": encode_point(running),
              "constructed_raw_target_z": encode(reciprocal(running)),
              "constructed_projected_target": encode_point(projected_target),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "sage_audit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "mask_checks": len(sample), "pair_controls": pair_controls,
                      "links": result["s3_links_verified"]}))


if __name__ == "__main__":
    main()
