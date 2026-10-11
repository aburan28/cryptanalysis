# Per-curve endomorphism-ring / volcano-level certification for all 263 curves
# (E0 + 262 floor curves) of the ECC2K-130 isogeny class.
#
# Criteria computed per curve (see report.md for the logic):
#  C1  CM / class polynomial: H_D(j) = 0 mod 2 for D = -7*263^2 (H_D recomputed with PARI polclass),
#      j != 1 (the root of H_{-7} = X + 3375 = X + 1 mod 2).
#  C2  263-Sylow of E(F_{q^2}): (a) PARI ellcard + ellgroup over GF(2^262);
#      (b) own affine arithmetic: random points times cofactor, order 263^2 found (cyclic) or
#          two independent points of order 263 (Z/263)^2, with Weil pairing check.
#  C3  explicit F_q-rational 263-isogeny back to j = 1 (hand Velu on the unique F_q-rational
#      263-subgroup of the quadratic twist) -> p-part of the conductor equals E0's (= 0),
#      263-part differs by at most 1.
#  C4  modular polynomial: factorisation pattern of Phi_263(j, Y) mod 2 over F_q
#      (floor: (Y+1) * irreducible of degree 263; crater E0: splits completely, (Y+1)^2 * H_D).
#  plus: #E(F_q) = 4N by own arithmetic, degree of j over F_2 (minpoly), Frobenius orbits.
from sage.all import *
import sys, json, time, hashlib, random
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k

OUTDIR = "/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/"
T0 = time.time()
rng = random.Random(20260923)
set_random_seed(20260923)
LOG = []
def log(msg, **kw):
    kw["msg"] = msg; kw["t"] = round(time.time() - T0, 1)
    LOG.append(kw); print(json.dumps(kw, default=str), flush=True)

K = ecc2k.field(); z = K.gen()
q = Integer(ecc2k.q); t = Integer(ecc2k.t); N = Integer(ecc2k.N); p = Integer(ecc2k.p)
n1 = q + 1 - t; n1tw = q + 1 + t
assert n1 == 4*N
n2 = n1 * n1tw                       # #E(F_{q^2}) for every curve with trace t over F_q
t2 = t*t - 2*q
assert n2 == q*q + 1 - t2
assert n2 % 263**2 == 0 and (n2 // 263**2) % 263 != 0
log("constants", n2=str(n2), v263_n1=int(valuation(n1, 263)), v263_n1tw=int(valuation(n1tw, 263)))

# ---------------- own affine arithmetic on y^2 + xy = x^3 + a2 x^2 + b (char 2) -------------
def add(P, Q, a2):
    if P is None: return Q
    if Q is None: return P
    x1, y1 = P; x2, y2 = Q
    if x1 == x2:
        if y1 + y2 == x2:        # Q = -P  (-(x,y) = (x, x+y))
            return None
        # doubling
        if x1 == 0: return None
        lam = x1 + y1/x1
        x3 = lam*lam + lam + a2
        y3 = x1*x1 + (lam + 1)*x3
        return (x3, y3)
    lam = (y1 + y2)/(x1 + x2)
    x3 = lam*lam + lam + x1 + x2 + a2
    y3 = lam*(x1 + x3) + x3 + y1
    return (x3, y3)

def mul(n, P, a2):
    n = Integer(n)
    if n < 0: n = -n; P = (P[0], P[0] + P[1]) if P is not None else None
    R = None
    for bit in n.bits()[::-1]:
        R = add(R, R, a2)
        if bit: R = add(R, P, a2)
    return R

def on_curve(P, a2, b):
    x, y = P
    return y*y + x*y == x**3 + a2*x*x + b

# solving z^2 + z = c: odd degree -> half trace; even degree -> precomputed F_2 linear solve
def half_trace(c, n):
    s = c; h = c
    for _ in range((n - 1)//2):
        s = s**4; h += s
    return h

def make_AS_solver(L, n):
    # matrix of z -> z^2 + z over F_2 in the polynomial basis (bit i = w^i)
    cols = []
    for i in range(n):
        e = L.from_integer(1 << i)
        v = (e*e + e).to_integer()
        cols.append([(v >> k) & 1 for k in range(n)])
    M = matrix(GF(2), cols).transpose()
    assert M.rank() == n - 1
    def solve(c):
        v = c.to_integer()
        rhs = vector(GF(2), [(v >> k) & 1 for k in range(n)])
        sol = M.solve_right(rhs)
        zz = L.from_integer(sum(int(sol[k]) << k for k in range(n)))
        assert zz*zz + zz == c
        return zz
    return solve

def random_point(L, n, a2, b, solver):
    while True:
        x = L.random_element()
        if x == 0: continue
        c = x + a2 + b/(x*x)
        if c.trace() != 0: continue
        zz = solver(c) if solver else half_trace(c, n)
        P = (x, x*zz)
        assert on_curve(P, a2, b)
        return P

# ---------------- load curves --------------------------------------------------------------
LABELS = ecc2k.LABELS
REC = ecc2k.RECORDS
B = {lab: ecc2k.dec(REC[lab]["b_int"]) for lab in LABELS}
A2 = {lab: int(REC[lab]["a2"]) for lab in LABELS}
J = {lab: 1/B[lab] for lab in LABELS}
for lab in LABELS:
    assert ecc2k.enc(J[lab]) == int(REC[lab]["j_int"]), lab
    assert A2[lab] == 0
floor = [l for l in LABELS if l != "E0"]
log("loaded", curves=len(LABELS), floor=len(floor))

res = {lab: {"label": lab, "orbit": REC[lab]["orbit"], "frob_index": REC[lab]["frob_index"]} for lab in LABELS}

# ---------------- (a) #E(F_q) = 4N by own arithmetic ----------------------------------------
for lab in LABELS:
    a2, b = K(A2[lab]), B[lab]
    tries = 0
    while True:
        tries += 1
        P = random_point(K, 131, a2, b, None)
        Q = mul(4, P, a2)
        if Q is not None: break
    assert mul(N, Q, a2) is None
    # order exactly 4N? ([2N]P != O means 4 | ord since ord | 4N and N prime, [4]P != O)
    res[lab]["card_Fq_own_arith"] = "4N (random point: [4]P != O, [N][4]P = O; 4N unique multiple of N in Hasse interval)"
log("orders over F_q checked by own arithmetic", n=len(LABELS))

# ---------------- E0: tau is an endomorphism with tau^2 + tau + 2 = 0 -----------------------
def tau(P): return None if P is None else (P[0]**2, P[1]**2)
a2 = K(0); b = B["E0"]
for _ in range(20):
    P = random_point(K, 131, a2, b, None)
    lhs = add(add(tau(tau(P)), tau(P), a2), mul(2, P, a2), a2)
    assert lhs is None
# on the twist too (tau maps the twist over F_2, x^2+x+1-coefficient... twist [1,1,0,0,1] is also over F_2)
for _ in range(20):
    P = random_point(K, 131, K(1), b, None)
    # twist E0' over F_2 has #E0'(F_2) = 2+1+1 = ... compute its F_2 trace by brute force
tw_cnt = 1 + sum(1 for x in GF(2) for y in GF(2) if y*y + x*y == x**3 + x**2 + 1)
t1tw = 3 - tw_cnt
for _ in range(20):
    P = random_point(K, 131, K(1), b, None)
    lhs = add(add(tau(tau(P)), mul(-t1tw, tau(P), K(1)), K(1)), mul(2, P, K(1)), K(1))
    assert lhs is None
s = Integer(ecc2k.TAU_EIGEN)
for _ in range(5):
    P = mul(4, random_point(K, 131, a2, b, None), a2)
    if P is None: continue
    assert tau(P) == mul(s, P, a2)
log("E0: tau^2 + tau + 2 = 0 on 20 random points of E0(F_q); twist E0' over F_2 has trace %d and tau^2 - (%d) tau + 2 = 0 on 20 points; tau acts as s on the N-subgroup" % (t1tw, t1tw))

# ---------------- (b) degree over F_2, orbits, H_D ------------------------------------------
t1 = time.time()
HD = pari.polclass(-484183)
coeffs = [Integer(HD.polcoef(i)) for i in range(int(HD.poldegree()) + 1)]
hexfile = open("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/class_polynomial_D-484183.hex").read().split()
hex_match = [Integer(h, 16) for h in hexfile] == coeffs
log("H_D recomputed with PARI polclass", degree=len(coeffs) - 1, time=round(time.time() - t1, 1),
    equals_ground_truth_hex_file=hex_match)
R2 = PolynomialRing(GF(2), 'X'); X = R2.gen()
HD2 = R2(coeffs)
assert HD2.degree() == 262 and gcd(HD2, HD2.derivative()) == 1
minpolys = {}
for lab in LABELS:
    j = J[lab]
    mp = j.minpoly()
    minpolys[lab] = mp
    res[lab]["j_degree_over_F2"] = int(mp.degree())
    res[lab]["j_in_F2"] = bool(j**2 == j)
    res[lab]["HD_mod2_at_j_is_zero"] = bool(HD2(j) == 0)
    res[lab]["H_minus7_mod2_at_j_is_zero(j==1)"] = bool(j == 1)
distinct = {}
for lab in floor:
    distinct.setdefault(str(minpolys[lab]), []).append(lab)
orbit_ok = True
for lab in floor:
    nxt = ecc2k.frobenius_next(lab)
    if J[nxt] != J[lab]**2: orbit_ok = False
groups = sorted(sorted(v) for v in distinct.values())
log("minpolys", distinct_minpolys_on_floor=len(distinct),
    group_sizes=[len(g) for g in groups],
    groups_are_label_orbits=[set(l[0] for l in g) for g in groups],
    frob_next_is_squaring_for_all=orbit_ok,
    product_of_two_minpolys_equals_HD_mod2=bool(prod(R2(k.list()) for k in [minpolys[groups[0][0]], minpolys[groups[1][0]]]) == HD2),
    all_floor_deg131=all(res[l]["j_degree_over_F2"] == 131 for l in floor),
    E0_j=str(J["E0"]))
for lab in floor:
    res[lab]["frobenius_orbit_size"] = len(distinct[str(minpolys[lab])])
res["E0"]["frobenius_orbit_size"] = 1

# ---------------- (c) Velu up: F_q-rational 263-subgroup of the twist -> j' ------------------
cof_tw = n1tw // 263**2
velu_times = []
for lab in LABELS:
    a2t, b = K(1), B[lab]              # quadratic twist (Tr(1) = 1 in F_{2^131})
    tries = 0
    while True:
        tries += 1
        P = random_point(K, 131, a2t, b, None)
        R = mul(cof_tw, P, a2t)
        if R is None: continue
        G = mul(263, R, a2t)
        if lab == "E0":
            assert G is None          # E0'(F_q)[263^inf] = (Z/263)^2: no point of order 263^2
            if tries < 30: continue   # sample 30 points, all killed by 263
            break
        if G is not None: break
        if tries > 50: raise Exception("no order-263^2 point on twist of " + lab)
    if lab == "E0":
        res[lab]["twist_Fq_random_points_all_killed_by_263"] = 30
        continue
    assert mul(263, G, a2t) is None
    t1 = time.time()
    pts = [G]
    for i in range(130): pts.append(add(pts[-1], G, a2t))
    v = sum(Pt[0] for Pt in pts)       # sum of x over half of the nonzero kernel points
    jprime = 1/(b + v + v*v)          # Velu codomain y^2+xy = x^3 + a2 x^2 + v x + (b+v)
    velu_times.append(time.time() - t1)
    res[lab]["velu_up_codomain_j"] = str(ecc2k.enc(jprime))
    res[lab]["velu_up_to_j1"] = bool(jprime == 1)
    res[lab]["twist_Fq_263_part"] = "Z/263^2 (point of order 263^2 found after %d tries)" % tries
log("Velu up done", all_to_j1=all(res[l]["velu_up_to_j1"] for l in floor),
    mean_time_s=round(sum(velu_times)/len(velu_times), 3))
# cross-check the hand Velu with Sage's isogeny on 8 curves
chk = []
for lab in ["A000", "A064", "A130", "B000", "B021", "B130", "A090", "B095"]:
    Et = EllipticCurve(K, [1, 1, 0, 0, B[lab]])
    while True:
        Pt = Et.random_point()
        Rt = cof_tw * Pt
        Gt = 263 * Rt
        if not Gt.is_zero(): break
    phi = Et.isogeny(Gt)
    chk.append((lab, bool(phi.codomain().j_invariant() == 1), int(phi.degree())))
log("Sage isogeny cross-check (twist kernel -> codomain j)", results=chk)

# ---------------- (d) F_{q^2}: PARI ellcard/ellgroup + own random-point Sylow -------------------
L = GF(2**262, 'w')
rL = K.modulus().change_ring(L).roots()[0][0]
emb = K.hom([rL], L)
for _ in range(10):
    u, w_ = K.random_element(), K.random_element()
    assert emb(u*w_) == emb(u)*emb(w_) and emb(u + w_) == emb(u) + emb(w_)
solver = make_AS_solver(L, 262)
log("F_{q^2} = GF(2^262)", modulus=str(L.modulus()))
cof2 = n2 // 263**2
for lab in LABELS:
    a2, b = L(0), emb(B[lab])
    EL = EllipticCurve(L, [1, 0, 0, 0, b])
    pe = EL.__pari__()
    c2 = Integer(pe.ellcard())
    grp = [Integer(d) for d in pe.ellgroup()]
    d263 = [int(valuation(d, 263)) for d in grp]
    syl_pari = "x".join("Z/263^%d" % e if e > 1 else "Z/263" for e in d263 if e > 0)
    res[lab]["card_Fq2_pari_equals_(q+1-t)(q+1+t)"] = bool(c2 == n2)
    res[lab]["ellgroup_Fq2_pari"] = [str(d) for d in grp]
    res[lab]["sylow263_pari"] = syl_pari
    # own arithmetic
    tries = 0; found = None; pts263 = []
    while tries < 40:
        tries += 1
        P = random_point(L, 262, a2, b, solver)
        assert mul(n2, P, a2) is None          # the group order kills the point
        Q = mul(cof2, P, a2)
        if Q is None: continue
        Q263 = mul(263, Q, a2)
        if Q263 is not None:
            assert mul(263, Q263, a2) is None
            found = "Z/263^2"; break
        pts263.append(Q)
        if lab != "E0" and tries >= 40: break
        if lab == "E0" and len(pts263) >= 12: break
    if found:
        res[lab]["sylow263_structure_q2"] = "Z/263^2 (cyclic)"
        res[lab]["sylow263_own_arith"] = "point of order 263^2 found after %d random points" % tries
    else:
        # all sampled points killed by 263: exhibit two independent points of order 263
        Q1 = pts263[0]
        multiples = set()
        Rm = None
        for i in range(263):
            multiples.add(Rm); Rm = add(Rm, Q1, a2)
        indep = [Qk for Qk in pts263[1:] if Qk not in multiples]
        # Weil pairing via Sage
        S1 = EL([Q1[0], Q1[1]]); S2 = EL([indep[0][0], indep[0][1]])
        wp = S1.weil_pairing(S2, 263)
        res[lab]["sylow263_structure_q2"] = "Z/263 x Z/263"
        res[lab]["sylow263_own_arith"] = ("%d random points: all of [cof]P killed by 263; %d of %d are outside <Q1>; "
                                          "Weil pairing e_263(Q1,Q2) != 1: %s, e^263 == 1: %s") % (
            len(pts263), len(indep), len(pts263) - 1, bool(wp != 1), bool(wp**263 == 1))
    agree = (res[lab]["sylow263_structure_q2"].startswith("Z/263^2") == (syl_pari == "Z/263^2"))
    res[lab]["sylow263_pari_and_own_agree"] = bool(agree)
log("F_{q^2} Sylow done",
    floor_cyclic=sum(1 for l in floor if res[l]["sylow263_structure_q2"].startswith("Z/263^2")),
    floor_pari_cyclic=sum(1 for l in floor if res[l]["sylow263_pari"] == "Z/263^2"),
    E0=res["E0"]["sylow263_structure_q2"], E0_pari=res["E0"]["sylow263_pari"],
    all_card_ok=all(res[l]["card_Fq2_pari_equals_(q+1-t)(q+1+t)"] for l in LABELS),
    all_agree=all(res[l]["sylow263_pari_and_own_agree"] for l in LABELS))

json.dump({lab: res[lab] for lab in LABELS}, open(OUTDIR + "per_curve_stage1.json", "w"), indent=1, default=str)
json.dump({"log": LOG}, open(OUTDIR + "per_curve_stage1_log.json", "w"), indent=1, default=str)
log("stage 1 written", runtime_s=round(time.time() - T0, 1), sage_version=version())
