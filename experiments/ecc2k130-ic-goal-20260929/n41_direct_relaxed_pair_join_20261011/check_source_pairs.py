"""Recover exact W6 source-mask pairs for returned relaxed witnesses."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
receipt = json.loads((HERE / "receipt.json").read_text())
source = json.loads((HERE.parent / "n41_two_pair_relaxation_20261011/targets.json").read_text())


def carryless_product(a, b):
    value = 0
    for i in range(6):
        if (b >> i) & 1:
            value ^= a << i
    return value


def solve(witness):
    return [[a, b] for a in range(1, 64) for b in range(a, 64)
            if a ^ b == witness["seed_sum"]
            and carryless_product(a, b) == witness["product_mask"]]


positive = receipt["queries"][0]
assert positive["label"] == "positive" and positive["status"] == "RELAXED_SUM_HIT"
left = solve(positive["left_witness"])
right = solve(positive["right_witness"])
assert left == [[53, 59]] and right == [[1, 6]]
assert source["known_positive"]["source_masks"] == [53, 59, 1, 6]
output = {
    "status": "PASS_EXACT_SOURCE_COEFFICIENT_RECOVERY",
    "left_pairs": left,
    "right_pairs": right,
    "source_masks": source["known_positive"]["source_masks"],
    "receipt_sha256": hashlib.sha256((HERE / "receipt.json").read_bytes()).hexdigest(),
    "fixture_sha256": hashlib.sha256((HERE.parent / "n41_two_pair_relaxation_20261011/targets.json").read_bytes()).hexdigest(),
}
(HERE / "source_pair_check.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
print(output["status"], left, right)
