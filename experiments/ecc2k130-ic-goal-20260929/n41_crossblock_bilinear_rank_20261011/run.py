"""Rank bilinear output features for exact N41 cross-block seed-offset witnesses."""

import csv
import hashlib
import json
import random
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w6_offset_quad_rank_20261010"
FILES = [SOURCE / "quad_outputs.tsv", SOURCE / "quad_outputs_b.tsv"]
FEATURES = 1681  # constant, 40 bits from each output, 40*40 cross products
SEED = 20261011


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def load(path):
    bins = defaultdict(list)
    with path.open(newline="") as stream:
        rows = csv.DictReader(stream, delimiter="\t")
        assert rows.fieldnames == ["seed", "x", "y", "first_pair", "second_pair", "columns"]
        for index, row in enumerate(rows):
            seed, x, columns = (int(row[k]) for k in ("seed", "x", "columns"))
            assert 1 <= seed < 64 and 0 <= x < (1 << 41) and x & 1 == 0
            assert columns.bit_count() == 4
            bins[seed].append((index, x, columns))
    assert set(bins) == set(range(1, 64))
    return bins


def feature_row(a, b):
    aa = [i for i in range(40) if (a >> (i + 1)) & 1]
    bb = [i for i in range(40) if (b >> (i + 1)) & 1]
    row = 1
    for i in aa:
        row |= 1 << (1 + i)
    for j in bb:
        row |= 1 << (41 + j)
    for i in aa:
        for j in bb:
            row |= 1 << (81 + 40 * i + j)
    return row


def main():
    protocol = {
        "status": "FROZEN_BEFORE_RANK",
        "curve": "GF(2)[t]/(t^41+t^3+1), y^2+xy=x^3+1",
        "source_sha256": {p.name: digest(p) for p in FILES},
        "producer_sha256": digest(Path(__file__)),
        "source_law": "exact four-atom outputs from rotations 10,15 and 20,25; distinct columns within and across blocks",
        "offsets": list(range(8)),
        "sampling": "Python Random(20261011), uniform seed A 1..63, uniform offset 0..7, uniform archived signed row in each bin; reject seed B=0 and cross-block column collisions",
        "features": "1; A x bits 1..40; B x bits 1..40; A_i B_j ordered i then j",
        "feature_count": FEATURES,
        "attempt_cap": 200000,
        "workers": 1,
    }
    write_new(HERE / "protocol_v2.json", protocol)
    start = time.perf_counter()
    bins_a, bins_b = (load(p) for p in FILES)
    rng = random.Random(SEED)
    pivots = {}
    witnesses = []
    reject_zero_seed = reject_columns = eligible = 0
    for attempt in range(1, protocol["attempt_cap"] + 1):
        sa = rng.randrange(1, 64)
        sb = sa ^ rng.randrange(8)
        if sb == 0:
            reject_zero_seed += 1
            continue
        ia, a, ca = rng.choice(bins_a[sa])
        ib, b, cb = rng.choice(bins_b[sb])
        if ca & cb:
            reject_columns += 1
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
        if len(pivots) == FEATURES:
            break
    write_new(HERE / "result.json", {
        "status": "FULL_BILINEAR_RANK" if len(pivots) == FEATURES else "CAPPED_RANK",
        "protocol_sha256": digest(HERE / "protocol_v2.json"),
        "attempts": attempt,
        "eligible": eligible,
        "reject_zero_seed": reject_zero_seed,
        "reject_columns": reject_columns,
        "rank": len(pivots),
        "feature_count": FEATURES,
        "pivotal_witnesses": witnesses,
        "elapsed_seconds": time.perf_counter() - start,
    })
    print(f"rank={len(pivots)}/{FEATURES} attempts={attempt} eligible={eligible}")


if __name__ == "__main__":
    main()
