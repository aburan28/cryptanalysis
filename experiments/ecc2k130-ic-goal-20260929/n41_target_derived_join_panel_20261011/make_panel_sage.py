"""Seeded trace-valid right-middle controls from one frozen public preimage."""

import hashlib
import json
import random
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNTIME = HERE / "sage_runtime_info.json"
assert json.loads(RUNTIME.read_text())["status"] == "verified"
SOURCE = ROOT / "n131_w18_four_pairs/native_join/native_input.txt"
FIXTURE = ROOT / "n41_transport_cubic_s8_20261011/fixture.json"
RAW_INPUT = ROOT / "n41_exact_transport_pair_join_20261011/input_v2.txt"
f = json.loads(FIXTURE.read_text())
ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, "t", modulus=t**41+t**3+1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
zero = curve(0)


def dec(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def coords(point):
    return [enc(point[0]), enc(point[1])]


def halftrace(value):
    out = field.zero()
    for _ in range(21):
        out += value
        value = value**4
    return out


tokens = list(map(int, SOURCE.read_text().split()))
cursor = 4
slots = []
for slot in range(8):
    assert tokens[cursor] == 64
    cursor += 1
    rows = []
    rotation = (0, 0, 10, 10, 20, 20, 30, 30)[slot]
    for _ in range(64):
        x, y, column, mask, branch, sign = tokens[cursor:cursor+6]
        cursor += 6
        w = dec(mask << 1)**(2**rotation)
        u = halftrace(w) + branch
        point = curve.lift_x(1+1/u, all=True)[sign]
        assert coords(4*point) == [x, y]
        transported = point + curve(point[0]**2, point[1]**2)
        assert transported[0] == 1/w
        rows.append((transported, column, mask, sign))
    slots.append(rows)
assert cursor == len(tokens)

U = curve(dec(f["raw_target_preimages"][0][0]),
          dec(f["raw_target_preimages"][0][1]))
B = curve(dec(f["pair_points"][1][0]), dec(f["pair_points"][1][1]))
assert coords(U) == f["raw_target_preimages"][0]
assert coords(B) == f["pair_points"][1]
excluded_columns = set(f["known_columns"][2:4])
positive_right = f["middle_points"][1]
valid = []
seen = set()
for i, a in enumerate(slots[0]):
    for j in range(i+1, 64):
        b = slots[1][j]
        if a[1] == b[1] or a[1] in excluded_columns or b[1] in excluded_columns:
            continue
        A = a[0] + b[0]
        V = U - A - B
        if V == zero or V[0] == 0:
            continue
        z = 1/V[0]
        if z.trace() != 0:
            continue
        encoded = tuple(coords(V))
        if list(encoded) == positive_right or encoded in seen:
            continue
        seen.add(encoded)
        assert A+B+V == U
        valid.append({"first_pair_ids": [i, j],
                      "first_pair_columns": [a[1], b[1]],
                      "first_pair_masks": [a[2], b[2]],
                      "first_pair_point": coords(A),
                      "right_middle_point": list(encoded),
                      "target_z": enc(z)})

rng = random.Random(20261011)
rng.shuffle(valid)
selected = valid[:min(512, len(valid))]
assert len(selected) >= 256
targets = [("positive", *positive_right)]
targets += [(f"control_{i}", *item["right_middle_point"])
            for i, item in enumerate(selected)]
lines = [str(len(targets))]
lines += [f"{label} {x} {y}" for label, x, y in targets]
targets_path = HERE / "targets.txt"
targets_path.write_text("\n".join(lines) + "\n")
raw_lines = RAW_INPUT.read_text().splitlines()
assert raw_lines[0] == "9" and raw_lines[10] == "20 64"
exact_input = HERE / "exact_input.txt"
exact_input.write_text("\n".join([*lines, *raw_lines[10:]]) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


out = {"status": "FROZEN_SEEDED_TARGET_DERIVED_N41_PANEL",
       "seed": 20261011, "selection": "shuffle valid distinct trace-zero V=U-A-B then take first min(512,count)",
       "public_raw_preimage": coords(U), "fixed_second_pair_point": coords(B),
       "positive_right_middle": positive_right,
       "eligible_count": len(valid), "selected_count": len(selected),
       "controls": selected,
       "sha256": {"targets": sha(targets_path),
                  "exact_input": sha(exact_input),
                  "producer": sha(__file__), "runtime": sha(RUNTIME),
                  "source_input": sha(SOURCE), "fixture": sha(FIXTURE),
                  "raw_input": sha(RAW_INPUT)}}
(HERE / "panel.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], "eligible", len(valid), "selected", len(selected))
