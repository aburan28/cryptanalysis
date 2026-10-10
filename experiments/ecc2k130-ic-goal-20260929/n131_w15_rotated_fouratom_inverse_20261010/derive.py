#!/usr/bin/env sage -python
"""Universal four-atom resultant with separately Frobenius-rotated pair seeds."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010/resultant_terms.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


freeze = json.loads((HERE / "protocol.json").read_text())
assert freeze["status"] == "FROZEN_BEFORE_ROTATED_RESULTANT_DERIVATION"
assert freeze["source_sha256"] == {"derive.py": sha(Path(__file__)),
                                    "old_resultant": sha(OLD),
                                    "sage_runtime_info": sha(HERE / "sage_runtime_info.json")}
assert not (HERE / "resultant.json").exists()

ring = PolynomialRing(GF(2), names=("a", "b", "p", "q", "z", "c", "d"))
a, b, p, q, z, c, d = ring.gens()
left = (1+p**2)*c**2 + p*c + a**2
right = (1+q**2)*d**2 + q*d + b**2
upper = (1+c**2*d**2)*z**2 + c*d*z + (c+d)**2
resultant = left.resultant(right.resultant(upper, d), c)
assert resultant.degree(c) == resultant.degree(d) == 0
assert resultant(a=b, b=a, p=q, q=p) == resultant
old = json.loads(OLD.read_text())
assert old["status"] == "PASS_UNIVERSAL_SAME_SEED_FOUR_ATOM_RESULTANT"
old_terms = {tuple(row) for row in old["terms_s_p_q_z"]}
same_seed = resultant(a=a, b=a)
specialized_terms = set()
for exponents, coefficient in same_seed.dict().items():
    ea, eb, ep, eq, ez, ec, ed = map(int, exponents)
    assert int(coefficient) == 1 and eb == ec == ed == 0
    specialized_terms.add((ea, ep, eq, ez))
assert specialized_terms == old_terms
terms = []
for exponents, coefficient in resultant.dict().items():
    ea, eb, ep, eq, ez, ec, ed = map(int, exponents)
    assert int(coefficient) == 1 and ec == ed == 0
    terms.append([ea, eb, ep, eq, ez])
terms.sort()
record = {
    "status": "PASS_UNIVERSAL_ROTATED_FOUR_ATOM_RESULTANT",
    "pair_equations": ["(1+p^2)c^2+pc+a^2=0", "(1+q^2)d^2+qd+b^2=0"],
    "upper_equation": "(1+c^2*d^2)z^2+cdz+(c+d)^2=0",
    "resultant_order": ["d", "c"],
    "variable_order": ["a", "b", "p", "q", "z"],
    "degrees": {str(v): int(resultant.degree(v)) for v in (a,b,p,q,z)},
    "term_count": len(terms), "terms": terms,
    "same_seed_specialization_matches_archived_150_terms": True,
    "source_sha256": freeze["source_sha256"],
    "protocol_sha256": sha(HERE / "protocol.json"),
}
with (HERE / "resultant.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
print({"status": record["status"], "term_count": len(terms), "degrees": record["degrees"]})
