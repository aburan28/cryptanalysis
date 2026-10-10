#!/usr/bin/env sage -python
"""Compute only the bucket intersection in the right-bucket quotient ring."""
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


protocol = json.loads((HERE / "protocol_v3.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_N41_QUOTIENT_JOIN_V3"
assert protocol["source_sha256"] == {
    "n41_quotient_v3.py": digest(Path(__file__)),
    "run_n41_v3.py": digest(HERE / "run_n41_v3.py"),
    "replay_result.json": digest(SOURCE),
    "sage_runtime_info.json": digest(HERE / "sage_runtime_info.json"),
}
assert not (HERE / "n41_result_v3.json").exists()

base = PolynomialRing(GF(2), "t")
t = base.gen()
F = GF(2**41, "t", modulus=t**41+t**3+1)


def decode(bits):
    return F(base([(int(bits) >> i) & 1 for i in range(41)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def w(mask):
    return sum((F.gen()**(i+1) for i in range(6) if mask >> i & 1), F.zero())


def basis(values):
    pivots = {}
    out = []
    for value in values:
        bits = encode(value)
        while bits:
            top = bits.bit_length()-1
            if top in pivots:
                bits ^= pivots[top]
            else:
                pivots[top] = bits
                out.append(value)
                break
    return out


started = time.perf_counter_ns()
replay = json.loads(SOURCE.read_text())
assert replay["status"] == "PASS_N41_SEED_PARTITION_PUBLIC_RELATION_SAGE"
rows = replay["normalized_pair_equations"][4:6]
assert [(row["seed"], row["rotation"]) for row in rows] == [(2,20),(2,25)]
ca, cb = [decode(row["normalized_c"])**(2**row["rotation"]) for row in rows]
s = w(2)
products = {w(mask)**2+s*w(mask) for mask in range(64)}
assert len(products) == 32
p_basis = basis([w(1 << i)**2+s*w(1 << i) for i in range(6)])
assert len(p_basis) == 5

D = PolynomialRing(F, "d")
d = D.gen()
right = D.one()
for p in sorted(products, key=encode):
    pp = p**(2**25)
    ss = s**(2**25)
    right *= d*d+(pp*d)**2+pp*d+ss*ss
assert right.degree() == 64 and right(cb) == 0

aa = 1+ca*ca*cb*cb
bb = ca*cb
cc0 = (ca+cb)**2
assert aa != 0 and bb != 0
scaled = aa*cc0/(bb*bb)
halftrace = F.zero()
power = scaled
for _ in range(21):
    halftrace += power
    power = power**4
assert halftrace*halftrace+halftrace == scaled
positive_r = (bb/aa)*halftrace
assert aa*positive_r*positive_r+bb*positive_r+cc0 == 0
negative_r = F.gen()+1
assert aa*negative_r*negative_r+bb*negative_r+cc0 != 0


def join(residual):
    aa = D.one()+D(residual**2)*d*d
    bb = D(residual)*d
    cc0 = D(residual**2)+d*d
    g, inv, _ = aa.xgcd(right)
    assert g.degree() == 0
    bz = (bb*inv/g[0]) % right
    cz = (cc0*inv/g[0]) % right
    zero = (D.zero(), D.zero())
    one = (D.zero(), D.one())

    def add(a, b):
        return a[0]+b[0], a[1]+b[1]

    def mul(a, b):
        uu = (a[0]*b[0]) % right
        return ((a[0]*b[1]+a[1]*b[0]+uu*bz) % right,
                (a[1]*b[1]+uu*cz) % right)

    def square(a):
        uu = (a[0]*a[0]) % right
        return ((uu*bz) % right, (a[1]*a[1]+uu*cz) % right)

    coeff = [one]
    for p in p_basis:
        p = p**(2**20)
        v = (D(p*p)*bz+D(p), D(p*p)*cz)
        power = v
        value = zero
        for a in coeff:
            value = add(value, mul(a, power))
            power = square(power)
        nxt = [zero for _ in range(len(coeff)+1)]
        for i,a in enumerate(coeff):
            nxt[i] = add(nxt[i], mul(a,value))
            nxt[i+1] = add(nxt[i+1], square(a))
        coeff = nxt
    ss = s**(2**20)
    y = (bz, cz+D(ss*ss))
    value = zero
    for a in coeff:
        value = add(value, mul(a,y))
        y = square(y)
    u,v = value
    norm = (v*v+bz*u*v+cz*u*u) % right
    intersection = norm.gcd(right)
    return {"intersection_degree":int(intersection.degree()),
            "known_right_root_in_intersection":bool(intersection(cb)==0),
            "norm_degree":int(norm.degree())}


positive = join(positive_r)
assert positive["known_right_root_in_intersection"]
negative = join(negative_r)
result = {"status":"PASS_N41_QUOTIENT_PAIR_BUCKET_JOIN_V3", "field_degree":41,
          "seed":2, "bucket_degree":int(right.degree()),
          "positive_residual":encode(positive_r),
          "negative_residual":encode(negative_r),
          "positive":positive,"negative":negative,
          "elapsed_ns":time.perf_counter_ns()-started,
          "source_sha256":protocol["source_sha256"],
          "protocol_sha256":digest(HERE/"protocol_v3.json"),"candidate_id":None}
with (HERE/"n41_result_v3.json").open("x") as stream:
    json.dump(result,stream,sort_keys=True,indent=2)
    stream.write("\n")
print({"status":result["status"],"positive":positive,"negative":negative,
       "elapsed_s":result["elapsed_ns"]/1e9},flush=True)
