"""Independent source-row and low-pivot rank replay for the N41 certificate."""

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w6_offset_quad_rank_20261010"
FILES = [SOURCE / "quad_outputs.tsv", SOURCE / "quad_outputs_b.tsv"]
FEATURES = 1681


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return [{k: int(v) for k, v in row.items()} for row in reader]


def reverse_features(a, b):
    # Independent order: B-major cross products, then reversed B and A bits.
    values = [1]
    values += [(b >> i) & 1 for i in range(40, 0, -1)]
    values += [(a >> i) & 1 for i in range(40, 0, -1)]
    values += [((a >> i) & (b >> j)) & 1
               for j in range(40, 0, -1) for i in range(40, 0, -1)]
    assert len(values) == FEATURES
    return sum(bit << index for index, bit in enumerate(values))


def main():
    protocol = json.loads((HERE / "protocol_v2.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert result["protocol_sha256"] == digest(HERE / "protocol_v2.json")
    assert protocol["producer_sha256"] == digest(HERE / "run.py")
    assert protocol["source_sha256"] == {p.name: digest(p) for p in FILES}
    assert protocol["offsets"] == list(range(8))
    assert result["status"] == "FULL_BILINEAR_RANK"
    assert result["rank"] == result["feature_count"] == FEATURES
    assert len(result["pivotal_witnesses"]) == FEATURES
    left, right = (rows(p) for p in FILES)
    pivots = {}
    for witness in result["pivotal_witnesses"]:
        ia, ib, sa, sb, a, b, ca, cb = witness
        la, rb = left[ia], right[ib]
        assert (la["seed"], la["x"], la["columns"]) == (sa, a, ca)
        assert (rb["seed"], rb["x"], rb["columns"]) == (sb, b, cb)
        assert 0 <= (sa ^ sb) <= 7 and (ca & cb) == 0
        assert a & 1 == b & 1 == 0
        row = reverse_features(a, b)
        while row:
            bit = row & -row
            if bit not in pivots:
                pivots[bit] = row
                break
            row ^= pivots[bit]
        else:
            raise AssertionError("dependent archived witness")
    assert len(pivots) == FEATURES
    receipt = {
        "status": "PASS_N41_CROSSBLOCK_BILINEAR_RANK",
        "protocol_sha256": digest(HERE / "protocol_v2.json"),
        "result_sha256": digest(HERE / "result.json"),
        "pivotal_rows_replayed": FEATURES,
        "independent_low_pivot_rank": len(pivots),
        "source_rows": [len(left), len(right)],
    }
    audit = HERE / "audit.json"
    if audit.exists():
        assert json.loads(audit.read_text()) == receipt
    else:
        with audit.open("x") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
    print(receipt["status"])


if __name__ == "__main__":
    main()
