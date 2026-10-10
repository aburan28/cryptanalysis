#!/usr/bin/env python3
"""Independent coefficient replay of the distinct-column six-pair count."""

import hashlib
import json
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    count = json.loads((HERE / "support_count.json").read_text())
    e12 = sum(comb(16323, a)*comb(56, b)*comb(2, c)*2**b*3**c
              for a in range(13) for b in range(13-a)
              for c in [12-a-b] if c <= 2 and b <= 56 and a <= 16323)
    tuples = 64*factorial(12)*e12
    assert str(e12) == count["elementary_symmetric_e12"]
    assert str(tuples) == count["distinct_column_signed_sixpair_tuples"]
    receipt = {"status": "PASS_INDEPENDENT_W15_SIXPAIR_BINOMIAL_COUNT",
               "elementary_symmetric_e12": str(e12),
               "tuple_count": str(tuples),
               "sha256": {"script": sha(Path(__file__)),
                          "count": sha(HERE / "support_count.json")}}
    with (HERE / "support_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "tuple_count": str(tuples)}))


if __name__ == "__main__":
    main()
