#!/usr/bin/env sage -python
"""Construct one twelve-column affine-plane correctness row for the native worker."""

import hashlib
import json
import random
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "n41_coupled_sixpair_full_ic_20261010"
R = 549756390943
OFFSET = 57


def main():
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    lines = (ROOT / "online_atoms.txt").read_text().splitlines()
    assert lines[0].split() == ["0", "0", str(R), "6"]
    source = {}
    position = 1
    for block in range(6):
        rotation, count = map(int, lines[position].split())
        assert (rotation, count) == (5*block, 64)
        position += 1
        source[block] = {}
        for line in lines[position:position + count]:
            x, y, mask, sign, column, coefficient = map(int, line.split())
            source[block][(mask, sign)] = {
                "point": [x, y], "mask": mask, "sign": sign,
                "column": column, "coefficient": coefficient}
        position += count
    assert position == len(lines)
    slots = [0, 1, 2, 2, 4, 4]
    rng = random.Random(202610102123)

    def pair_options(block):
        masks = sorted({mask for mask, _ in source[block]})
        return [(a, b) for a in masks for b in masks if a < b and
                source[block][(a, 0)]["column"] != source[block][(b, 0)]["column"]]

    free = {block: pair_options(block) for block in (0, 1)}
    plane = {}
    for block in (2, 4):
        rational = {mask for mask, _ in source[block]}
        configs = []
        for a, b in pair_options(block):
            u, v = sorted((a ^ OFFSET, b ^ OFFSET))
            if u not in rational or v not in rational:
                continue
            columns = [source[block][(mask, 0)]["column"] for mask in (a, b, u, v)]
            if len(set(columns)) == 4:
                configs.append((a, b, u, v))
        plane[block] = configs
        assert len(configs) * 16 == 3328

    selected = None
    for _ in range(100000):
        a, b = rng.choice(free[0]); c, d = rng.choice(free[1])
        masks_a = rng.choice(plane[2]); masks_b = rng.choice(plane[4])
        masks = (a, b, c, d, *masks_a, *masks_b)
        signs = tuple(rng.randrange(2) for _ in range(12))
        atoms = [source[slots[i // 2]][(masks[i], signs[i])] for i in range(12)]
        if len({item["column"] for item in atoms}) != 12:
            continue
        points = [curve(decode(item["point"][0]), decode(item["point"][1]))
                  for item in atoms]
        target = sum(points, curve(0))
        if target == curve(0):
            continue
        selected = masks, signs, atoms, target
        break
    assert selected is not None
    masks, signs, atoms, target = selected
    logs = [int(line) for line in (ROOT / "online_logs.txt").read_text().splitlines()]
    assert len(logs) == 26
    scalar = sum(item["coefficient"] * logs[item["column"]] for item in atoms) % R
    generator = curve(decode(2056947637384), decode(1635505394702))
    assert scalar * generator == target and R * target == curve(0)
    xy = [encode(target[0]), encode(target[1])]
    fixture = {"status": "PASS_CONSTRUCTED_AFFINE_PLANE_ROW",
               "target": xy, "scalar": scalar, "slot_rotations": [0,5,10,10,20,20],
               "offset_mask": OFFSET, "masks": list(masks), "signs": list(signs),
               "columns": [item["column"] for item in atoms],
               "source_sha256": {"script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                 "atoms": hashlib.sha256((ROOT / "online_atoms.txt").read_bytes()).hexdigest(),
                                 "factor_logs": hashlib.sha256((ROOT / "online_logs.txt").read_bytes()).hexdigest()}}
    public = {"curve_id": "EC1N41Ckb1h023d9a38bbf7",
              "target": xy, "target_count": 1,
              "input_law": "constructed correctness control; witness sidecar excluded from worker"}
    for name, value in (("control_fixture.json", fixture), ("control_public.json", public)):
        with (HERE / name).open("x") as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write("\n")
    print(json.dumps({"status": fixture["status"], "target": xy}))


if __name__ == "__main__":
    main()
