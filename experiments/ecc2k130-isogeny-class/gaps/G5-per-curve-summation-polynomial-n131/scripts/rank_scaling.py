"""Q5 support: the number of independent Boolean equations (F_2-dimension of the span of the
coefficients of the descended S_{m+1}) as a function of the subspace dimension k, for E0, the
class representatives and control curves, on the polynomial-basis subspace V_k (and, for E0,
on c*V_k and a random subspace).  This is the quantity behind E0's lower formal d_reg
(E0 k = 6: 115 vs 131).  Also the rank of the non-constant part (a random target is
inconsistent by linear algebra alone iff the constant is outside that span).

m = 2, 3 with this repo's own descent (g5lib); m = 4 with the repo's reference tensor descent
(experiments/pdp-scaling/descend.py, polynomial basis only).
Usage: sage -python rank_scaling.py  -> rank_scaling.json
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
MAXK = {2: int(sys.argv[1]) if len(sys.argv) > 1 else 40, 3: int(sys.argv[2]) if len(sys.argv) > 2 else 9}


def cb(label):
    if label in L.ecc2k.RECORDS:
        return L.dec(L.ecc2k.RECORDS[label]["b_int"])
    return L.dec(next(c["b_int"] for c in CTRL["curves"] if c["label"] == label))


def ranks(anf):
    full = L.coeff_rank(anf)
    nonconst = L.coeff_rank({mk: c for mk, c in anf.items() if mk})
    return full, nonconst


labels = ["E0", "A000", "B000", "A010", "RD00", "RD01", "RD02", "RS00", "RS02", "RS05", "RS07", "RZz"]
out = {"labels": labels, "rows": []}
rng = random.Random(20260924 + 7)
r_list = [L.dec(rng.getrandbits(131)) for _ in range(3)]  # 3 fixed random target x's
t0 = time.time()
for m in (2, 3):
    for k in range(2, MAXK[m] + 1):
        for lab in labels:
            b = cb(lab)
            subs = [("poly", L.poly_basis(k))]
            if lab == "E0":
                c = L.dec(CTRL["scale_constants"][0])
                subs.append(("scaled0", [c * L.ZGEN**j for j in range(k)]))
                w = L.dec(CTRL["power_w"][0])
                subs.append(("powerw0", [w**j for j in range(k)]))
                if k <= 6:
                    subs.append(("rand0", [L.dec(u) for u in CTRL["random_bases"][0][:k]]))
            if lab in ("A000", "RD00") and k <= 131:
                subs.append(("powerb", [b**j for j in range(k)]))
            for sname, basis in subs:
                if m == 3 and sname != "poly" and k > 7:
                    continue
                if m == 3 and k > 7 and lab not in ("E0", "A000", "RD00", "RS00"):
                    continue
                res = []
                ts = time.time()
                for r in r_list:
                    anf = L.descended_anf(m, basis, b, r)
                    res.append(ranks(anf) + (len(anf),))
                row = {"m": m, "k": k, "label": lab, "sub": sname,
                       "rank_full": [x[0] for x in res], "rank_nonconst": [x[1] for x in res],
                       "monomials": res[0][2], "seconds": round(time.time() - ts, 2)}
                out["rows"].append(row)
                print(json.dumps(row), flush=True)
        (ROOT / "rank_scaling.json").write_text(json.dumps(out, indent=1))

# m = 4 via the reference implementation (S5 from the Sylvester resultant), polynomial basis
import descend as REF  # noqa: E402
import gf2n as RG  # noqa: E402
import sumpoly as RS  # noqa: E402

try:
    S5 = RS.load(5)
    F = RG.GF2n(131, L.ecc2k.MODULUS_INT)
    for k in (2, 3, 4):
        for lab in ("E0", "A000", "RD00", "RS00"):
            b = cb(lab)
            Er = RG.Curve(F, L.enc(b))
            res = []
            ts = time.time()
            for r in r_list[:2]:
                anf = {mk: v for mk, v in REF.descend(S5, F, Er, 4, k, L.enc(r)).items() if v}
                res.append(ranks(anf) + (len(anf),))
            row = {"m": 4, "k": k, "label": lab, "sub": "poly", "rank_full": [x[0] for x in res],
                   "rank_nonconst": [x[1] for x in res], "monomials": res[0][2],
                   "seconds": round(time.time() - ts, 2), "engine": "pdp-scaling/descend.py"}
            out["rows"].append(row)
            print(json.dumps(row), flush=True)
            (ROOT / "rank_scaling.json").write_text(json.dumps(out, indent=1))
except Exception as exc:  # noqa: BLE001
    out["m4_error"] = repr(exc)
out["seconds"] = time.time() - t0
(ROOT / "rank_scaling.json").write_text(json.dumps(out, indent=1))
print("done", out["seconds"])
