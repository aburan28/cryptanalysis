#!/usr/bin/env sage -python
"""Independent Sage group replay and M4RI rank of every same-seed output bin."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix


HERE = Path(__file__).resolve().parent
BASE = HERE.parent
INPUT = BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
OUTPUTS = HERE / "quad_outputs.tsv"
RANK = HERE / "rank_result.json"
RUNTIME = HERE / "sage_runtime_info.json"
FREEZE = HERE / "sage_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


freeze = json.loads(FREEZE.read_text())
assert freeze["status"] == "FROZEN_BEFORE_INDEPENDENT_SAGE_AUDIT"
assert freeze["sha256"] == {name: sha(path) for name, path in {
    "audit_sage.py": Path(__file__), "input": INPUT, "quad_outputs.tsv": OUTPUTS,
    "rank_result.json": RANK, "sage_runtime_info.json": RUNTIME}.items()}
assert not (HERE / "sage_audit.json").exists()

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
F = GF(2**41, "t", modulus=t**41+t**3+1)
E = EllipticCurve(F, [1, 0, 0, 0, 1])


def decode(value):
    return F(ring([(int(value) >> i) & 1 for i in range(41)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


lines = INPUT.read_text().splitlines()
qx, qy, order, blocks = map(int, lines[0].split())
assert (qx, qy, order, blocks) == (1458168294740, 1672312028033, 549756390943, 6)
atoms = []
cursor = 1
for block in range(6):
    rotation, size = map(int, lines[cursor].split())
    cursor += 1
    assert (rotation, size) == (block*5, 64)
    rows = []
    for _ in range(size):
        x, y, mask, sign, column = map(int, lines[cursor].split())
        cursor += 1
        rows.append((E(decode(x), decode(y)), mask, sign, column))
    atoms.append(rows)
assert cursor == len(lines)

pairs = []
for block in (2, 3):
    domain = []
    for i, a in enumerate(atoms[block]):
        for j, b in enumerate(atoms[block]):
            if a[1] >= b[1] or a[3] == b[3]:
                continue
            domain.append((a[0]+b[0], a[1]^b[1], (1 << a[3]) | (1 << b[3])))
    pairs.append(domain)
assert [len(domain) for domain in pairs] == [1956, 1956]

xs = defaultdict(set)
sample = []
rows = 0
with OUTPUTS.open(newline="") as source:
    reader = csv.DictReader(source, delimiter="\t")
    for row in reader:
        seed, x, y = (int(row[key]) for key in ("seed", "x", "y"))
        i, j, columns = (int(row[key]) for key in ("first_pair", "second_pair", "columns"))
        xs[seed].add(x)
        if rows % 521 == 0:
            sample.append((seed, x, y, i, j, columns))
        rows += 1
assert rows == 51840 and len(sample) >= 99 and len(xs) == 63
for seed, x, y, i, j, columns in sample:
    left, right = pairs[0][i], pairs[1][j]
    assert left[1] == right[1] == seed and left[2] & right[2] == 0
    point = left[0] + right[0]
    assert point != E(0) and (encode(point[0]), encode(point[1])) == (x, y)
    assert left[2] | right[2] == columns


def feature_bits(x):
    bits = [1]
    active = [(x >> (i+1)) & 1 for i in range(40)]
    bits.extend(active)
    bits.extend(active[i] & active[j] for i in range(40) for j in range(i+1, 40))
    assert len(bits) == 821
    return bits


rank_result = json.loads(RANK.read_text())
checked = []
for item in rank_result["bins"]:
    seed = item["seed"]
    values = sorted(xs[seed])
    sage_rank = matrix(GF(2), [feature_bits(x) for x in values], sparse=False).rank()
    assert len(values) == item["distinct_x"] and sage_rank == item["quadratic_rank"]
    checked.append({"seed": seed, "distinct_x": len(values), "sage_rank": sage_rank})

audit = {"status": "PASS_INDEPENDENT_SAGE_QUAD_GROUP_AND_ALL_BIN_RANK",
         "sampled_witnesses": len(sample), "all_bin_count": len(checked),
         "all_bin_distinct_x": sum(item["distinct_x"] for item in checked),
         "extra_rank_defect_bins": sum(item["sage_rank"] != min(item["distinct_x"], 821) for item in checked),
         "bins": checked, "protocol_sha256": sha(FREEZE)}
with (HERE / "sage_audit.json").open("x") as target:
    json.dump(audit, target, sort_keys=True, indent=2)
    target.write("\n")
print({k: v for k, v in audit.items() if k != "bins"})
