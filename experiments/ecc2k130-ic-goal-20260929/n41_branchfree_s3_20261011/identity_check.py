"""Independent GF(2^41) check of all fixture links and S3 equivalence."""

import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
W9 = HERE.parent / "n41_w7_entropy_cubic_20261011/w9"
N = 41
MASK = (1 << N) - 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(left, right):
    output = 0
    while right:
        if right & 1:
            output ^= left
        right >>= 1
        left <<= 1
        if left >> N:
            left = (left & MASK) ^ 9
    return output


def square(value):
    return mul(value, value)


def frob(value, turns):
    for _ in range(turns):
        value = square(value)
    return value


def check(left, right, output):
    product = mul(mul(left, right), output)
    total = left ^ right ^ output
    branchfree = total == (product ^ frob(product, N - 1))
    semaev = square(total) == (square(product) ^ product)
    assert branchfree == semaev
    return branchfree


def check_pair(seed_sum, seed_product, output):
    product = mul(seed_product, output)
    total = seed_sum ^ output
    branchfree = total == (product ^ frob(product, N - 1))
    semaev = square(total) == (square(product) ^ product)
    assert branchfree == semaev
    return branchfree


fixture = json.loads((W9 / "fixture.json").read_text())
field_links = []
for i in range(4):
    a = fixture["known_masks"][2 * i] << 1
    b = fixture["known_masks"][2 * i + 1] << 1
    s = frob(a ^ b, 10 * i)
    p = frob(mul(a, b), 10 * i)
    c = fixture["pair_reciprocals"][i]
    field_links.append(check_pair(s, p, c))
for i in range(2):
    field_links.append(check(fixture["pair_reciprocals"][2 * i],
                             fixture["pair_reciprocals"][2 * i + 1],
                             fixture["middle_reciprocals"][i]))
target_z = fixture["raw_target_reciprocals"][fixture["known_raw_preimage_index"]]
field_links.append(check(*fixture["middle_reciprocals"], target_z))
assert field_links == [True] * 7, field_links

rng = random.Random(20261011)
random_valid = 0
for _ in range(1024):
    values = [rng.randrange(1 << N) for _ in range(3)]
    random_valid += check(*values)
out = {"status": "PASS_BRANCHFREE_S3_FIELD_IDENTITY_CHECK",
       "fixture_link_count": len(field_links),
       "all_fixture_links_valid": all(field_links),
       "random_triples_checked": 1024,
       "random_s3_hits": random_valid,
       "source_sha256": sha(Path(__file__)),
       "fixture_sha256": sha(W9 / "fixture.json")}
(HERE / "identity_check.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], len(field_links), random_valid)
