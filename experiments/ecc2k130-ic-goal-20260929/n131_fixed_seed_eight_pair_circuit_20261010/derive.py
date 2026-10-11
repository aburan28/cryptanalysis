#!/usr/bin/env sage -python
"""Derive the reciprocal S3 link and replay fixed-seed W18 pair controls."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
R = 680564733841876926932320129493409985129
SEED = 212
ROTATIONS = [0, 16, 32, 48, 64, 80, 96, 112]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "derive_protocol.json").read_text())
    paths = {"script": Path(__file__), "support": HERE / "support_result.json",
             "mask_columns": SOURCE / "support_w18.tsv",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    support = json.loads(paths["support"].read_text())
    assert support["selected"]["seed_mask"] == SEED
    assert support["slot_rotations"] == ROTATIONS

    symbolic = PolynomialRing(GF(2), names=("a", "b", "z"))
    a, b, z = symbolic.gens()
    numerator = z*(a+1)*(b+1) + b*(a+1)*(z+1) + a*(b+1)*(z+1)
    cleared_s3 = numerator**2 + a*b*z*(a+1)*(b+1)*(z+1) + (a*b*z)**2
    t = a*b*z
    s1 = a+b+z
    s2 = a*b+a*z+b*z
    reciprocal_s3 = (t+s1)**2 + t*(s2+s1+1)
    pair_equation = z*z + (a+b)**2 + (z*z+z)*(a*a+a)*(b*b+b)
    assert numerator == t+s1
    assert cleared_s3 == reciprocal_s3 == pair_equation

    base = PolynomialRing(GF(2), "t")
    tt = base.gen()
    field = GF(2**131, name="t", modulus=tt**131+tt**13+tt**2+tt+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def coordinate(mask):
        return sum((field(tt**(bit+1)) for bit in range(18) if mask >> bit & 1),
                   field.zero())

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def encode_point(point):
        return [encode(point[0]), encode(point[1])]

    def half_trace(value):
        output = field.zero()
        current = value
        for _ in range(66):
            output += current
            current = current**4
        assert output**2 + output == value
        return output

    columns = {}
    for line in paths["mask_columns"].read_text().splitlines():
        mask, column = map(int, line.split())
        columns[mask] = column
    edges = [(mask, mask ^ SEED) for mask, column in columns.items()
             if mask < (mask ^ SEED) and mask ^ SEED in columns
             and column != columns[mask ^ SEED]]
    assert len(edges) == support["selected"]["valid_unordered_source_pairs"]
    edges.sort()
    seed_field = coordinate(SEED)
    seed_u = half_trace(seed_field)
    cache = {}

    def point_options(mask):
        if mask not in cache:
            u = half_trace(coordinate(mask))
            assert u != 0
            x = 1 + 1/u
            cache[mask] = sorted(curve.lift_x(x, all=True),
                                 key=lambda point: encode(point[1]))
            assert len(cache[mask]) == 2
        return cache[mask]

    def reciprocal(point):
        if point == curve(0) or point[0] == 1:
            return None
        return 1/(point[0]+1)

    def link(u, v, w):
        product = u*v*w
        first = u+v+w
        second = u*v+u*w+v*w
        return (product+first)**2 + product*(second+first+1)

    selected = []
    occupied = set()
    raw_pairs = []
    pair_equation_controls = 0
    for slot, rotation in enumerate(ROTATIONS):
        for step in range(len(edges)):
            left_mask, right_mask = edges[(slot*4093+step) % len(edges)]
            pair_columns = {columns[left_mask], columns[right_mask]}
            if len(pair_columns) != 2 or pair_columns & occupied:
                continue
            left_options = point_options(left_mask)
            right_options = point_options(right_mask)
            products = coordinate(left_mask) * coordinate(right_mask)
            for left in left_options:
                for right in right_options:
                    raw = left+right
                    zz = reciprocal(raw)
                    if zz is None:
                        continue
                    assert zz**2 + seed_u**2 == (zz**2+zz)*products
                    pair_equation_controls += 1
            raw = left_options[slot & 1] + right_options[(slot >> 1) & 1]
            zz = reciprocal(raw)
            if zz is None:
                continue
            selected.append({"slot": slot, "rotation": rotation,
                             "masks": [left_mask, right_mask],
                             "folded_columns": [columns[left_mask], columns[right_mask]],
                             "unrotated_pair_output_z": encode(zz),
                             "product_p": encode(products)})
            occupied.update(pair_columns)
            raw_pairs.append(raw)
            break
        else:
            raise AssertionError("no source pair for slot")
    assert len(selected) == 8 and len(occupied) == 16
    assert pair_equation_controls == 32

    rotated = []
    for raw, rotation in zip(raw_pairs, ROTATIONS):
        power = 1 << rotation
        rotated.append(curve(raw[0]**power, raw[1]**power))
    running = rotated[0]
    chain_links = 0
    for point in rotated[1:]:
        next_point = running + point
        ua, ub, uc = reciprocal(running), reciprocal(point), reciprocal(next_point)
        assert ua is not None and ub is not None and uc is not None
        assert link(ua, ub, uc) == 0
        running = next_point
        chain_links += 1
    assert chain_links == 7
    target_projected = 4*running
    assert R*target_projected == curve(0)
    for mask in {mask for item in selected for mask in item["masks"]}:
        for point in point_options(mask):
            assert R*(4*point) == curve(0)

    result = {"status": "PASS_SYMBOLIC_RECIPROCAL_S3_AND_N131_FIXED_SEED_CONTROL",
              "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "source_dimension": 18, "seed_mask": SEED,
              "symbolic_s3_terms": len(reciprocal_s3.dict()),
              "symbolic_s3_total_degree": int(reciprocal_s3.total_degree()),
              "pair_equation_controls": pair_equation_controls,
              "chain_links_verified": chain_links,
              "selected": selected,
              "planted_raw_target": encode_point(running),
              "planted_projected_target": encode_point(target_projected),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "derive_protocol.json")}
    with (HERE / "derive_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "pair_controls": pair_equation_controls,
                      "s3_links": chain_links}))


if __name__ == "__main__":
    main()
