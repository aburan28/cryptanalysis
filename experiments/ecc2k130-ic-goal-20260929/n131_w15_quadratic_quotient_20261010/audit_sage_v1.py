#!/usr/bin/env sage -python
"""Independently check native N131 resultant remainders and source witness."""
import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, ZZ

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
NORM = BASE / "n131_w15_pair_bucket_polynomial_20261010/polynomial_sparse_v3.json"
SOURCE = BASE / "n131_w15_sparse_pair_bucket_join_20261010/as_result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol_path = HERE / "audit_protocol.json"
protocol = json.loads(protocol_path.read_text())
assert protocol["status"] == "FROZEN_BEFORE_N131_RESULTANT_SAGE_AUDIT"
for rel, expected in protocol["sha256"].items():
    assert sha((HERE / rel).resolve()) == expected, rel
assert not (HERE / "audit_result.json").exists()

started = time.perf_counter_ns()
B = PolynomialRing(GF(2), "t")
t = B.gen()
F = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
R = PolynomialRing(F, "c")


def decode(bits):
    return F(B(ZZ(bits).digits(2)))


sparse = json.loads(NORM.read_text())
assert sparse["field_degree"] == 131 and sparse["seed"] == 13686
left_coefficients = [F.zero()] * 32769
for exponent, bits in sparse["terms"]:
    left_coefficients[int(exponent)] = decode(bits)**(2**26)
left = R(left_coefficients)
assert left.degree() == 32768
print({"phase": "left_polynomial_ready", "elapsed_s": (time.perf_counter_ns()-started)/1e9}, flush=True)

source = json.loads(SOURCE.read_text())
known = source["positive"]["bucket_hits"][0]
assert known["left_masks"] == [5576, 8382]
assert known["right_masks"] == [3, 13685]
c = decode(known["left_output"])
d = decode(known["right_output"])
r = decode(source["positive_residual"])
assert left(c) == 0
assert (1+c*c*d*d)*r*r + c*d*r + (c+d)**2 == 0

rows = {}
for label in ("positive", "negative"):
    path = HERE / f"certificate_{label}.remainder.bin"
    data = path.read_bytes()
    assert len(data) == 32768 * 17
    values = [decode(int.from_bytes(data[i:i+17], "little"))
              for i in range(0, len(data), 17)]
    remainder = R(values)
    native = json.loads((HERE / f"certificate_{label}.json").read_text())
    receipt = json.loads((HERE / f"certificate_{label}.receipt.json").read_text())
    assert native["status"] == "COMPLETE_QUOTIENT_INTERSECTION"
    assert receipt["status"] == "COMPLETE" and receipt["returncode"] == 0
    assert receipt["remainder_sha256"] == sha(path)
    assert int(remainder.degree()) == native["remainder_degree"]
    common = left.gcd(remainder)
    assert int(common.degree()) == native["intersection_degree"]
    assert int(common.degree()) == (1 if label == "positive" else 0)
    if label == "positive":
        assert common(c) == 0
    rows[label] = {"remainder_degree": int(remainder.degree()),
                   "gcd_degree": int(common.degree()),
                   "known_left_root_in_gcd": bool(common(c) == 0),
                   "remainder_sha256": sha(path),
                   "elapsed_s": (time.perf_counter_ns()-started)/1e9}
    print({"phase": label + "_gcd_checked", **rows[label]}, flush=True)

peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
result = {"status": "PASS_INDEPENDENT_N131_RESULTANT_GCD_AUDIT",
          "field_degree": 131, "left_polynomial_degree": int(left.degree()),
          "known_source_masks": [known["left_masks"], known["right_masks"]],
          "known_source_s3_replay": True, "cases": rows,
          "elapsed_ns": time.perf_counter_ns()-started,
          "peak_rss_bytes": int(peak),
          "protocol_sha256": sha(protocol_path), "candidate_id": None,
          "target_count": 0}
with (HERE / "audit_result.json").open("x") as output:
    json.dump(result, output, sort_keys=True, indent=2)
    output.write("\n")
print(json.dumps(result, sort_keys=True), flush=True)
