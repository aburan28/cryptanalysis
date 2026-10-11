"""Independently replay the native N41 relaxed-pair panel in Sage."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
receipt = json.loads((HERE / "receipt.json").read_text())
protocol = json.loads((HERE / "protocol.json").read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert runtime["status"] == "verified"
assert receipt["status"] == "COMPLETE_N41_RELAXED_TWO_PAIR_PANEL"
assert len(receipt["queries"]) == 9
for name, file in {
    "source": HERE / "direct_join.cpp",
    "helper": HERE.parent.parent / "koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "binary": HERE / "direct_join_native",
    "targets": HERE / "targets.txt",
    "input_manifest": HERE / "input_manifest.json",
    "producer": HERE / "make_input.py",
}.items():
    assert hashlib.sha256(file.read_bytes()).hexdigest() == protocol["sha256"][name]

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])


def dec(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def point(pair):
    return curve(dec(pair[0]), dec(pair[1]))


def halftrace(value):
    output = field.zero()
    for _ in range(21):
        output += value
        value = value**4
    return output


def replay_witness(pair, witness, rotation):
    rotated = point(pair)
    original = curve(rotated[0]**(2**(41-rotation)),
                     rotated[1]**(2**(41-rotation)))
    z = dec(witness["reciprocal_z"])
    s = dec(witness["seed_sum"] << 1)
    product = dec(witness["product_mask"] << 2)
    branch = field(witness["branch"])
    assert witness["seed_sum"] in range(1, 64)
    assert witness["product_mask"] in range(2048)
    assert branch in (0, 1)
    assert z != 0 and z.trace() == 0
    assert product*z + halftrace((s+z)**2) + branch == 0
    assert original[0] == 1/z
    assert original[1]**2 + original[0]*original[1] == original[0]**3 + 1
    return {"unrotated_point": [enc(original[0]), enc(original[1])],
            "rotation": rotation, "equation_verified": True}


input_rows = (HERE / "targets.txt").read_text().splitlines()[1:]
parsed = [(label, [int(x), int(y)]) for label, x, y in map(str.split, input_rows)]
assert len(parsed) == 9
checks = []
for row, (label, coords) in zip(receipt["queries"], parsed):
    assert row["label"] == label and row["target"] == coords
    target = point(coords)
    if row["status"] == "RELAXED_SUM_HIT":
        left, right = point(row["left_point"]), point(row["right_point"])
        assert left + right == target
        left_check = replay_witness(row["left_point"], row["left_witness"], 20)
        right_check = replay_witness(row["right_point"], row["right_witness"], 30)
        checks.append({"label": label, "group_sum_verified": True,
                       "left": left_check, "right": right_check})
    else:
        assert row["status"] == "COMPLETE_RELAXED_NO_SUM"
        assert row["probes"] == receipt["left_rotated_points"]
        checks.append({"label": label, "exhaustion_probes_verified": True})

assert receipt["rank_histogram"] == {"39": 255, "40": 1269, "41": 524}
assert len([row for row in checks if row.get("group_sum_verified")]) == 1
output = {
    "status": "PASS_INDEPENDENT_SAGE_REPLAY",
    "receipt_sha256": hashlib.sha256((HERE / "receipt.json").read_bytes()).hexdigest(),
    "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
    "runtime_sha256": hashlib.sha256((HERE / "sage_runtime_info.json").read_bytes()).hexdigest(),
    "checks": checks,
}
(HERE / "sage_replay.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
print(output["status"], "checks", len(checks))
