"""Red team 0, real-curve checks.   sage -python rt0_checks.py  -> rt0_checks.json

C1  The cheapest (CVP-min-norm) endomorphism of E0 acting as a primitive cube root of unity
    on E0(F_q)[N]: evaluate it on a real point by its tau-adic NAF (Frobenius free), count the
    additions, confirm alpha(P) == [zeta3]P, zeta3^3 == 1, and time it against one addition.
C2  Low-weight tau-adic representation MITM: minimal typical weight w of k in
    {sum_{i<131} c_i tau^i, c_i in {0,+-1}} and the size of the Coppersmith rotation-split lists.
C3  Twist transport: floor twist A000' = [1,1,0,0,b] -> E0' = [1,1,0,0,1] by the Velu isogeny
    of its F_q-rational 263-subgroup; codomain is E0' (not E0); P114-part maps injectively;
    tau' acts on the image as the order-131 eigenvalue.
"""
import json, math, sys, time, random
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import EllipticCurve, Integer, binomial, log, RR, set_random_seed, primitive_root

set_random_seed(20260924)
random.seed(20260924)
N, t, q = ecc2k.N, ecc2k.t, ecc2k.q
lam = ecc2k.TAU_EIGEN
K, curves = ecc2k.load(["E0", "A000"])
E0 = curves["E0"]
out = {}

prev = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/redteam-0/rt0_endos.json"))
rec3 = [r for r in prev["S2"] if r["r"] == 3][0]["cond1"]
a, b = int(rec3["a"]), int(rec3["b"])
zeta = (a + b * lam) % N
assert pow(zeta, 3, N) == 1 and zeta != 1


def tnaf_digits(a, b):
    mu = -1
    r0, r1 = a, b
    d = []
    while r0 != 0 or r1 != 0:
        if r0 % 2 != 0:
            u = 2 - ((r0 - 2 * r1) % 4)
            r0 -= u
        else:
            u = 0
        d.append(u)
        r0, r1 = r1 + mu * (r0 // 2), -(r0 // 2)
    return d


def frob(P):
    return P.curve()(P[0] ** 2, P[1] ** 2) if not P.is_zero() else P


digs = tnaf_digits(a, b)
P = 4 * E0.random_point()
while P.is_zero():
    P = 4 * E0.random_point()
assert (N * P).is_zero()
# Horner: alpha(P) = sum u_i tau^i P  ->  Q = u_{L-1}P; Q = tau(Q) + u_i P
adds = 0
Q = E0(0)
for u in reversed(digs):
    Q = frob(Q)
    if u == 1:
        Q = Q + P; adds += 1
    elif u == -1:
        Q = Q - P; adds += 1
ok = (Q == zeta * P)
# timing: one addition vs the alpha evaluation (Sage-level, indicative only)
R1 = 4 * E0.random_point()
t0 = time.process_time()
for _ in range(2000):
    R1 = R1 + P
t_add = (time.process_time() - t0) / 2000
t0 = time.process_time()
for _ in range(50):
    Q2 = E0(0)
    for u in reversed(digs):
        Q2 = frob(Q2)
        if u:
            Q2 = Q2 + P if u == 1 else Q2 - P
t_alpha = (time.process_time() - t0) / 50
out["C1"] = dict(a=str(a), b=str(b), norm_log2=float(RR(a * a - a * b + 2 * b * b).log(2)),
                 tnaf_len=len(digs), tnaf_additions=adds, alpha_P_equals_zeta3_P=bool(ok),
                 zeta3=str(zeta), sage_cpu_add_us=t_add * 1e6, sage_cpu_alpha_us=t_alpha * 1e6,
                 ratio=t_alpha / t_add,
                 breakeven_ratio_for_class_x3=1 / (math.sqrt(3) + 1),
                 net_gain_x3_measured_cost=math.sqrt(3) / (1 + 2 * t_alpha / t_add))
print("C1", out["C1"])
assert ok

# ---------------------------------------------------------------- C2
logN = float(RR(N).log(2))
wmin = None
for w in range(1, 132):
    cnt = binomial(131, w) * 2 ** w
    if float(RR(cnt).log(2)) >= logN:
        wmin = w
        break
rows = []
for w in (wmin, wmin + 2, wmin + 4):
    half = binomial(65, w // 2) * 2 ** (w // 2)
    rows.append(dict(w=w, log2_count_weight_w=float(RR(binomial(131, w) * 2 ** w).log(2)),
                     log2_half_list=float(RR(half).log(2)),
                     log2_time_with_131_rotations=float(RR(131 * half).log(2)),
                     log2_generic_floor_sqrt_classes=0.5 * (logN - math.log2(262))))
out["C2"] = dict(w_min_typical=wmin, rows=rows)
print("C2", out["C2"])

# ---------------------------------------------------------------- C3
b0 = curves["A000"].a6()
Et = EllipticCurve(K, [1, 1, 0, 0, b0])
E0t = EllipticCurve(K, [1, 1, 0, 0, 1])
tw = q + 1 + t
P114 = tw // (2 * 263 ** 2)
cof = tw // 263 ** 2
T = None
for _ in range(20):
    X = cof * Et.random_point()
    if not (263 * X).is_zero():
        T = 263 * X  # order 263, F_q-rational
        break
assert T is not None and (263 * T).is_zero() and not T.is_zero()
t0 = time.process_time()
phi = Et.isogeny(T)
t_build = time.process_time() - t0
C = phi.codomain()
jC = C.j_invariant()
iso_to_E0t = C.is_isomorphic(E0t)
iso_to_E0 = C.is_isomorphic(E0)
# P114 point
Y = (2 * 263 ** 2) * Et.random_point()
while Y.is_zero():
    Y = (2 * 263 ** 2) * Et.random_point()
assert (P114 * Y).is_zero()
iso = C.isomorphism_to(E0t)
Z = iso(phi(Y))
kk = random.randrange(1, P114)
Z2 = iso(phi(kk * Y))
lin_ok = (Z2 == kk * Z) and not Z.is_zero() and (P114 * Z).is_zero()
# tau' eigenvalue of order 131 on E0t P114-part
e131 = int(prev["S7"]["frobenius_eig"])
tau_ok = (E0t(Z[0] ** 2, Z[1] ** 2) == e131 * Z)
out["C3"] = dict(floor="A000", codomain_j_is_1=bool(jC == 1), codomain_iso_E0twist=bool(iso_to_E0t),
                 codomain_iso_E0=bool(iso_to_E0), P114_linear_transport=bool(lin_ok),
                 tau_twist_acts_as_order131_eig=bool(tau_ok), build_cpu_s=t_build)
print("C3", out["C3"])
json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/redteam-0/rt0_checks.json", "w"), indent=1)
print("done")
