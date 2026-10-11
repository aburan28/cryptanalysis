"""Audit seed-conditioned product images on N41 hits and W15 geometry."""

import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
protocol = json.loads((HERE / "protocol.json").read_text())
relaxed = json.loads((HERE / "relaxed_receipt.json").read_text())
exact = json.loads((HERE / "exact_receipt.json").read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


assert protocol["sha256"]["relaxed_binary"] == sha(HERE / "relaxed_panel_native")
assert protocol["sha256"]["exact_binary"] == sha(HERE / "exact_panel_native")


def product(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a <<= 1
        b >>= 1
    return result


def columns(s, dimension):
    return [(1 << (2*i)) ^ product(s, 1 << i) for i in range(dimension)]


def pivots(values):
    basis = {}
    for value in values:
        while value:
            high = value.bit_length()-1
            if high in basis:
                value ^= basis[high]
            else:
                basis[high] = value
                break
    return basis


def member(value, basis):
    while value:
        high = value.bit_length()-1
        if high not in basis:
            return False
        value ^= basis[high]
    return True


rank_histograms = {}
odd_rank_histograms = {}
for dimension in (6, 15):
    ranks = Counter()
    odd_ranks = Counter()
    for s in range(1, 1 << dimension):
        images = columns(s, dimension)
        ranks[len(pivots(images))] += 1
        odd_images = [sum(((value >> (2*j+1)) & 1) << j
                          for j in range(dimension-1))
                      for value in images]
        odd_ranks[len(pivots(odd_images))] += 1
    assert ranks == {dimension-1: (1 << dimension)-1}
    rank_histograms[str(dimension)] = dict(sorted(ranks.items()))
    odd_rank_histograms[str(dimension)] = dict(sorted(odd_ranks.items()))

checks = []
for rq, eq in zip(relaxed["queries"], exact["queries"]):
    if rq["status"] != "RELAXED_SUM_HIT":
        continue
    row = {"label": rq["label"], "exact_status": eq["status"]}
    for side in ("left", "right"):
        witness = rq[f"{side}_witness"]
        s, p = witness["seed_sum"], witness["product_mask"]
        basis = pivots(columns(s, 6))
        image_member = member(p, basis)
        roots = [a for a in range(1, 64)
                 if a ^ s and product(a, a ^ s) == p]
        assert image_member == bool(roots)
        assert len(roots) in (0, 2)
        row[f"{side}_factorable"] = image_member
        row[f"{side}_source_masks"] = sorted(roots)
    checks.append(row)
assert len(checks) == 10
assert checks[0]["label"] == "positive"
assert checks[0]["left_source_masks"] == [53, 59]
assert checks[0]["right_source_masks"] == [1, 6]
assert all(not row["right_factorable"] for row in checks[1:])
assert sum(not row["left_factorable"] for row in checks[1:]) == 7

out = {"status": "PASS_SEED_CONDITIONED_PRODUCT_IMAGE_GATE",
       "rank_histograms": rank_histograms,
       "odd_coordinate_rank_histograms": odd_rank_histograms,
       "product_span_dimensions": {"W6": 11, "W15": 29},
       "product_image_dimensions": {"W6": 5, "W15": 14},
       "image_density_in_product_span": {"W6": "1/64", "W15": "1/32768"},
       "w15_parity_check_table_bits": 32767*15*29,
       "relaxed_hit_checks": checks,
       "protocol_sha256": sha(HERE / "protocol.json"),
       "relaxed_receipt_sha256": sha(HERE / "relaxed_receipt.json"),
       "exact_receipt_sha256": sha(HERE / "exact_receipt.json"),
       "source_sha256": sha(__file__)}
(HERE / "factorization_gate.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], "hits", len(checks))
