"""Exact degree-two output rank of valid N41 cross-block source pairs."""

import csv
import hashlib
import json
import random
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w6_offset_quad_rank_20261010"
FILES = (SOURCE / "quad_outputs.tsv", SOURCE / "quad_outputs_b.tsv")
DIM = 1 + 80 + 40 * 39 + 40 * 40  # 1 + 80 + C(80, 2) = 3241
SEED = 20261011
CAP = 200000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2)
        stream.write("\n")


def load(path):
    bins = defaultdict(list)
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        assert reader.fieldnames == ["seed", "x", "y", "first_pair", "second_pair", "columns"]
        for index, raw in enumerate(reader):
            seed, x, columns = (int(raw[key]) for key in ("seed", "x", "columns"))
            assert 1 <= seed < 64 and 0 <= x < (1 << 41) and x & 1 == 0
            assert columns.bit_count() == 4
            bins[seed].append((index, x, columns))
    assert set(bins) == set(range(1, 64))
    return bins


def feature_row(a, b):
    """Order: 1, A, B, A*A, A*B, B*B; each product lexicographic."""
    active = [i for i in range(40) if (a >> (i + 1)) & 1]
    other = [j for j in range(40) if (b >> (j + 1)) & 1]
    row = 1
    for i in active:
        row |= 1 << (1 + i)
    for j in other:
        row |= 1 << (41 + j)
    pos = 81
    aset, bset = set(active), set(other)
    for i in range(40):
        for j in range(i + 1, 40):
            if i in aset and j in aset:
                row |= 1 << pos
            pos += 1
    for i in range(40):
        for j in range(40):
            if i in aset and j in bset:
                row |= 1 << pos
            pos += 1
    for i in range(40):
        for j in range(i + 1, 40):
            if i in bset and j in bset:
                row |= 1 << pos
            pos += 1
    assert pos == DIM
    return row


def main():
    protocol = {
        "status": "FROZEN_BEFORE_RANK",
        "curve": "GF(2)[t]/(t^41+t^3+1), y^2+xy=x^3+1",
        "source_sha256": {path.name: sha(path) for path in FILES},
        "producer_sha256": sha(Path(__file__)),
        "source_law": "exact four-atom outputs from rotations 10,15 and 20,25; eight distinct source columns",
        "offsets": list(range(8)),
        "sampling": "Python Random(20261011), uniform seed A 1..63, uniform offset 0..7, uniform archived row per seed bin; reject seed B=0 and cross-block column collisions",
        "features": "1; A x bits 1..40; B x bits 1..40; A_i A_j (i<j); A_i B_j; B_i B_j (i<j), lexicographic within each family",
        "feature_count": DIM,
        "attempt_cap": CAP,
        "workers": 1,
    }
    write_once(HERE / "protocol.json", protocol)
    start = time.perf_counter()
    left, right = (load(path) for path in FILES)
    rng = random.Random(SEED)
    pivots = {}
    witnesses = []
    rejected_seed = rejected_columns = eligible = 0
    for attempt in range(1, CAP + 1):
        sa = rng.randrange(1, 64)
        sb = sa ^ rng.randrange(8)
        if sb == 0:
            rejected_seed += 1
            continue
        ia, a, ca = rng.choice(left[sa])
        ib, b, cb = rng.choice(right[sb])
        if ca & cb:
            rejected_columns += 1
            continue
        eligible += 1
        row = feature_row(a, b)
        while row:
            pivot = row.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = row
                witnesses.append([ia, ib, sa, sb, a, b, ca, cb])
                break
            row ^= pivots[pivot]
        if len(pivots) == DIM:
            break
    result = {
        "status": "FULL_QUADRATIC_RANK" if len(pivots) == DIM else "CAPPED_RANK",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "attempts": attempt,
        "eligible": eligible,
        "reject_zero_seed": rejected_seed,
        "reject_columns": rejected_columns,
        "rank": len(pivots),
        "feature_count": DIM,
        "pivotal_witnesses": witnesses,
        "elapsed_seconds": time.perf_counter() - start,
    }
    write_once(HERE / "result.json", result)
    print(f"rank={len(pivots)}/{DIM} attempts={attempt} eligible={eligible}")


if __name__ == "__main__":
    main()
