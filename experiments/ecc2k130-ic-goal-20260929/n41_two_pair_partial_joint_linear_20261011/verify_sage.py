"""Independent Sage field, source-image, and GF(2) rank audit."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector


HERE = Path(__file__).resolve().parent
assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def field_of(n):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**41+t**3+1 if n == 41 else t**131+t**13+t**2+t+1
    field = GF(2**n, "t", modulus=modulus)

    def dec(value):
        return field(ring([(int(value) >> i) & 1 for i in range(n)]))

    def enc(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    return field, dec, enc


def check_case(n, row, target, width, rotations, source_dim):
    field, dec, enc = field_of(n)
    values = row.get("coordinates", row.get("pair_coordinates"))
    c0, d0 = [dec(value & ~((1 << width)-1)) for value in values]
    z = dec(target)
    seeds = row.get("seed_masks", [13686, 13686])
    states = []
    for seed, rotation, x0 in zip(seeds, rotations, (c0, d0)):
        s = dec(seed << 1)**(2**rotation)
        images = [(dec(1 << (j+1))**(2**rotation))**2
                  +s*(dec(1 << (j+1))**(2**rotation))
                  for j in range(source_dim)]
        bit_basis = {}
        basis = []
        for candidate in images:
            value = enc(candidate)
            while value:
                pivot = value.bit_length()-1
                if pivot in bit_basis:
                    value ^= bit_basis[pivot]
                else:
                    bit_basis[pivot] = value
                    basis.append(candidate)
                    break
        assert len(basis) == source_dim-1
        delta = [dec(1 << i) for i in range(width)]
        const = x0**2+s**2
        linear = [e**2 for e in delta]
        product = [b*x0+b**2*x0**2 for b in basis]
        cross = [b*e+b**2*e**2 for e in delta for b in basis]
        states.append((x0, const, linear, product, cross, delta))
    (c, lc, ldelta, lproduct, lcross, le), (d, rc, rdelta, rproduct, rcross, re) = states
    cd = c*d
    upper = z**2+(cd)**2*z**2+cd*z+c**2+d**2
    left_upper = [e**2+(e*d)**2*z**2+(e*d)*z for e in le]
    right_upper = [e**2+(c*e)**2*z**2+(c*e)*z for e in re]
    cross_upper = [(e*f)**2*z**2+(e*f)*z for e in le for f in re]
    columns = []
    columns += [(v,field.zero(),u) for v,u in zip(ldelta,left_upper)]
    columns += [(field.zero(),v,u) for v,u in zip(rdelta,right_upper)]
    columns += [(v,field.zero(),field.zero()) for v in lproduct+lcross]
    columns += [(field.zero(),v,field.zero()) for v in rproduct+rcross]
    columns += [(field.zero(),field.zero(),u) for u in cross_upper]
    vectors = [sum(enc(part) << (i*n) for i,part in enumerate(column))
               for column in columns]
    rhs = enc(lc) | (enc(rc) << n) | (enc(upper) << (2*n))
    bits = 3*n
    span = matrix(GF(2), len(vectors), bits)
    for i, word in enumerate(vectors):
        while word:
            bit = (word & -word).bit_length()-1
            span[i,bit] = 1
            word &= word-1
    rank = int(span.rank())
    rhs_vector = vector(GF(2), [(rhs >> i)&1 for i in range(bits)])
    augmented_rank = int(span.stack(rhs_vector).rank())
    return {"rank": rank, "augmented_rank": augmented_rank,
            "consistent": rank == augmented_rank, "variables": len(columns)}


n41 = json.loads((HERE / "result.json").read_text())
n131 = json.loads((HERE / "n131_wide_result.json").read_text())
n131_panel = json.loads((HERE / "n131_panel.json").read_text())
holdout = json.loads((HERE / "holdout64_result.json").read_text())
checks = []
for row in (n41["rows"][0], n41["rows"][1]):
    for width in (8, 10):
        _, dec41, enc41 = field_of(41)
        target_z = enc41(1/dec41(n41["target"][0]))
        result = check_case(41, row, target_z, width, (20,30), 6)
        prior = row["decisions"][str(width)]
        assert result["rank"] == prior["rank"]
        assert result["consistent"] == prior["joint"]
        checks.append({"field_degree": 41, "label": row["label"],
                       "width": width, **result})
for row in (n131["rows"][0], n131["rows"][1]):
    for width in (32, 36):
        result = check_case(131, row, n131_panel["target_z"], width, (26,39), 18)
        prior = row["decisions"][str(width)]
        assert result["rank"] == prior["rank"]
        assert result["consistent"] == prior["joint"]
        checks.append({"field_degree": 131, "label": row["label"],
                       "width": width, **result})
survivor = holdout["rows"][18]
assert survivor["decisions"]["32"]["joint"]
survivor_result = check_case(131, survivor, n131_panel["target_z"], 32,
                             (26,39), 18)
assert survivor_result["rank"] == survivor["decisions"]["32"]["rank"]
assert survivor_result["consistent"]
field131, dec131, _ = field_of(131)
c, d = (dec131(value) for value in survivor["coordinates"])
z = dec131(n131_panel["target_z"])
assert z**2+(c*d)**2*z**2+c*d*z+c**2+d**2 != 0
checks.append({"field_degree": 131, "label": survivor["label"],
               "width": 32, "exact_s3_zero": False, **survivor_result})

out = {"status": "PASS_INDEPENDENT_SAGE_JOINT_LINEAR_RANK",
       "checks": checks,
       "sha256": {name: sha(name) for name in
                  ("result.json", "n131_result.json", "n131_wide_result.json",
                   "holdout64_result.json",
                   "n131_panel.json", "sage_runtime_info.json")}}
(HERE / "sage_audit.json").write_text(json.dumps(out, indent=2, sort_keys=True)+"\n")
print(out["status"], len(checks))
