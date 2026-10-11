"""G2 items (7b) and (8).

(7b) Halving criterion on 50 random curves y^2 + xy = x^3 + b over F_{2^131} (a2 = 0):
     8 | #E  <=>  Tr(b) = 0.  Tr(b) from own f2lin; #E from PARI ellcard as the control.
     Plus 20 random curves with a2 = 1 as a control of 4 | #E <=> Tr(a2) = 0.
     Plus a direct halving test with own arithmetic: the order-4 points have x = b^(1/4);
     such a point is rational iff Tr(a2) = 0 and is halvable iff Tr(b^(1/4)) = Tr(a2).
(8)  E0: 5 random points P of order N (own arithmetic, then Sage as a second implementation):
     sum_{i<131} pi_2^i(P) = O, with pi_2 (x,y) -> (x^2,y^2); also pi_2(P) = [s]P.

Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 sage -python halving_and_trace.py
"""
import sys, json, time, random
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
sys.path.insert(0, OUT)
import ecc2k
import f2lin as F
from sage.all import EllipticCurve, pari

T0 = time.time()
K = ecc2k.field()
N, s = ecc2k.N, ecc2k.TAU_EIGEN
rng = random.Random(202609248)
res = {}

# ------------------------------------------------------------------ (7b)
rows = []
for i in range(70):
    a2 = 0 if i < 50 else 1
    b = rng.getrandbits(131)
    if b == 0:
        continue
    E = EllipticCurve(K, [1, a2, 0, 0, K.from_integer(b)])
    card = int(pari(E).ellcard())          # PARI control
    trb = F.ftrace(b)
    x4 = F.fsqrt(F.fsqrt(b))                # x-coordinate of the order-4 points
    # point with x = x4 exists over F_q iff Tr(x4 + a2 + b/x4^2) = 0
    c = x4 ^ a2 ^ F.fmul(b, F.finv(F.fsqr(x4)))
    has_order4 = F.ftrace(c) == 0
    halvable = has_order4 and (F.ftrace(x4) == F.ftrace(a2))
    if has_order4:
        w = F.half_trace(c)
        P4 = (x4, F.fmul(x4, w))
        assert F.ec_on(P4, a2, b)
        P2 = F.ec_dbl(P4, a2, b)
        assert P2 is not None and P2[0] == 0 and F.ec_dbl(P2, a2, b) is None   # exact order 4
    row = {"a2": a2, "b_int": str(b), "trace_b": trb, "card_pari": str(card), "card_mod_8": card % 8,
           "own_order4_point_exists": has_order4, "own_order4_halvable": halvable}
    if a2 == 0:
        row["criterion_8|#E_iff_Tr(b)=0"] = ((card % 8 == 0) == (trb == 0))
        row["direct_halving_consistent"] = ((card % 8 == 0) == halvable) and has_order4 == (card % 4 == 0)
    else:
        row["criterion_4|#E_iff_Tr(a2)=0"] = ((card % 4 == 0) == (F.ftrace(a2) == 0))
        row["direct_halving_consistent"] = (has_order4 == (card % 4 == 0))
    rows.append(row)
a0 = [r for r in rows if r["a2"] == 0]
a1 = [r for r in rows if r["a2"] == 1]
res["7b_random_curves"] = {
    "a2=0_curves": len(a0),
    "a2=0_trace_b_split": {"Tr=0": sum(r["trace_b"] == 0 for r in a0), "Tr=1": sum(r["trace_b"] == 1 for r in a0)},
    "a2=0_card_mod_8_histogram": {str(k): sum(r["card_mod_8"] == k for r in a0) for k in range(8)},
    "a2=0_criterion_holds_all": all(r["criterion_8|#E_iff_Tr(b)=0"] for r in a0),
    "a2=0_direct_halving_consistent_all": all(r["direct_halving_consistent"] for r in a0),
    "a2=1_curves": len(a1),
    "a2=1_card_mod_4_histogram": {str(k): sum(int(r["card_pari"]) % 4 == k for r in a1) for k in range(4)},
    "a2=1_criterion_holds_all": all(r["criterion_4|#E_iff_Tr(a2)=0"] for r in a1),
    "a2=1_direct_consistent_all": all(r["direct_halving_consistent"] for r in a1),
}
res["7b_rows"] = rows

# ------------------------------------------------------------------ (8)
assert (s * s + s + 2) % N == 0
geo = sum(pow(s, i, N) for i in range(131)) % N
res["8_scalar"] = {"sum_{i<131} s^i mod N": geo, "s^131 mod N": pow(s, 131, N), "s mod N != 1": s % N != 1}
own = []
E0s = EllipticCurve(K, [1, 0, 0, 0, 1])
for i in range(5):
    P = F.ec_random_point(0, 1, rng)
    P = F.ec_mul(4, P, 0, 1)
    assert P is not None and F.ec_mul(N, P, 0, 1) is None          # order exactly N (N prime)
    S = None
    Q = P
    for _ in range(131):
        S = F.ec_add(S, Q, 0, 1)
        Q = F.ec_frob(Q)
    assert Q == P                                                  # pi_2^131 = pi = id on E0(F_q)
    frob_is_s = F.ec_frob(P) == F.ec_mul(s, P, 0, 1)
    # partial sums S_k for k = 1..130 are nonzero (sum_{i<k} s^i != 0 mod N for k < 131)
    partial_scalars_nonzero = all(sum(pow(s, i, N) for i in range(k)) % N != 0 for k in (1, 2, 65, 130))
    # Sage second implementation on the same point
    Ps = E0s(K.from_integer(P[0]), K.from_integer(P[1]))
    Ss = E0s(0)
    Qs = Ps
    for _ in range(131):
        Ss += Qs
        Qs = E0s(Qs[0] ** 2, Qs[1] ** 2)
    own.append({"P_x": str(P[0]), "order_N": True, "trace_sum_is_O_own": S is None,
                "trace_sum_is_O_sage": Ss.is_zero(), "pi2(P)==[s]P": frob_is_s,
                "sage_N*P==O": (N * Ps).is_zero(), "partial_scalar_sums_nonzero(k=1,2,65,130)": partial_scalars_nonzero})
res["8_E0_points"] = own
res["8_all_ok"] = geo == 0 and all(r["trace_sum_is_O_own"] and r["trace_sum_is_O_sage"] and r["pi2(P)==[s]P"]
                                   and r["sage_N*P==O"] for r in own)
res["8_E0_F2_points"] = int(pari(EllipticCurve(__import__('sage.all', fromlist=['GF']).GF(2), [1, 0, 0, 0, 1])).ellcard())
res["elapsed_s"] = round(time.time() - T0, 1)
json.dump(res, open(f"{OUT}/halving_and_trace.json", "w"), indent=1)
out = {k: v for k, v in res.items() if k != "7b_rows"}
print(json.dumps(out, indent=1))
