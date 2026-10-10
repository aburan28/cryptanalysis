#!/usr/bin/env sage -python
"""Exact two-bucket S3 join on the frozen N41 public relation."""
import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCE = BASE / "n41_seed_partition_indexless_20261010/replay_result.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = json.loads((HERE / "protocol.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_N41_BUCKET_JOIN"
assert protocol["source_sha256"] == {
    "n41_join.py": digest(Path(__file__)),
    "run_n41.py": digest(HERE / "run_n41.py"),
    "replay_result.json": digest(SOURCE),
    "sage_runtime_info.json": digest(HERE / "sage_runtime_info.json"),
}
assert not (HERE / "n41_result.json").exists()

base = PolynomialRing(GF(2), "t")
t = base.gen()
F = GF(2**41, "t", modulus=t**41 + t**3 + 1)


def decode(bits):
    return F(base([(int(bits) >> i) & 1 for i in range(41)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def bucket(seed):
    s = sum((F.gen()**(i + 1) for i in range(6) if seed >> i & 1), F.zero())
    products = {
        w*w + s*w
        for mask in range(64)
        for w in [sum((F.gen()**(i + 1) for i in range(6) if mask >> i & 1), F.zero())]
    }
    assert len(products) == 32
    R = PolynomialRing(F, "v")
    v = R.gen()
    out = R.one()
    for p in sorted(products, key=encode):
        out *= v*v + (p*v)**2 + p*v + s*s
    assert out.degree() == 64
    return out


started = time.perf_counter_ns()
replay = json.loads(SOURCE.read_text())
assert replay["status"] == "PASS_N41_SEED_PARTITION_PUBLIC_RELATION_SAGE"
rows = replay["normalized_pair_equations"][4:6]
assert [(x["seed"], x["rotation"]) for x in rows] == [(2, 20), (2, 25)]
raw = bucket(2)
ca, cb = [decode(x["normalized_c"])**(2**x["rotation"]) for x in rows]
assert raw(decode(rows[0]["normalized_c"])) == 0
assert raw(decode(rows[1]["normalized_c"])) == 0

D = PolynomialRing(F, "d")
d = D.gen()
Z = PolynomialRing(D, "z")
z = Z.gen()
left = Z([D(a**(2**20)) for a in raw.list()])
right = D([a**(2**25) for a in raw.list()])
assert left(ca) == 0 and right(cb) == 0

Rr = PolynomialRing(F, "r")
rvar = Rr.gen()
residual_equation = (1 + ca*ca*cb*cb)*rvar*rvar + ca*cb*rvar + (ca + cb)**2
residual_roots = residual_equation.roots(multiplicities=False)
assert residual_roots
known_residual = sorted(residual_roots, key=encode)[0]


def join(residual):
    upper = (1 + z*z*d*d)*residual*residual + z*d*residual + (z + d)**2
    elimination = left.resultant(upper)
    intersection = elimination.gcd(right)
    return {
        "elimination_degree": int(elimination.degree()),
        "intersection_degree": int(intersection.degree()),
        "known_right_root_in_intersection": bool(intersection(cb) == 0),
        "intersection_roots": [encode(root) for root in intersection.roots(multiplicities=False)],
    }


positive = join(known_residual)
assert positive["known_right_root_in_intersection"]
negative_residual = F.gen() + 1
assert residual_equation(negative_residual) != 0
negative = join(negative_residual)
result = {
    "status": "PASS_N41_EXACT_PAIR_BUCKET_JOIN",
    "field_degree": 41,
    "seed": 2,
    "bucket_degree": int(raw.degree()),
    "left_pair_output": encode(ca),
    "right_pair_output": encode(cb),
    "positive_residual": encode(known_residual),
    "negative_residual": encode(negative_residual),
    "positive": positive,
    "negative": negative,
    "elapsed_ns": time.perf_counter_ns() - started,
    "source_sha256": protocol["source_sha256"],
    "protocol_sha256": digest(HERE / "protocol.json"),
    "candidate_id": None,
}
with (HERE / "n41_result.json").open("x") as stream:
    json.dump(result, stream, sort_keys=True, indent=2)
    stream.write("\n")
print({"status": result["status"], "positive": positive, "negative": negative,
       "elapsed_s": result["elapsed_ns"]/1e9}, flush=True)
