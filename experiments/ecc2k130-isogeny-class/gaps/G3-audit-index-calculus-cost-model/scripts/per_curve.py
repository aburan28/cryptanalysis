"""Per-curve facts that the index-calculus cost model depends on, for all 263 curves
(sage -python per_curve.py OUT.json).  For every curve E = [1, a2, 0, 0, b] from the ground truth:
  * #E(F_q) = 4N (ground-truth PARI count, re-checked: a random point P has [4N]P = O, [4]P != O,
    [N]([4]P) = O), so the relation probability p = |F|^m/(m! #E) is the same for every curve;
  * Tr(a2) = 0 and the E/2E criterion "P in 2E iff Tr(x(P)) = 0" holds on 16 random points
    (P in 2E tested as [2N]P = O, since E(F_q) = Z/4 x Z/N): this is what makes the
    V subset ker(Tr) factor base put every factor-base point in 2E (the +1 bit for G-targets);
  * whether x -> x^2 is an endomorphism (a2, b in F_2): only then GGMP Sec 3.1 ordered tau-slots and
    the tau-union are available natively; the floor curves reach them only through the 263-isogeny
    to E0 (transfer).
"""
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
from sage.all import *
import ecc2k

t0 = time.time()
K, curves = ecc2k.load()
gt = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json"))
rec = {c["label"]: c for c in gt["curves"]}
N = Integer(ecc2k.N)
set_random_seed(20260924)
out = {}
for label, E in curves.items():
    a1, a2, a3, a4, a6 = E.a_invariants()
    ok_order = Integer(rec[label]["order_pari"]) == 4 * N
    # re-check the order with a random point
    P = E.random_point()
    while (4 * P).is_zero():
        P = E.random_point()
    ok_pt = (4 * N * P).is_zero() and (N * (4 * P)).is_zero()
    trA2 = (K(a2)).trace()
    crit = 0
    for _ in range(16):
        Q = E.random_point()
        if Q.is_zero() or Q[0] == 0:
            continue
        in2E = (2 * N * Q).is_zero()
        crit += int(in2E == (K(Q[0]).trace() == 0))
    frob_endo = (K(a2).polynomial().degree() <= 0) and (K(a6).polynomial().degree() <= 0)
    out[label] = dict(order_is_4N_groundtruth=bool(ok_order), order_point_recheck=bool(ok_pt),
                      a2=int(K(a2).polynomial().change_ring(ZZ)(2)), Tr_a2=int(trA2),
                      E2E_trace_criterion_holds=f"{crit}/16", tau_endomorphism_native=bool(frob_endo),
                      level=rec[label]["level"])
    print(label, out[label], flush=True)
json.dump(dict(curves=out, seconds=time.time() - t0), open(sys.argv[1], "w"), indent=1)
print("done", time.time() - t0)
