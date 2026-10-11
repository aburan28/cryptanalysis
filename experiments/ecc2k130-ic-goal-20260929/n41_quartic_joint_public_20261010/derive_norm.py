"""Reduce the rotated four-atom split to one Artin--Schreier branch bit.

All polynomial arithmetic is sparse, exact, and over GF(2).  The input
factor terms use variables (a,v,u,P,Q), with b=a+v^2+v and z=u^2+u.
"""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FACTORS = ROOT / "rotated_fouratom_factorization_20261010" / "symbolic_result.json"
RESULTANT = ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"


def toggle(out, term):
    if term in out:
        out.remove(term)
    else:
        out.add(term)


def mul(left, right):
    out = set()
    for x in left:
        for y in right:
            toggle(out, tuple(i + j for i, j in zip(x, y)))
    return out


def shift(poly, axis):
    out = set()
    for term in poly:
        exponent = term[axis]
        for k in range(exponent + 1):
            if k & ~exponent == 0:
                row = list(term)
                row[axis] = k
                toggle(out, tuple(row))
    return out


def reduce_as(poly, axis, rhs_axes):
    """Reduce x^2+x=sum(rhs_axes), preserving all other variables."""
    out = set(poly)
    while True:
        term = next((t for t in out if t[axis] >= 2), None)
        if term is None:
            return out
        out.remove(term)
        row = list(term)
        row[axis] -= 1
        toggle(out, tuple(row))
        for rhs_axis in rhs_axes:
            row = list(term)
            row[axis] -= 2
            row[rhs_axis] += 1
            toggle(out, tuple(row))


def factor_in_w(factor):
    # Input (a,v,u,P,Q); output (a,S,v,w,P,Q), u=w+v, S=v^2+v.
    expanded = set()
    for a, v, u, p, q in factor:
        for k in range(u + 1):
            if k & ~u == 0:
                toggle(expanded, (a, 0, v + u - k, k, p, q))
    reduced = reduce_as(expanded, 2, (1,))
    assert all(term[2] == 0 for term in reduced)
    return {(a, s, w, p, q) for a, s, _, w, p, q in reduced}


def resultant_in_s_z(terms):
    # Input (a,b,P,Q,z); output (a,S,Z,P,Q), b=a+S.
    out = set()
    for ea, eb, ep, eq, ez in terms:
        for k in range(eb + 1):
            if k & ~eb == 0:
                toggle(out, (ea + eb - k, k, ez, ep, eq))
    return out


def main():
    factor_data = json.loads(FACTORS.read_text())
    factors = [set(map(tuple, f["terms"])) for f in factor_data["factors"]]
    assert len(factors) == 2
    assert shift(factors[0], 1) == factors[1]
    assert shift(factors[0], 2) == factors[1]
    assert shift(shift(factors[0], 1), 2) == factors[0]

    f0 = factor_in_w(factors[0])
    f1 = factor_in_w(factors[1])
    assert shift(f0, 2) == f1
    # Reduce w^2+w=Z+S.  Place Z before w: (a,S,Z,w,P,Q).
    lifted = {(a, s, 0, w, p, q) for a, s, w, p, q in f0}
    linear = reduce_as(lifted, 3, (1, 2))
    assert all(t[3] <= 1 for t in linear)
    A = {(a, s, z, p, q) for a, s, z, w, p, q in linear if w == 0}
    B = {(a, s, z, p, q) for a, s, z, w, p, q in linear if w == 1}
    # Norm(A+wB) = A^2 + A*B + (Z+S)*B^2.
    aa, ab, bb = mul(A, A), mul(A, B), mul(B, B)
    norm = set()
    for part in (aa, ab):
        for row in part:
            toggle(norm, row)
    for axis in (1, 2):
        for row in bb:
            shifted = list(row)
            shifted[axis] += 1
            toggle(norm, tuple(shifted))
    original = resultant_in_s_z(json.loads(RESULTANT.read_text())["terms"])
    assert norm == original
    assert len(A) and len(B)
    result = {
        "status": "PASS_EXACT_SINGLE_BRANCH_NORM",
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {"symbolic_result.json": hashlib.sha256(FACTORS.read_bytes()).hexdigest(),
                         "resultant.json": hashlib.sha256(RESULTANT.read_bytes()).hexdigest()},
        "identities": ["F0(v+1,u)=F1(v,u)", "F0(v,u+1)=F1(v,u)",
                       "F0=A+wB; w=u+v; w^2+w=Z+S; S=a+b; Z=z",
                       "H=A^2+A*B+(Z+S)*B^2"],
        "counts": {"factor_0_terms": len(factors[0]), "factor_1_terms": len(factors[1]),
                   "single_branch_factor_terms": len(f0), "A_terms": len(A),
                   "B_terms": len(B), "norm_terms": len(norm),
                   "original_after_substitution_terms": len(original)},
        "A_terms": sorted(map(list, A)), "B_terms": sorted(map(list, B)),
    }
    (HERE / "norm_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "counts": result["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
