# Demonstration (sampled floor curves): the unique F_q-rational 263-isogeny psi: E_floor -> E0
# (kernel polynomial over F_q from the twist's rational 263-subgroup) composed with an F_q-isomorphism
# is injective on the order-N subgroup and carries tau's eigen-structure: tau(psi(P)) = [s] psi(P).
# So a floor-curve DLP Q=[k]P maps to the E0 DLP psi(Q)=[k]psi(P), where negation+tau classes apply.
# Toy k only; the Certicom challenge points are NOT used.
from sage.all import *
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
set_random_seed(7)
K = ecc2k.field(); q = Integer(ecc2k.q); t = Integer(ecc2k.t); N = Integer(ecc2k.N)
s = Integer(ecc2k.TAU_EIGEN)
E0 = ecc2k.curve("E0")
out = {}
for lab in sys.argv[1:]:
    t0 = time.time()
    b = ecc2k.dec(ecc2k.RECORDS[lab]["b_int"])
    E = EllipticCurve(K, [1, 0, 0, 0, b]); Et = EllipticCurve(K, [1, 1, 0, 0, b])
    cof = (q + 1 + t) // 263**2
    while True:
        G = 263 * (cof * Et.random_point())
        if not G.is_zero(): break
    assert (263 * G).is_zero()
    X = PolynomialRing(K, 'X').gen()
    ker = prod(X - (i*G)[0] for i in range(1, 132))       # x-coords shared by E and its twist
    psi = E.isogeny(ker)
    E1 = psi.codomain()
    iso = E1.isomorphism_to(E0)                          # exists over F_q iff E1 is not the twist
    P = 4 * E.random_point()
    assert not P.is_zero() and (N * P).is_zero()
    k = ZZ.random_element(2**40)
    Q = k * P
    P0 = iso(psi(P)); Q0 = iso(psi(Q))
    tauP0 = E0(P0[0]**2, P0[1]**2)
    out[lab] = {"psi_degree": int(psi.degree()), "codomain_j": str(ecc2k.enc(E1.j_invariant())),
                "codomain_F_q_isomorphic_to_E0": True,
                "psi(P)!=O": bool(not P0.is_zero()), "N*psi(P)==O": bool((N*P0).is_zero()),
                "psi([k]P)==[k]psi(P) (toy k < 2^40)": bool(Q0 == k*P0),
                "tau(psi(P))==[s]psi(P)": bool(tauP0 == s*P0),
                "tau(P)_on_same_curve": bool(E.is_on_curve(P[0]**2, P[1]**2)),
                "time_s": float("%.1f" % (time.time() - t0))}
    print(lab, out[lab], flush=True)
json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/transfer_demo.json", "w"), indent=1)
