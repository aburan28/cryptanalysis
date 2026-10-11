"""Independent Sage replay of the complete first-half input law and positive."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
panel = json.loads((HERE / "panel.json").read_text())
exact = json.loads((HERE / "receipt.json").read_text())
s3 = json.loads((HERE / "s3_receipt.json").read_text())
fixture = json.loads((ROOT / "n41_transport_cubic_s8_20261011/fixture.json").read_text())
assert runtime["status"] == "verified"
assert panel["status"] == "FROZEN_FULL_TARGET_DERIVED_N41_FIRSTHALF_FAMILY"
assert exact["status"] == "COMPLETE_EXACT_TRANSPORT_PAIR_PANEL"
assert s3["status"] == "COMPLETE_RECIPROCAL_S3_PANEL"

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])


def dec(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def coords(point):
    return [enc(point[0]), enc(point[1])]


def point(values):
    return curve(dec(values[0]), dec(values[1]))


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


lines = (HERE / "exact_input.txt").read_text().splitlines()
assert int(lines[0]) == 1712
targets = {}
for line in lines[1:1713]:
    label, x, y = line.split()
    assert label not in targets
    targets[label] = point((int(x), int(y)))
assert list(targets) == [q["label"] for q in exact["queries"]]
assert list(targets) == [q["label"] for q in s3["queries"]]

sources = []
cursor = 1713
for rotation in (20, 30):
    assert lines[cursor] == f"{rotation} 64"
    cursor += 1
    rows = []
    for line in lines[cursor:cursor+64]:
        x, y, column, mask, branch, sign = map(int, line.split())
        raw = point((x, y))
        transported = raw + curve(raw[0]**2, raw[1]**2)
        assert branch == 0
        assert 1/transported[0] == dec(mask << 1)**(2**rotation)
        rows.append((raw, transported, column, mask, sign))
    sources.append(rows)
    cursor += 64
assert cursor == len(lines)

U = point(panel["public_raw_preimage"])
B = point(panel["fixed_second_pair_point"])
assert coords(U) == fixture["raw_target_preimages"][0]
assert coords(B) == fixture["pair_points"][1]
assert len(set(fixture["known_columns"])) == 8
assert targets["positive"] == point(fixture["middle_points"][1])
assert len(panel["controls"]) == 1711

source_tokens = list(map(int, (ROOT / "n131_w18_four_pairs/native_join/native_input.txt").read_text().split()))
source_cursor = 4
first_slots = []
for slot in range(2):
    assert source_tokens[source_cursor] == 64
    source_cursor += 1
    rows = []
    for _ in range(64):
        x, y, column, mask, branch, sign = source_tokens[source_cursor:source_cursor+6]
        source_cursor += 6
        w = dec(mask << 1)
        halftrace = field.zero()
        for _ in range(21):
            halftrace += w
            w = w**4
        atom = curve.lift_x(1+1/(halftrace+branch), all=True)[sign]
        assert coords(4*atom) == [x, y]
        transported = atom + curve(atom[0]**2, atom[1]**2)
        rows.append((transported, column, mask))
    first_slots.append(rows)

for i, control in enumerate(panel["controls"]):
    label = f"control_{i}"
    a, b = control["first_pair_ids"]
    first = first_slots[0][a][0] + first_slots[1][b][0]
    assert coords(first) == control["first_pair_point"]
    assert [first_slots[0][a][1], first_slots[1][b][1]] == control["first_pair_columns"]
    assert [first_slots[0][a][2], first_slots[1][b][2]] == control["first_pair_masks"]
    right = U - first - B
    assert coords(right) == control["right_middle_point"]
    assert targets[label] == right
    assert (1/right[0]).trace() == 0
    assert exact["queries"][i+1]["status"] == "COMPLETE_EXACT_NO_SUM"
    assert s3["queries"][i+1]["status"] == "COMPLETE_EXACT_NO_SUM"
    assert exact["queries"][i+1]["group_hits"] == s3["queries"][i+1]["group_hits"] == 0

witnesses = exact["queries"][0]["source_witnesses"]
assert len(witnesses) == 4
assert witnesses == s3["queries"][0]["source_witnesses"]
assert [w["column"] for w in witnesses] == fixture["known_columns"][4:]
assert [w["mask"] for w in witnesses] == fixture["known_masks"][4:]
positive_sum = curve(0)
for witness in witnesses:
    raw = point(witness["raw"])
    transported = raw + curve(raw[0]**2, raw[1]**2)
    assert coords(transported) == witness["transported"]
    positive_sum += transported
assert positive_sum == targets["positive"]
assert exact["queries"][0]["group_hits"] == s3["queries"][0]["group_hits"] == 1

out = {"status": "PASS_SAGE_FULL_FIRSTHALF_INPUT_AND_POSITIVE_REPLAY",
       "controls": len(panel["controls"]), "source_rows": [len(v) for v in sources],
       "positive_four_columns": [w["column"] for w in witnesses],
       "sha256": {name: sha(name) for name in
                  ("panel.json", "exact_input.txt", "receipt.json", "s3_receipt.json",
                   "sage_runtime_info.json")}}
(HERE / "sage_replay.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], out["controls"])
