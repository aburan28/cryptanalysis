"""Second opinion with Sage / PARI for all 263 curves (sage -python sage_crosscheck.py).

 - Sage default E.cardinality() (dispatch: 'subfield' when j lies in a proper subfield, i.e. E0,
   else PARI ellcard); records which path was taken.
 - PARI via gp strings (curves built from the integer bitmasks inside gp, not via Sage or the
   ground-truth loader): ellcard, ellgroup (group structure) for E and for its quadratic twist
   [1, a2+1, 0, 0, b].
Writes raw/sage_crosscheck.json.
"""
import json
import time

from sage.all import pari, EllipticCurve, GF, PolynomialRing, version

GT = "/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json"
OUT = "/Volumes/SSD990/ecdlp-hardness-work/group-order/raw/sage_crosscheck.json"

gt = json.load(open(GT))
N = int(gt["meta"]["N"])
q = 2 ** 131
t = int(gt["meta"]["t"])
P114 = 19678316408850118605767852657510239

pari.allocatemem(2 * 10**9)
pari("zz = ffgen(Mod(1,2)*(x^131+x^13+x^2+x+1), 'zz)")
pari("tofq(n) = subst(Pol(binary(n)), x, zz) + 0*zz")

zpol = PolynomialRing(GF(2), "z").gen()
K = GF(2 ** 131, name="z", modulus=zpol ** 131 + zpol ** 13 + zpol ** 2 + zpol + 1)

res = {}
t0 = time.time()
for c in gt["curves"]:
    lab, a2, b = c["label"], int(c["a2"]), int(c["b_int"])
    r = {}
    # --- Sage default dispatch ---
    E = EllipticCurve(K, [1, a2, 0, 0, K.from_integer(b)])
    jpol = E.j_invariant().minimal_polynomial()
    r["sage_algorithm"] = "subfield" if jpol.degree() < 131 else "pari"
    r["sage_card"] = str(E.cardinality())
    # --- PARI directly ---
    pari("Eg = ellinit([1, %d, 0, 0, tofq(%d)])" % (a2, b))
    pari("Et = ellinit([1, %d, 0, 0, tofq(%d)])" % (a2 + 1, b))
    r["pari_j_matches"] = bool(pari("Eg.j == 1/tofq(%d)" % b))
    card = int(pari("ellcard(Eg)"))
    grp = [int(v) for v in pari("ellgroup(Eg)")]
    tcard = int(pari("ellcard(Et)"))
    tgrp = [int(v) for v in pari("ellgroup(Et)")]
    r["pari_card"] = str(card)
    r["pari_group"] = [str(v) for v in grp]
    r["pari_twist_card"] = str(tcard)
    r["pari_twist_group"] = [str(v) for v in tgrp]
    r["order_ok"] = (card == 4 * N == int(r["sage_card"]))
    r["cyclic_Z4N"] = (grp == [4 * N])
    r["twist_order_ok"] = (tcard == q + 1 + t)
    if tgrp == [q + 1 + t]:
        r["twist_structure"] = "cyclic Z/(2*263^2*P114)"
    elif tgrp == [(q + 1 + t) // 263, 263]:
        r["twist_structure"] = "Z/263 x Z/(2*263*P114)"
    else:
        r["twist_structure"] = "other: %s" % tgrp
    res[lab] = r
    if len(res) % 50 == 0:
        print(len(res), "done", round(time.time() - t0, 1), flush=True)

meta = {"sage_version": version(), "pari_version": str(pari.version()), "seconds": round(time.time() - t0, 1)}
json.dump({"meta": meta, "curves": res}, open(OUT, "w"), indent=1)
bad = [l for l, r in res.items() if not (r["order_ok"] and r["cyclic_Z4N"] and r["twist_order_ok"] and r["pari_j_matches"])]
from collections import Counter
print("bad", bad)
print("sage algorithms", Counter(r["sage_algorithm"] for r in res.values()))
print("twist structures", Counter(r["twist_structure"] for r in res.values()))
print("time", meta["seconds"])
