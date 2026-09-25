"""(5, caveat) One-time isogeny transfer floor curve -> E0.
For a floor curve E (a2=0, b), the twist E' = [1,1,0,0,b] has cyclic 263-part Z/263^2, so its unique
F_q-rational subgroup of order 263 is <K1>.  x-coordinates are shared by E and E', so
prod_{i=1..131}(X - x([i]K1)) is an F_q-rational kernel polynomial on E (the ascending isogeny).
We build phi: E -> C, check C ~= E0 over F_q, transfer a toy DLP instance Q = [k]P (k chosen by us) and check
phi(Q) = [k]phi(P) with phi(P) of order N, and tau(phi(P)) = [lambda]phi(P).
Usage: sage -python transfer_demo.py LABEL [LABEL ...]  -> transfer_<LABEL>.json
"""
import sys, json, time, random
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import ecc2k
import common_rho as C
from sage.all import EllipticCurve, PolynomialRing, set_random_seed

N, q, t, LAM = C.N, C.q, C.t, C.LAM
TW = q + 1 + t
assert TW % 263 ** 2 == 0 and (TW // 263 ** 2) % 263 != 0
set_random_seed(20260923)
rng = random.Random(20260923)
for lab in sys.argv[1:]:
    rec = {"label": lab}
    t0 = time.time()
    K, cs = ecc2k.load([lab, "E0"])
    E, E0 = cs[lab], cs["E0"]
    b = E.a6()
    Et = EllipticCurve(K, [1, 1, 0, 0, b])
    assert Et.cardinality(extension_degree=1) if False else True
    while True:
        R1 = (TW // 263 ** 2) * Et.random_point()
        if not (263 * R1).is_zero():
            break
    K1 = 263 * R1
    assert not K1.is_zero() and (263 * K1).is_zero()
    Rx = PolynomialRing(K, "X"); X = Rx.gen()
    ker = Rx(1); Pi = K1
    for i in range(1, 132):
        ker *= (X - Pi[0]); Pi = Pi + K1
    rec["kernel_poly_degree"] = ker.degree()
    t1 = time.time()
    phi = E.isogeny(ker)
    Cc = phi.codomain()
    rec["build_seconds"] = round(time.time() - t1, 1)
    rec["codomain_j_is_1"] = Cc.j_invariant() == 1
    iso = Cc.isomorphism_to(E0)            # raises if only the twist
    rec["codomain_Fq_isomorphic_to_E0"] = True
    while True:
        P = 4 * E.random_point()
        if not P.is_zero():
            break
    assert (N * P).is_zero()
    k = rng.randrange(1, N)
    Q = k * P
    t2 = time.time()
    fP = iso(phi(P)); fQ = iso(phi(Q))
    rec["eval_seconds_two_points"] = round(time.time() - t2, 2)
    rec["phi(P)!=O and N*phi(P)=O"] = (not fP.is_zero()) and (N * fP).is_zero()
    rec["phi(Q) == [k]phi(P)"] = fQ == k * fP
    rec["tau(phi(P)) == [lambda]phi(P)"] = E0(fP[0] ** 2, fP[1] ** 2) == LAM * fP
    rec["total_seconds"] = round(time.time() - t0, 1)
    print(rec, flush=True)
    json.dump(rec, open("transfer_%s.json" % lab, "w"), indent=1, default=str)
