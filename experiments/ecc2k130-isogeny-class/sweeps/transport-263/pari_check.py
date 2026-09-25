"""
Third, independent implementation check with PARI's ellisogeny (not Sage's EllipticCurveIsogeny, not our Velu):
for every floor curve, feed the stored ascending-kernel x-coordinates (kernels_all.json) to PARI as a kernel
polynomial, get the codomain and the rational maps (f/h^2, g/h^3), and check
  * codomain j = 1 and codomain == [1,0,0,v,b+v]  (what the explicit Velu formula predicts),
  * PARI's map composed with an F_q-isomorphism to E0 (found by Sage isomorphism_to) sends a fresh random R of
    order N (own seed) to a point of order N, agrees with transport.velu_eval at R and S = k R, and phi(S) = k phi(R).
Writes raw/pari_check_<i>of<n>.json.   Run: sage -python pari_check.py I NSHARDS
"""
import sys, os, json, time, random, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, HERE)
import ecc2k
import transport as T
from sage.all import pari, PolynomialRing, EllipticCurve, prod, set_random_seed

K = ecc2k.field()
N = ecc2k.N
E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
E0.set_order(ecc2k.CARD)
kers = json.load(open(os.path.join(HERE, "kernels_all.json")))
SH, NSH = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, 1)
labs = [lab for lab in ecc2k.LABELS if lab != "E0"][SH::NSH]
fn = os.path.join(HERE, "raw", "pari_check_%dof%d.json" % (SH, NSH))
RX = PolynomialRing(K, "x")
px, py = pari("x"), pari("y")
out = {}
for lab in labs:
    b = K.from_integer(int(ecc2k.RECORDS[lab]["b_int"]))
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    E.set_order(ecc2k.CARD)
    xs = [K.from_integer(int(u, 16)) for u in kers[lab]]
    sqs = [u * u for u in xs]
    v = sum(xs)
    h = prod([RX.gen() - u for u in xs])
    c = time.process_time()
    res = pari.ellisogeny(pari(E), pari(h))
    build = time.process_time() - c
    ainv = [K(res[0][i]) for i in range(5)]
    f, g, hh = res[1][0], res[1][1], res[1][2]
    C = EllipticCurve(K, ainv)
    iso = C.isomorphism_to(E0)
    set_random_seed(int(hashlib.sha256(("pari:" + lab).encode()).hexdigest()[:15], 16))
    rng = random.Random("pari:" + lab)
    R = 4 * E.random_point()
    k = rng.randrange(2, N - 1)
    S = k * R

    def pmap(P):
        xv, yv = pari(P[0]), pari(P[1])
        hv = pari.substvec(hh, [px], [xv])
        X = pari.substvec(f, [px], [xv]) / hv ** 2
        Y = pari.substvec(g, [px, py], [xv, yv]) / hv ** 3
        return iso(C(K(X), K(Y)))

    c = time.process_time()
    pR, pS = pmap(R), pmap(S)
    ev = (time.process_time() - c) / 2
    eR = E0(*T.velu_eval(xs, sqs, v, R[0], R[1], T.Ops()))
    eS = E0(*T.velu_eval(xs, sqs, v, S[0], S[1], T.Ops()))
    rec = {
        "pari_codomain_j_is_1": bool(C.j_invariant() == 1),
        "pari_codomain_equals_explicit": ainv == [1, 0, 0, v, b + v],
        "pari_R_order_N": bool(not R.is_zero() and (N * R).is_zero()),
        "pari_phiR_order_N": bool(not pR.is_zero() and (N * pR).is_zero()),
        "pari_phiS_eq_k_phiR": bool(pS == k * pR),
        "pari_agrees_explicit": "equal" if (pR == eR and pS == eS) else ("negated" if (pR == -eR and pS == -eS) else "DIFFERENT"),
        "pari_build_seconds": round(build, 4),
        "pari_eval_seconds": round(ev, 5),
    }
    rec["pari_ok"] = bool(rec["pari_codomain_j_is_1"] and rec["pari_codomain_equals_explicit"] and rec["pari_R_order_N"]
                          and rec["pari_phiR_order_N"] and rec["pari_phiS_eq_k_phiR"] and rec["pari_agrees_explicit"] != "DIFFERENT")
    out[lab] = rec
    print(lab, rec["pari_ok"], rec["pari_agrees_explicit"], rec["pari_build_seconds"], flush=True)
    json.dump(out, open(fn + ".part", "w"), indent=1)
os.replace(fn + ".part", fn)
print("pari_ok:", sum(r["pari_ok"] for r in out.values()), "/", len(out),
      "agree:", {s: sum(r["pari_agrees_explicit"] == s for r in out.values()) for s in ["equal", "negated", "DIFFERENT"]},
      "build s median:", sorted(r["pari_build_seconds"] for r in out.values())[len(out) // 2])
