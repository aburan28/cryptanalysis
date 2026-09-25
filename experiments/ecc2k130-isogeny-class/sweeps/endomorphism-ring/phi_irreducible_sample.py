# For sampled floor curves: h(Y) = Phi_263(j,Y)/(Y+1) mod 2 is irreducible of degree 263 over F_q
# (Rabin test for prime degree n=263: Y^(q^263) == Y mod h and gcd(Y^q - Y, h) = 1).
# Prediction from the volcano: pi acts on E[263] as a non-scalar Jordan block, so the 263
# non-rational 263-subgroups form one Galois orbit of length 263.
# usage: sage -python phi_irreducible_sample.py LABEL [LABEL ...]
from sage.all import *
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
K = ecc2k.field()
phi = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/phi263_mod2.json"))
byb = {}
for (a_, b_) in phi["odd_terms_xy"]: byb.setdefault(b_, []).append(a_)
RY = PolynomialRing(K, 'Y'); Y = RY.gen()
out = {}
for lab in sys.argv[1:]:
    t0 = time.time()
    j = 1/ecc2k.dec(ecc2k.RECORDS[lab]["b_int"])
    pw = [K(1)]
    for _ in range(264): pw.append(pw[-1]*j)
    g = RY({b_: sum(pw[a_] for a_ in al) for b_, al in byb.items()})
    h, rem = g.quo_rem(Y + 1)
    assert rem == 0 and h.degree() == 263
    hp = h.__pari__(); v = hp.variable()
    F1 = (pari.Mod(v, hp) ** (2**131))              # sigma(Y) = Y^q mod h
    gcd1 = pari.gcd(F1.lift() - v, hp)
    def comp(Fa, Fb):                               # sigma^{a+b}(Y) = Fa(Fb) mod h
        return pari.subst(Fa.lift(), v, Fb)
    pows = {1: F1}
    k = 1
    while 2*k <= 263:
        pows[2*k] = comp(pows[k], pows[k]); k *= 2
    acc = None; tot = 0
    for bit in [256, 128, 64, 32, 16, 8, 4, 2, 1]:
        if 263 & bit:
            acc = pows[bit] if acc is None else comp(acc, pows[bit]); tot += bit
    assert tot == 263
    Fn = acc.lift()
    ok = bool(Fn == v)
    # also: no smaller Frobenius period divides (263 prime, so only degree 1 matters)
    out[lab] = {"deg_h": 263, "gcd(Y^q-Y,h)_degree": int(gcd1.poldegree()) if gcd1.type() == 't_POL' else 0,
                "Y^(q^263)==Y mod h": ok,
                "irreducible_deg263": bool(ok and (gcd1.type() != 't_POL' or gcd1.poldegree() == 0)),
                "time_s": float("%.1f" % (time.time() - t0))}
    print(lab, out[lab], flush=True)
    json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/phi_irreducible_%s.json" % "_".join(sys.argv[1:]), "w"), indent=1)
