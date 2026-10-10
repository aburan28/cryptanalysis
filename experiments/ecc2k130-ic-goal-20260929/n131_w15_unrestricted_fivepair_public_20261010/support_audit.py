#!/usr/bin/env python3
"""Independent binomial-coefficient replay of the folded-column count."""

import hashlib
import json
from collections import Counter
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coefficient(n1, n2, n3, degree):
    return sum(comb(n1, a)*comb(n2, b)*comb(n3, c)*2**b*3**c
               for a in range(degree+1) for b in range(degree-a+1)
               for c in [degree-a-b] if c <= n3 and b <= n2 and a <= n1)


def main():
    result = json.loads((HERE / "support_count.json").read_text())
    inp = json.loads((HERE / "input.json").read_text())
    support = BASE / "support_w15.tsv"
    groups = {}
    for line in support.read_text().splitlines():
        mask, column = map(int, line.split())
        groups.setdefault(column, set()).add(mask)
    assert sum(map(len, groups.values())) == 16441
    assert len(groups) == 16381
    whole = Counter(map(len, groups.values()))
    assert whole == {1: 16323, 2: 56, 3: 2}
    restricted = Counter(len(masks) for column, masks in groups.items()
                         if column not in inp["prefix_columns"])
    assert restricted == {1: 16323, 2: 55, 3: 1}
    e2 = coefficient(whole[1], whole[2], whole[3], 2)
    e10 = coefficient(restricted[1], restricted[2], restricted[3], 10)
    assert 4*e2 == result["signed_unordered_pair_states_before_prefix_exclusion"]
    assert str(e10) == result["elementary_symmetric_e10"]
    tuples = 32*factorial(10)*e10
    assert str(tuples) == result["distinct_column_signed_unordered_fivepair_tuples"]
    receipt = {"status": "PASS_INDEPENDENT_BINOMIAL_FIVEPAIR_COUNT",
               "multiplicities_before_prefix": dict(sorted(whole.items())),
               "multiplicities_after_prefix": dict(sorted(restricted.items())),
               "e2": str(e2), "e10": str(e10),
               "tuple_count": str(tuples),
               "source_sha256": {"script": sha(Path(__file__)),
                                 "result": sha(HERE / "support_count.json"),
                                 "input": sha(HERE / "input.json"),
                                 "support": sha(support)}}
    with (HERE / "support_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "tuple_count": receipt["tuple_count"]}))


if __name__ == "__main__":
    main()
