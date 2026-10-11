"""Independent sampler replay and reversed-monomial rank certificate."""

import csv
import hashlib
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w6_offset_quad_rank_20261010"
FILES = (SOURCE / "quad_outputs.tsv", SOURCE / "quad_outputs_b.tsv")
DIM = 1 + 80 + 80 * 79 // 2


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_rows(path):
    rows = []
    bins = defaultdict(list)
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        assert reader.fieldnames == ["seed", "x", "y", "first_pair", "second_pair", "columns"]
        for index, raw in enumerate(reader):
            item = {key: int(value) for key, value in raw.items()}
            assert 1 <= item["seed"] <= 63
            assert 0 <= item["x"] < (1 << 41) and item["x"] & 1 == 0
            assert item["columns"].bit_count() == 4
            rows.append(item)
            bins[item["seed"]].append(index)
    assert set(bins) == set(range(1, 64))
    return rows, bins


def reversed_features(a, b):
    """All square-free degree <= 2 monomials, reverse variable order."""
    values = [((a >> i) & 1) for i in range(1, 41)]
    values += [((b >> i) & 1) for i in range(1, 41)]
    vector = 1
    bit = 1
    for i in range(79, -1, -1):
        vector |= values[i] << bit
        bit += 1
    for i, j in itertools.combinations(range(79, -1, -1), 2):
        vector |= (values[i] & values[j]) << bit
        bit += 1
    assert bit == DIM
    return vector


def main():
    protocol_path, result_path = HERE / "protocol.json", HERE / "result.json"
    protocol, result = (json.loads(path.read_text()) for path in (protocol_path, result_path))
    assert protocol["source_sha256"] == {path.name: sha(path) for path in FILES}
    assert protocol["producer_sha256"] == sha(HERE / "run.py")
    assert result["protocol_sha256"] == sha(protocol_path)
    assert protocol["feature_count"] == result["feature_count"] == DIM
    assert protocol["offsets"] == list(range(8)) and protocol["workers"] == 1
    left, lbin = source_rows(FILES[0])
    right, rbin = source_rows(FILES[1])
    rng = random.Random(20261011)
    pivots = {}
    witnesses = []
    rejected_seed = rejected_columns = eligible = 0
    for attempt in range(1, result["attempts"] + 1):
        sa = rng.randrange(1, 64)
        sb = sa ^ rng.randrange(8)
        if sb == 0:
            rejected_seed += 1
            continue
        ia = rng.choice(lbin[sa])
        ib = rng.choice(rbin[sb])
        la, rb = left[ia], right[ib]
        ca, cb = la["columns"], rb["columns"]
        if ca & cb:
            rejected_columns += 1
            continue
        eligible += 1
        a, b = la["x"], rb["x"]
        vector = reversed_features(a, b)
        while vector:
            pivot = vector & -vector
            if pivot not in pivots:
                pivots[pivot] = vector
                witnesses.append([ia, ib, sa, sb, a, b, ca, cb])
                break
            vector ^= pivots[pivot]
    assert len(pivots) == result["rank"] == len(result["pivotal_witnesses"])
    assert witnesses == result["pivotal_witnesses"]
    assert eligible == result["eligible"]
    assert rejected_seed == result["reject_zero_seed"]
    assert rejected_columns == result["reject_columns"]
    assert eligible + rejected_seed + rejected_columns == result["attempts"]
    assert result["status"] == ("FULL_QUADRATIC_RANK" if len(pivots) == DIM else "CAPPED_RANK")
    assert (len(pivots) == DIM or result["attempts"] == protocol["attempt_cap"])
    receipt = {
        "status": "PASS_N41_CROSSBLOCK_FULL_QUADRATIC_RANK_REPLAY",
        "protocol_sha256": sha(protocol_path),
        "result_sha256": sha(result_path),
        "source_rows": [len(left), len(right)],
        "attempts_replayed": attempt,
        "eligible_replayed": eligible,
        "independent_low_pivot_rank": len(pivots),
        "pivotal_witnesses_replayed": len(witnesses),
    }
    audit = HERE / "audit.json"
    if audit.exists():
        assert json.loads(audit.read_text()) == receipt
    else:
        with audit.open("x") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
    print(receipt["status"], f"rank={len(pivots)}/{DIM}")


if __name__ == "__main__":
    main()
