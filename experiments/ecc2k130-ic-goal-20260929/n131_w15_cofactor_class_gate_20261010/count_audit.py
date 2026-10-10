#!/usr/bin/env python3
"""Independent binomial-coefficient replay of the colored five-pair count."""

import hashlib
import json
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coefficient(n1, n2, n3, degree):
    return sum(comb(n1, a)*comb(n2, b)*comb(n3, c)*2**b*3**c
               for a in range(degree+1) for b in range(degree-a+1)
               for c in [degree-a-b] if a <= n1 and b <= n2 and c <= n3)


def main():
    count = json.loads((HERE / "count.json").read_text())
    bits = (HERE / "class_bits.bin").read_bytes()
    assert bits[4] == bits[17] == 1
    zero = [coefficient(8236, 28, 1, degree) for degree in range(11)]
    one = [coefficient(8087, 27, 0, degree) for degree in range(11)]
    unrestricted = 32*factorial(10)*sum(zero[j]*one[10-j] for j in range(11))
    constrained = 32*sum(comb(5, j)*factorial(2*j)*factorial(10-2*j)
                         *one[2*j]*zero[10-2*j] for j in range(6))
    assert str(unrestricted) == count["unrestricted_tuple_count"]
    assert str(constrained) == count["subgroup_pair_tuple_count"]
    receipt = {"status": "PASS_INDEPENDENT_BINOMIAL_CLASS_PAIR_COUNT",
               "after_prefix_column_multiplicities": {
                   "0": {"1": 8236, "2": 28, "3": 1},
                   "1": {"1": 8087, "2": 27, "3": 0}},
               "prefix_classes": [1, 1],
               "unrestricted_tuple_count": str(unrestricted),
               "subgroup_pair_tuple_count": str(constrained),
               "sha256": {"script": sha(Path(__file__)),
                          "count": sha(HERE / "count.json"),
                          "class_bits": sha(HERE / "class_bits.bin")}}
    with (HERE / "count_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "subgroup_pair_tuple_count": str(constrained)}))


if __name__ == "__main__":
    main()
