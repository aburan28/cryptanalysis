"""Which Boolean-degree slices of the descended S_{m+1} depend on b?  For a fixed subspace and
target x(R), compare the ANF coefficient of every monomial for E0 (b = 1) and other curves;
report, per Boolean degree, how many monomials have b-dependent coefficients.
m = 3 via g5lib (V_k polynomial basis and a random subspace); m = 4 via the repo's reference
descent (polynomial basis).  Usage: sage -python b_dependence.py -> b_dependence.json"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "ref"))
import g5lib as L  # noqa: E402

CTRL = json.loads((ROOT / "controls.json").read_text())


def cb(label):
    if label in L.ecc2k.RECORDS:
        return L.dec(L.ecc2k.RECORDS[label]["b_int"])
    return L.dec(next(c["b_int"] for c in CTRL["curves"] if c["label"] == label))


def compare(a, b):
    out = {}
    for mm in set(a) | set(b):
        d = bin(mm).count("1")
        o = out.setdefault(d, [0, 0])
        o[0] += 1
        if a.get(mm, 0) != b.get(mm, 0):
            o[1] += 1
    return {str(d): {"monomials": v[0], "b_dependent": v[1]} for d, v in sorted(out.items())}


rng = random.Random(20260924 + 13)
r = L.dec(rng.getrandbits(131))
res = {"rows": []}
for k in (4, 6, 8):
    for sub, basis in (("poly", L.poly_basis(k)), ("rand0", [L.dec(u) for u in CTRL["random_bases"][0][:min(k, 6)]])):
        if len(basis) != k:
            continue
        base = L.descended_anf(3, basis, cb("E0"), r)
        for lab in ("A000", "RD00"):
            other = L.descended_anf(3, basis, cb(lab), r)
            row = {"m": 3, "k": k, "sub": sub, "pair": f"E0 vs {lab}", "by_degree": compare(base, other)}
            res["rows"].append(row)
            print(json.dumps(row), flush=True)
import descend as REF  # noqa: E402
import gf2n as RG  # noqa: E402
import sumpoly as RS  # noqa: E402

S5 = RS.load(5)
F = RG.GF2n(131, L.ecc2k.MODULUS_INT)
for k in (3, 4):
    anfs = {}
    for lab in ("E0", "A000"):
        Er = RG.Curve(F, L.enc(cb(lab)))
        anfs[lab] = {mk: v for mk, v in REF.descend(S5, F, Er, 4, k, L.enc(r)).items() if v}
    row = {"m": 4, "k": k, "sub": "poly", "pair": "E0 vs A000", "by_degree": compare(anfs["E0"], anfs["A000"])}
    res["rows"].append(row)
    print(json.dumps(row), flush=True)
(ROOT / "b_dependence.json").write_text(json.dumps(res, indent=1))
