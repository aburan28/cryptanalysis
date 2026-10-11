"""Independent low-pivot rank and exact group replay of all witness rows."""

import hashlib
import importlib.util
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "n41_seed_bin_quadratic_filter_20261009"
ORBITS = SOURCE / "x_orbits.bin"
SIGN = BASE / "n41_two_pair_sign_orbit_x_support_20261009/run.py"
CENSUS = BASE / "n41_two_free_pair_occupancy_20261009/audit.json"
FEATURES = [()] + [(i,) for i in range(52)] + list(itertools.combinations(range(52), 2))
INDEX = {monomial: position for position, monomial in enumerate(FEATURES)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"audit": HERE / "audit.py", "rank_source": HERE / "rank.py",
            "rank_protocol": HERE / "protocol.json", "rank_result": HERE / "result.json",
            "witnesses": HERE / "witnesses.json", "orbits": ORBITS,
            "sign_source": SIGN, "independent_sage_census": CENSUS}


def freeze():
    assert len(FEATURES) == len(INDEX) == 1379
    result = json.loads((HERE / "result.json").read_text())
    census = json.loads(CENSUS.read_text())
    assert result["status"] == "FULL_QUADRATIC_EVALUATION_RANK"
    assert census["status"] == "PASS_FULL_EXACT_RECOUNT_AND_GROUP_REPLAY"
    new_json(HERE / "audit_protocol.json", {
        "status": "FROZEN_BEFORE_AUDIT",
        "method": "independent feature enumeration and low-bit Gaussian pivots on all witness rows; exact pair-column, sign-orbit, and group-sum replay",
        "source_sha256": {name: sha(path) for name,path in sources().items()},
    })


def feature_row(left, right, x):
    bits = (x >> 1) | (left << 40) | (right << 46)
    active = [index for index in range(52) if bits & (1 << index)]
    row = 1
    for bit in active:
        row |= 1 << INDEX[(bit,)]
    for pair in itertools.combinations(active, 2):
        row |= 1 << INDEX[pair]
    return row


def run():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name,path in sources().items()}
    witnesses = json.loads((HERE / "witnesses.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert len(witnesses) == result["feature_count"] == 1379
    data = ORBITS.read_bytes()
    assert len(data) == 1583568 * 12
    spec = importlib.util.spec_from_file_location("frozen_sign_orbit", SIGN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, geometry, _, curve = module.load_inputs()
    assert geometry["curve_id"] == "EC1N41Ckb1h7d5e80d3c4d0"
    left, left_neg = module.build_domain(curve, geometry["point_rows_by_unique_rotation"]["20"])
    right, right_neg = module.build_domain(curve, geometry["point_rows_by_unique_rotation"]["30"])
    pivots = {}
    seen_indices = set()
    bins = Counter()
    for witness in witnesses:
        index = witness["source_index"]
        assert 0 <= index < 1583568 and index not in seen_indices
        seen_indices.add(index)
        raw = data[12 * index:12 * (index + 1)]
        s,t = raw[0],raw[1]
        x = int.from_bytes(raw[2:8], "little")
        i = int.from_bytes(raw[8:10], "little")
        j = int.from_bytes(raw[10:12], "little")
        assert (s,t,x,i,j) == (witness["left_seed"],witness["right_seed"],
                               witness["x"],witness["left_pair_index"],
                               witness["right_pair_index"])
        assert 1 <= s <= 63 and 1 <= t <= 63 and x < 1 << 41 and x & 1 == 0
        assert 0 <= i < len(left) and 0 <= j < len(right)
        assert left[i][2] == s and right[j][2] == t
        assert left[i][1] & right[j][1] == 0
        assert i * 1956 + j < left_neg[i] * 1956 + right_neg[j]
        point = curve.add(left[i][0],right[j][0])
        assert point is not None and point[0] == x
        row = feature_row(s,t,x)
        while row:
            pivot = row & -row
            previous = pivots.get(pivot)
            if previous is None:
                pivots[pivot] = row
                break
            row ^= previous
        assert row, "producer witness rows are dependent under independent feature order"
        bins[(s,t)] += 1
    assert len(pivots) == len(FEATURES) == 1379
    output = {"status": "PASS_FULL_QUADRATIC_RANK_AND_GROUP_WITNESS_REPLAY",
              "rank": len(pivots), "feature_count": len(FEATURES),
              "witness_rows_replayed": len(witnesses),
              "distinct_seed_bins_in_witness": len(bins),
              "audit_protocol_sha256": sha(HERE / "audit_protocol.json"),
              "witnesses_sha256": sha(HERE / "witnesses.json"),
              "independent_sage_census_sha256": sha(CENSUS)}
    new_json(HERE / "audit.json", output)
    print(output["status"], "rank", output["rank"])


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
