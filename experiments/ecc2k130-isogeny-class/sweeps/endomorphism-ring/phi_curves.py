# Criterion C4: number of F_q-rational 263-isogenies from each curve, read off from the
# classical modular polynomial Phi_263(X,Y) mod 2 (phi263_mod2.json, from PARI polmodular(263)).
# For each curve: g(Y) = Phi_263(j, Y) in F_q[Y] (degree 264); number of distinct F_q-roots
# = deg gcd(Y^q - Y, g); which roots; multiplicity of the root Y = 1.
# usage: sage -python phi_curves.py WORKER NWORKERS
from sage.all import *
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
W, NW = int(sys.argv[1]), int(sys.argv[2])
OUT = "/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/phi_roots_%d_of_%d.json" % (W, NW)
K = ecc2k.field()
phi = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/phi263_mod2.json"))
byb = {}
for (a_, b_) in phi["odd_terms_xy"]: byb.setdefault(b_, []).append(a_)
RY = PolynomialRing(K, 'Y'); Y = RY.gen()
labels = ecc2k.LABELS[W::NW]
floor_js = set(int(ecc2k.RECORDS[l]["j_int"]) for l in ecc2k.LABELS if l != "E0")
res = {}
for lab in labels:
    t0 = time.time()
    j = 1/ecc2k.dec(ecc2k.RECORDS[lab]["b_int"])
    pw = [K(1)]
    for _ in range(264): pw.append(pw[-1]*j)
    g = RY({b_: sum(pw[a_] for a_ in al) for b_, al in byb.items()})
    assert g.degree() == 264
    gp = g.__pari__(); v = gp.variable()
    Yq = (pari.Mod(v, gp) ** (2**131)).lift()
    d = pari.gcd(Yq - v, gp)
    d = RY(d.Vec().Vecrev().list()[::1]) if False else RY([K(c) for c in d.Vecrev()])
    d = d.monic()
    nroots = d.degree()
    roots = sorted(int(ecc2k.enc(r)) for r, _ in d.roots())
    mult1 = 0; gg = g
    while gg(K(1)) == 0:
        mult1 += 1; gg = gg // (Y + 1)
    r = {"num_distinct_Fq_roots": int(nroots), "mult_of_root_Y=1": int(mult1),
         "num_Fq_roots_with_mult": int(nroots - (1 if mult1 else 0) + mult1)}
    if lab == "E0":
        r["Fq_roots_are_1_and_exactly_the_262_floor_j"] = bool(set(roots) == floor_js | {1})
    else:
        r["Fq_roots"] = [str(x) for x in roots]
        r["only_Fq_root_is_j=1"] = bool(roots == [1])
    r["time_s"] = float("%.2f" % (time.time() - t0))
    res[lab] = r
    print(lab, json.dumps(r)[:200], flush=True)
    json.dump(res, open(OUT, "w"), indent=1)
print("done", len(res))
