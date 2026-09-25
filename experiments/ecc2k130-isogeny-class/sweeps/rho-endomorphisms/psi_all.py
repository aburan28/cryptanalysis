"""Verify on points, for a slice of floor curves, that psi = iso o I_11 o Frob^16 (I_11 the F_q-rational
11-isogeny E^(2^16) -> E) acts on the N-subgroup as +-(774 + omega_263), i.e. as +-ev with
ev = 774 + 263*lambda + 132 mod N.   Usage: sage -python psi_all.py SLICE NSLICES -> psi_all_<SLICE>.json"""
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import ecc2k
import common_rho as C
from sage.all import set_random_seed
sl, ns = int(sys.argv[1]), int(sys.argv[2])
N = C.N
EV = (774 + C.W_O263) % N
labs = [l for l in ecc2k.LABELS if l != "E0"][sl::ns]
set_random_seed(1000 + sl)
K, cs = ecc2k.load()
res = {}
for lab in labs:
    t0 = time.time()
    E = cs[lab]
    E16 = cs["%s%03d" % (lab[0], (int(lab[1:]) + 16) % 131)]
    assert E16.a6() == E.a6() ** (2 ** 16)
    Is = E16.isogenies_prime_degree(11)
    back = [I for I in Is if I.codomain().j_invariant() == E.j_invariant()]
    I = back[0]
    iso = I.codomain().isomorphism_to(E)
    signs = []
    for _ in range(3):
        while True:
            P = 4 * E.random_point()
            if not P.is_zero():
                break
        Q = iso(I(E16(P[0] ** (2 ** 16), P[1] ** (2 ** 16))))
        signs.append(1 if Q == EV * P else (-1 if Q == (N - EV) * P else 0))
    res[lab] = {"n_rational_11_isog": len(Is), "n_back": len(back), "signs": signs,
                "ok": len(back) == 1 and 0 not in signs and len(set(signs)) == 1, "sec": round(time.time() - t0, 1)}
json.dump(res, open("psi_all_%d.json" % sl, "w"), indent=0)
print(sl, "done", sum(r["ok"] for r in res.values()), "/", len(res))
