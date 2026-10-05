"""Q5 support: the degree-graded linear structure of the descended system (no solver).

For the 131 Boolean equations of S_{m+1}(x_1..x_m, r) (x_i in V_k, polynomial basis), row-reduce
with a degree-compatible pivot order and count the independent rows by top degree.  Rows whose
top degree is below the input degree are "degree falls available by linear algebra alone"; a
constant row means the target is inconsistent by linear algebra.  The profile is invariant
under the choice of degree-compatible order and of F_2-basis of F_q used to split the
equations, so it is a property of (curve, subspace, target).  This is the mechanism behind
Codex's lower formal d_reg for E0; here it is followed to larger k than any solver can reach.

m = 2, 3: g5lib descent; m = 4: the repo's reference tensor descent (pdp-scaling/descend.py).
Usage: sage -python graded_profile.py MAXK3 MAXK4  -> graded_profile.json
"""
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "ref"))
import g5lib as L  # noqa: E402

CTRL = json.loads((ROOT / "controls.json").read_text())
MAXK3 = int(sys.argv[1]) if len(sys.argv) > 1 else 9
MAXK4 = int(sys.argv[2]) if len(sys.argv) > 2 else 4


def cb(label):
    if label in L.ecc2k.RECORDS:
        return L.dec(L.ecc2k.RECORDS[label]["b_int"])
    return L.dec(next(c["b_int"] for c in CTRL["curves"] if c["label"] == label))


def graded(anf):
    """RREF of the 131 equation rows; pivot = the largest monomial in (degree, mask) order.
    Returns {top_degree: count} (degree 0 = the constant row, i.e. inconsistent)."""
    mons = sorted(anf, key=lambda mm: (bin(mm).count("1"), mm))
    idx = {mm: i for i, mm in enumerate(mons)}
    rows = [0] * L.NB
    for mm, c in anf.items():
        bit = 1 << idx[mm]
        while c:
            lo = c & -c
            rows[lo.bit_length() - 1] |= bit
            c ^= lo
    piv = {}
    for row in rows:
        while row:
            p = row.bit_length() - 1
            if p not in piv:
                piv[p] = row
                break
            row ^= piv[p]
    hist = {}
    for p in piv:
        d = bin(mons[p]).count("1")
        hist[d] = hist.get(d, 0) + 1
    return dict(sorted(hist.items()))


labels = ["E0", "A000", "B000", "A010", "RD00", "RD01", "RS00", "RS05"]
rng = random.Random(20260924 + 11)
rs = [L.dec(rng.getrandbits(131)) for _ in range(2)]
out = {"labels": labels, "rows": []}
t0 = time.time()


def emit(row):
    out["rows"].append(row)
    print(json.dumps(row), flush=True)
    (ROOT / "graded_profile.json").write_text(json.dumps(out, indent=1))


for m, kmax in ((2, 30), (3, MAXK3)):
    for k in range(2, kmax + 1):
        if m == 2 and k not in (2, 4, 6, 8, 10, 15, 20, 30):
            continue
        for lab in labels:
            b = cb(lab)
            subs = [("poly", L.poly_basis(k))]
            if lab in ("E0", "A000") and k <= 8:
                c = L.dec(CTRL["scale_constants"][0])
                subs.append(("scaled0", [c * L.ZGEN**j for j in range(k)]))
                if k <= 6:
                    subs.append(("rand0", [L.dec(u) for u in CTRL["random_bases"][0][:k]]))
            for sname, basis in subs:
                ts = time.time()
                hs = [graded(L.descended_anf(m, basis, b, r)) for r in rs]
                emit({"m": m, "k": k, "label": lab, "sub": sname, "graded": hs,
                      "seconds": round(time.time() - ts, 2)})

import descend as REF  # noqa: E402
import gf2n as RG  # noqa: E402
import sumpoly as RS  # noqa: E402

S5 = RS.load(5)
F = RG.GF2n(131, L.ecc2k.MODULUS_INT)
for k in range(2, MAXK4 + 1):
    for lab in ("E0", "A000", "B000", "RD00", "RS00"):
        b = cb(lab)
        Er = RG.Curve(F, L.enc(b))
        ts = time.time()
        hs = []
        for r in rs:
            anf = {mk: v for mk, v in REF.descend(S5, F, Er, 4, k, L.enc(r)).items() if v}
            hs.append(graded(anf))
        emit({"m": 4, "k": k, "label": lab, "sub": "poly", "graded": hs, "seconds": round(time.time() - ts, 2),
              "engine": "pdp-scaling/descend.py"})
out["seconds"] = time.time() - t0
(ROOT / "graded_profile.json").write_text(json.dumps(out, indent=1))
print("done", out["seconds"])
