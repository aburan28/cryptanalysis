"""Replay every relaxed hit and its exact transported-domain classification."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
panel = json.loads((HERE / "panel.json").read_text())
protocol = json.loads((HERE / "protocol.json").read_text())
relaxed = json.loads((HERE / "relaxed_receipt.json").read_text())
exact = json.loads((HERE / "exact_receipt.json").read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
fixture = json.loads((ROOT / "n41_transport_cubic_s8_20261011/fixture.json").read_text())
screen = json.loads((ROOT / "n131_w18_four_pairs/screen.json").read_text())["n41"]
assert runtime["status"] == "verified"
assert panel["selected_count"] == 512
assert len(relaxed["queries"]) == len(exact["queries"]) == 513


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for name, path in {
    "panel": HERE / "panel.json",
    "targets": HERE / "targets.txt",
    "exact_input": HERE / "exact_input.txt",
    "producer": HERE / "make_panel_sage.py",
    "sage_runtime": HERE / "sage_runtime_info.json",
    "relaxed_source": HERE / "relaxed_panel.cpp",
    "relaxed_binary": HERE / "relaxed_panel_native",
    "exact_source": HERE / "exact_panel.cpp",
    "exact_binary": HERE / "exact_panel_native",
    "helper": HERE.parent.parent / "koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "source_input": ROOT / "n131_w18_four_pairs/native_join/native_input.txt",
    "source_fixture": ROOT / "n41_transport_cubic_s8_20261011/fixture.json",
    "raw_input": ROOT / "n41_exact_transport_pair_join_20261011/input_v2.txt",
    "prior_relaxed": ROOT / "n41_direct_relaxed_pair_join_20261011/receipt.json",
    "prior_exact": ROOT / "n41_exact_transport_pair_join_20261011/receipt_v2.json",
}.items():
    assert sha(path) == protocol["sha256"][name], name

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, "t", modulus=t**41+t**3+1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])


def dec(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def coords(point):
    return (enc(point[0]), enc(point[1]))


def point(pair):
    return curve(dec(pair[0]), dec(pair[1]))


def halftrace(value):
    out = field.zero()
    for _ in range(21):
        out += value
        value = value**4
    return out


U = point(panel["public_raw_preimage"])
B = point(panel["fixed_second_pair_point"])
assert coords(U) == tuple(fixture["raw_target_preimages"][0])
targets = [(name, (int(x), int(y)))
           for name, x, y in (line.split() for line in
                              (HERE / "targets.txt").read_text().splitlines()[1:])]
assert targets[0][0] == "positive"
assert len(targets) == 513
for i, row in enumerate(panel["controls"]):
    name, encoded = targets[i+1]
    assert name == f"control_{i}" and encoded == tuple(row["right_middle_point"])
    A = point(row["first_pair_point"])
    V = point(encoded)
    assert A+B+V == U
    assert (1/V[0]).trace() == 0
    assert len(set(row["first_pair_columns"] + fixture["known_columns"][2:4])) == 4

lines = (HERE / "exact_input.txt").read_text().splitlines()
assert lines[:514] == (HERE / "targets.txt").read_text().splitlines()
cursor = 514
sources = []
for rotation in (20, 30):
    assert lines[cursor] == f"{rotation} 64"
    cursor += 1
    block = []
    screen_rows = screen["point_rows_by_unique_rotation"][str(rotation)]
    for line, original in zip(lines[cursor:cursor+64], screen_rows):
        x, y, column, mask, branch, sign = map(int, line.split())
        assert (column, mask, branch, sign) == tuple(original[2:])
        raw = curve(dec(x), dec(y))
        assert coords(4*raw) == tuple(original[:2])
        d = raw + curve(raw[0]**2, raw[1]**2)
        assert d[0] == 1/(dec(mask << 1)**(2**rotation))
        block.append((column, mask, d))
    sources.append(block)
    cursor += 64
assert cursor == len(lines)

pair_maps = []
for block in sources:
    pair_map = defaultdict(list)
    for i, a in enumerate(block):
        for b in block[i+1:]:
            if a[0] == b[0]:
                continue
            pair_map[coords(a[2]+b[2])].append((a, b))
    assert sum(map(len, pair_map.values())) == len(pair_map) == 1956
    pair_maps.append(pair_map)


def replay_relaxed(pair_coords, witness, rotation):
    rotated = point(pair_coords)
    original = curve(rotated[0]**(2**(41-rotation)),
                     rotated[1]**(2**(41-rotation)))
    z = dec(witness["reciprocal_z"])
    s = dec(witness["seed_sum"] << 1)
    p = dec(witness["product_mask"] << 2)
    assert z != 0 and z.trace() == 0
    assert original[0] == 1/z
    assert p*z + halftrace((s+z)**2) + witness["branch"] == 0


relaxed_hits = []
exact_hits = []
checks = []
for (name, encoded), rq, eq in zip(targets, relaxed["queries"], exact["queries"]):
    assert rq["label"] == eq["label"] == name
    assert tuple(rq["target"]) == tuple(eq["target"]) == encoded
    assert eq["pair_probes"] == 1956
    if eq["status"] == "EXACT_FOUR_ATOM_HIT":
        exact_hits.append(name)
    else:
        assert eq["status"] == "COMPLETE_EXACT_NO_SUM"
    if rq["status"] == "RELAXED_SUM_HIT":
        relaxed_hits.append(name)
        target = point(encoded)
        left, right = point(rq["left_point"]), point(rq["right_point"])
        assert left+right == target
        replay_relaxed(rq["left_point"], rq["left_witness"], 20)
        replay_relaxed(rq["right_point"], rq["right_witness"], 30)
        group_hits = compatible = 0
        for left_coords, left_witnesses in pair_maps[0].items():
            needed = coords(target-point(left_coords))
            for a, b in left_witnesses:
                for c, d in pair_maps[1].get(needed, []):
                    group_hits += 1
                    if len({a[0], b[0], c[0], d[0]}) == 4:
                        compatible += 1
        assert group_hits == eq["group_hits"]
        assert compatible == eq["column_compatible_hits"]
        checks.append({"label": name, "relaxed_group_sum": True,
                       "exact_group_hits": group_hits,
                       "exact_column_compatible_hits": compatible})
    else:
        assert rq["status"] == "COMPLETE_RELAXED_NO_SUM"
        assert rq["probes"] == 128656

assert exact_hits == ["positive"]
assert len(relaxed_hits) == 10 and len(checks) == 10
assert len([row for row in checks if row["exact_group_hits"] == 0]) == 9
out = {"status": "PASS_SAGE_REPLAY_ALL_RELAXED_HITS",
       "panel_sha256": sha(HERE / "panel.json"),
       "protocol_sha256": sha(HERE / "protocol.json"),
       "relaxed_receipt_sha256": sha(HERE / "relaxed_receipt.json"),
       "exact_receipt_sha256": sha(HERE / "exact_receipt.json"),
       "target_derivations_checked": 512,
       "relaxed_hit_labels": relaxed_hits,
       "exact_hit_labels": exact_hits,
       "checks": checks}
(HERE / "sage_replay.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], "relaxed", len(relaxed_hits), "exact", len(exact_hits))
