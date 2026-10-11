"""Independently rebuild transported W6 pair domains and nine joins."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert runtime["status"] == "verified"
protocol = json.loads((HERE / "protocol_v2.json").read_text())
manifest = json.loads((HERE / "input_v2_manifest.json").read_text())
receipt = json.loads((HERE / "receipt_v2.json").read_text())
assert receipt["status"] == "COMPLETE_EXACT_TRANSPORT_PAIR_PANEL"
assert manifest["status"] == "PASS_SAGE_RAW_SOURCE_PREIMAGES"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for key, path in {
    "source": HERE / "exact_join.cpp",
    "binary": HERE / "exact_join_native",
    "helper": ROOT.parent / "koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "input": HERE / "input_v2.txt",
    "input_manifest": HERE / "input_v2_manifest.json",
    "producer": HERE / "make_input_sage.py",
    "sage_runtime": HERE / "sage_runtime_info.json",
    "screen": ROOT / "n131_w18_four_pairs/screen.json",
    "fixture": ROOT / "n41_two_pair_relaxation_20261011/targets.json",
    "relaxed_receipt": ROOT / "n41_direct_relaxed_pair_join_20261011/receipt.json",
    "v1_protocol": HERE / "protocol.json",
    "v1_failure": HERE / "run.stderr",
}.items():
    assert sha(path) == protocol["source_sha256"][key], key

screen = json.loads((ROOT / "n131_w18_four_pairs/screen.json").read_text())["n41"]
fixture = json.loads((ROOT / "n41_two_pair_relaxation_20261011/targets.json").read_text())
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


rows = (HERE / "input_v2.txt").read_text().splitlines()
assert rows[0] == "9"
targets = [(parts[0], (int(parts[1]), int(parts[2])))
           for parts in (row.split() for row in rows[1:10])]
assert [name for name, _ in targets] == [row["label"] for row in receipt["queries"]]
cursor = 10
sources = []
for rotation in (20, 30):
    assert rows[cursor] == f"{rotation} 64"
    cursor += 1
    block = []
    screen_rows = screen["point_rows_by_unique_rotation"][str(rotation)]
    for native_row, screen_row in zip(rows[cursor:cursor+64], screen_rows):
        x, y, column, mask, branch, sign = map(int, native_row.split())
        sx, sy, sc, sm, sb, ss = screen_row
        assert (column, mask, branch, sign) == (sc, sm, sb, ss)
        raw = curve(dec(x), dec(y))
        assert coords(4*raw) == (sx, sy)
        pi = curve(raw[0]**2, raw[1]**2)
        d = raw + pi
        assert d[0] == 1/(dec(mask << 1)**(2**rotation))
        block.append((column, mask, sign, raw, d))
    sources.append(block)
    cursor += 64
assert cursor == len(rows)

pair_maps = []
pair_counts = []
for block in sources:
    pair_map = defaultdict(list)
    excluded = 0
    for i, a in enumerate(block):
        for b in block[i+1:]:
            if a[0] == b[0]:
                excluded += 1
                continue
            pair_sum = a[4] + b[4]
            assert pair_sum != curve(0) and pair_sum[0] != 0
            pair_map[coords(pair_sum)].append((a, b))
    pair_maps.append(pair_map)
    pair_counts.append((sum(map(len, pair_map.values())), len(pair_map), excluded))
assert pair_counts == [(1956, 1956, 60), (1956, 1956, 60)]
assert receipt["exact_pair_witnesses"] == [1956, 1956]
assert receipt["distinct_exact_pair_points"] == [1956, 1956]

checks = []
for (label, encoded), native in zip(targets, receipt["queries"]):
    target = point(encoded)
    hits = 0
    compatible = 0
    first = None
    for left_coords, left_witnesses in pair_maps[0].items():
        needed = coords(target - point(left_coords))
        for a, b in left_witnesses:
            for c, d in pair_maps[1].get(needed, []):
                hits += 1
                if len({a[0], b[0], c[0], d[0]}) == 4:
                    compatible += 1
                    if first is None:
                        first = (left_coords, needed,
                                 [a[1], b[1], c[1], d[1]])
    assert hits == native["group_hits"]
    assert compatible == native["column_compatible_hits"]
    assert (first is not None) == (label == "positive")
    if first:
        assert list(first[0]) == native["left_pair_point"]
        assert list(first[1]) == native["right_pair_point"]
        assert first[2] == fixture["known_positive"]["source_masks"]
        assert point(first[0]) + point(first[1]) == target
    else:
        assert native["status"] == "COMPLETE_EXACT_NO_SUM"
        assert native["pair_probes"] == 1956
    checks.append({"label": label, "group_hits": hits,
                   "column_compatible_hits": compatible})

out = {"status": "PASS_INDEPENDENT_EXACT_TRANSPORT_PAIR_JOIN",
       "protocol_sha256": sha(HERE / "protocol_v2.json"),
       "receipt_sha256": sha(HERE / "receipt_v2.json"),
       "runtime_sha256": sha(HERE / "sage_runtime_info.json"),
       "pair_counts": pair_counts, "checks": checks}
(HERE / "sage_replay_v2.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], "queries", len(checks))
