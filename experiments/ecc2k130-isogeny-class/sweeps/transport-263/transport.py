"""
transport-263: explicit ascending 263-isogeny  phi : E -> E0  for every floor curve E
of the ECC2K-130 263-volcano, with planted-scalar verification.

Run (one shard of the 262 floor curves):
    export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
    sage -python transport.py SHARD NSHARDS [--no-sage]

Writes raw/shard_<SHARD>of<NSHARDS>.json   (per-curve records)
       raw/kernels_<SHARD>of<NSHARDS>.json (ascending-kernel x-coordinates, hex, per curve)

Math (all over F_q = F_2[z]/(z^131+z^13+z^2+z+1), q = 2^131):
  E  : y^2 + xy = x^3 + b        (a2 = 0, #E(F_q) = 4N, 263 does not divide 4N)
  E' : y^2 + xy = x^3 + x^2 + b  (quadratic twist, #E'(F_q) = q+1+t, v_263 = 2)
  E ~ E' over F_{q^2} by (x,y) -> (x, y + s x), s^2+s+1 = 0, which keeps x.
  pi acts on E[263] with char poly (X+1)^2 mod 263; its (-1)-eigenlines are the
  F_q-rational (Galois-stable) 263-subgroups of E and are the images of E'(F_q)[263].
  If E'(F_q)[263^oo] is cyclic (= Z/263^2) there is exactly one: the ascending kernel.
  Velu in char 2 for y^2+xy = x^3+a2x^2+a6, odd kernel G, S = (G\\O)/+-:
     X = x + sum_Q [ x_Q/(x+x_Q) + x_Q^2/(x+x_Q)^2 ]
     Y = y + sum_Q [ x_Q^2 x/(x+x_Q)^3 + x_Q (x + y + x_Q^2)/(x+x_Q)^2 ]
     codomain [1, a2, 0, v, a6 + v],  v = sum_Q x_Q
  (only the x_Q in F_q enter; y_Q and a2 drop out), so phi is F_q-rational even though
  the kernel points of E are not. j(codomain) = 1/(a6 + v + v^2); if that is 1 then
  (X, Y) -> (X, Y + v) is an F_q-isomorphism onto E0 : y^2 + xy = x^3 + 1.
"""
import sys, os, json, time, random, hashlib

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import EllipticCurve, PolynomialRing, GF, prod, set_random_seed
from sage.groups.generic import bsgs

HERE = os.path.dirname(os.path.abspath(__file__))
N, q, t = ecc2k.N, ecc2k.q, ecc2k.t
CARD, TW = ecc2k.CARD, ecc2k.TWIST_CARD
L = 263
assert TW % (L * L) == 0 and (TW // (L * L)) % L != 0 and CARD % L != 0
COF_TW = TW // (L * L)          # cofactor of the 263^2-part of E'(F_q)
SEED = 20260923


# --------------------------------------------------------------------- op counter
class Ops:
    def __init__(self):
        self.M = self.S = self.I = self.A = 0

    def d(self):
        return {"M": self.M, "S": self.S, "I": self.I, "A": self.A}


# --------------------------------------------------------------------- affine char-2 arithmetic
# curve y^2 + xy = x^3 + a2 x^2 + b ; points are tuples (x, y) or None for O
def padd(P, Q, a2, ops):
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if y1 + y2 == x2:          # Q = -P  ((x, x + y) is -P)
            return None
        return pdbl(P, a2, ops)
    lam = (y1 + y2) * (x1 + x2) ** -1; ops.I += 1; ops.M += 1; ops.A += 2
    x3 = lam * lam + lam + x1 + x2 + a2; ops.S += 1; ops.A += 4
    y3 = lam * (x1 + x3) + x3 + y1; ops.M += 1; ops.A += 3
    return (x3, y3)


def pdbl(P, a2, ops):
    if P is None:
        return None
    x1, y1 = P
    if x1 == 0:
        return None
    lam = x1 + y1 * x1 ** -1; ops.I += 1; ops.M += 1; ops.A += 1
    x3 = lam * lam + lam + a2; ops.S += 1; ops.A += 2
    y3 = x1 * x1 + (lam + 1) * x3; ops.S += 1; ops.M += 1; ops.A += 2
    return (x3, y3)


def pmul(k, P, a2, ops):
    """left-to-right double-and-add"""
    R = None
    for bit in bin(k)[2:]:
        R = pdbl(R, a2, ops)
        if bit == "1":
            R = padd(R, P, a2, ops)
    return R


def trace(c):
    s, u = c, c
    for _ in range(130):
        u = u * u
        s += u
    return s


def half_trace(c):
    """h with h^2 + h = c, valid when Tr(c) = 0 and n = 131 odd"""
    s, u = c, c
    for _ in range(65):
        u = (u * u) * (u * u)
        s += u
    return s


def random_affine_point(K, a2, b, rng, ops):
    """uniform-ish random point of y^2+xy = x^3+a2x^2+b via half-trace (counted)"""
    while True:
        x = K.from_integer(rng.getrandbits(131))
        if x == 0:
            continue
        # y = x z, z^2 + z = x + a2 + b/x^2
        ix = x ** -1; ops.I += 1
        c = x + a2 + b * ix * ix; ops.M += 1; ops.S += 1; ops.A += 2
        ops.S += 130; ops.A += 130               # trace
        if trace(c) != 0:
            continue
        z = half_trace(c); ops.S += 130; ops.A += 65
        if rng.getrandbits(1):
            z += 1
        return (x, x * z)


# --------------------------------------------------------------------- explicit Velu (char 2)
def velu_eval(xs, sqs, v, x, y, ops):
    """phi(x, y) followed by (X, Y) -> (X, Y + v); requires x != x_Q for all Q"""
    m = len(xs)
    d = [x + xq for xq in xs]; ops.A += m
    pref = [None] * m
    acc = d[0]
    pref[0] = acc
    for i in range(1, m):
        acc = acc * d[i]; ops.M += 1
        pref[i] = acc
    inv = acc ** -1; ops.I += 1
    e = [None] * m
    for i in range(m - 1, 0, -1):
        e[i] = inv * pref[i - 1]; ops.M += 1
        inv = inv * d[i]; ops.M += 1
    e[0] = inv
    X, Y = x, y
    xy = x + y; ops.A += 1
    for i in range(m):
        a = xs[i] * e[i]; ops.M += 1                   # x_Q/(x+x_Q)
        X += a + a * a; ops.S += 1; ops.A += 2           # x_Q e + x_Q^2 e^2
        ae = a * e[i]; ops.M += 1                       # x_Q e^2
        inner = a * x + xy + sqs[i]; ops.M += 1; ops.A += 2
        Y += ae * inner; ops.M += 1; ops.A += 1        # x_Q^2 x e^3 + x_Q (x+y+x_Q^2) e^2
    return (X, Y + v)


def kernel_from_generator(P, a2, ops):
    """x-coordinates of <P>\\O modulo +-, P of order 263, via 130 counted additions"""
    xs, R = [], P
    for i in range(131):
        xs.append(R[0])
        if i < 130:
            R = padd(R, P, a2, ops)
    return xs


def to_sage(E, P):
    return E(0) if P is None else E(P[0], P[1])


def xs_digest(xs):
    h = hashlib.sha256()
    for n in sorted(int(u.to_integer()) for u in xs):
        h.update(n.to_bytes(17, "big"))
    return h.hexdigest()


# --------------------------------------------------------------------- F_{q^2} set-up
def setup_fq2(K):
    K2 = GF(2 ** 262, "w")
    zpol = PolynomialRing(GF(2), "Z")([int(c) for c in K.modulus().list()])
    r = sorted(zpol.change_ring(K2).roots(multiplicities=False), key=lambda u: u.to_integer())[0]
    pw = [K2(1)]
    for _ in range(130):
        pw.append(pw[-1] * r)

    def emb(u):
        n, s, i = int(u.to_integer()), K2(0), 0
        while n:
            if n & 1:
                s += pw[i]
            n >>= 1
            i += 1
        return s

    rng = random.Random(1)
    for _ in range(20):
        a, c = K.from_integer(rng.getrandbits(131)), K.from_integer(rng.getrandbits(131))
        assert emb(a * c) == emb(a) * emb(c) and emb(a + c) == emb(a) + emb(c)
    return K2, emb


# --------------------------------------------------------------------- E0 side: all 264 kernels
DESC = {}


def precompute_E0_kernels(K):
    """all 264 cyclic subgroups of E0'(F_q)[263] = (Z/263)^2, E0' = [1,1,0,0,1]; returns
    dict  int(1+v+v^2) -> list of (index, xs, sqs, v)  (codomain of E0 by that kernel is [1,0,0,0,1+v+v^2])"""
    set_random_seed(SEED)
    one = K(1)
    E0t = EllipticCurve(K, [1, 1, 0, 0, 1])
    E0t.set_order(TW)
    cof = TW // (L * L)
    ops = Ops()
    while True:
        T1 = cof * E0t.random_point()
        if not T1.is_zero():
            break
    assert (L * T1).is_zero()
    x1 = set(kernel_from_generator((T1[0], T1[1]), one, ops))
    while True:
        T2 = cof * E0t.random_point()
        if not T2.is_zero() and T2[0] not in x1:
            break
    assert (L * T2).is_zero()
    gens = [("inf", T1)] + [(i, T2 + i * T1) for i in range(L)]
    out, seen = {}, set()
    for idx, G in gens:
        xs = kernel_from_generator((G[0], G[1]), one, ops)
        fs = frozenset(xs)
        assert len(fs) == 131 and fs not in seen
        seen.add(fs)
        v = sum(xs)
        key = int((1 + v + v * v).to_integer())
        out.setdefault(key, []).append((idx, xs, [u * u for u in xs], v))
    assert len(seen) == 264
    assert len(out.get(1, [])) == 2                     # the two horizontal (tau-eigen) kernels back to E0
    assert len(out) == 263 and all(len(val) == 1 for kk, val in out.items() if kk != 1)
    return out


# --------------------------------------------------------------------- per curve
def run_curve(label, K, E0, K2, emb, use_sage=True):
    rec = {"label": label}
    r = ecc2k.RECORDS[label]
    rec["orbit"], rec["frob_index"] = r["orbit"], r["frob_index"]
    b = K.from_integer(int(r["b_int"]))
    assert int(r["a2"]) == 0
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    Et = EllipticCurve(K, [1, 1, 0, 0, b])
    E.set_order(CARD)
    Et.set_order(TW)
    rng = random.Random("transport-263:%s:%d" % (label, SEED))
    set_random_seed(int(hashlib.sha256(("sage:%s:%d" % (label, SEED)).encode()).hexdigest()[:15], 16))
    one = K(1)

    # ---------------- 1. BUILD (explicit pipeline, op-counted): ascending kernel from the twist
    ob = Ops()
    c0, w0 = time.process_time(), time.time()
    tries = 0
    while True:
        tries += 1
        U = random_affine_point(K, one, b, rng, ob)
        Qt = pmul(COF_TW, U, one, ob)               # in E'(F_q)[263^oo]
        Pt = pmul(L, Qt, one, ob)
        if Pt is not None:
            break
    xs = kernel_from_generator(Pt, one, ob)
    sqs = [u * u for u in xs]; ob.S += 131
    v = sum(xs); ob.A += 130
    build_cpu, build_wall = time.process_time() - c0, time.time() - w0
    rec["build_ops"] = ob.d()
    rec["build_tries"] = tries
    rec["build_seconds"] = round(build_cpu, 4)
    rec["build_wall_seconds"] = round(build_wall, 4)

    # checks on the kernel
    QtS, PtS = to_sage(Et, Qt), to_sage(Et, Pt)
    rec["twist_Q_order_263sq"] = bool((L * L * QtS).is_zero() and not (L * QtS).is_zero())
    rec["twist_263_sylow_cyclic"] = rec["twist_Q_order_263sq"]  # |Sylow| = 263^2 (v_263(q+1+t)=2) and has elt of order 263^2
    rec["kernel_gen_order_263"] = bool((L * PtS).is_zero() and not PtS.is_zero())
    rec["kernel_gen_matches_sage_mult"] = bool(PtS == L * (COF_TW * to_sage(Et, U)))
    rec["kernel_xs_distinct_131"] = len(set(xs)) == 131 and all(u != 0 for u in xs)
    # kernel points on E itself are NOT F_q-rational: y^2+xy = x^3+b solvable iff Tr((x^3+b)/x^2) = 0
    rec["kernel_pts_not_Fq_rational_on_E"] = all(trace(u + b / (u * u)) == 1 for u in xs)
    rec["E_Fq_has_no_263_torsion"] = CARD % L != 0
    rec["v_int"] = str(int(v.to_integer()))
    rec["kernel_xs_sha256"] = xs_digest(xs)
    rec["kernel_sq_xs_sha256"] = xs_digest(sqs)      # = kernel_xs_sha256 of frobenius_next(label) expected
    # codomain via explicit Velu: [1, 0, 0, v, b + v] with j = 1/(b + v + v^2)
    rec["codomain_j_is_1"] = bool(b + v + v * v == 1)

    # ---------------- 2. F_{q^2} derivation (literal: 263-Sylow of E(F_{q^2}))
    c2 = time.process_time()
    E2 = EllipticCurve(K2, [1, 0, 0, 0, emb(b)])
    cof2 = CARD * TW // (L * L)
    while True:
        Q2 = cof2 * E2.random_point()
        if not (L * Q2).is_zero():
            break
    P2 = L * Q2
    fr = lambda Pp: E2(Pp[0] ** (2 ** 131), Pp[1] ** (2 ** 131))
    xs2, R2 = [], P2
    for i in range(131):
        xs2.append(R2[0])
        R2 = R2 + P2
    RX2 = PolynomialRing(K2, "X")
    h2 = prod([RX2.gen() - u for u in xs2])
    RX = PolynomialRing(K, "X")
    h = prod([RX.gen() - u for u in xs])
    rec["fq2_sylow_cyclic_order_263sq"] = bool((L * L * Q2).is_zero())
    rec["fq2_kernel_galois_stable_frob_eq_minus"] = bool(fr(P2) == -P2)
    rec["fq2_kernel_y_not_in_Fq"] = bool(P2[1] ** (2 ** 131) != P2[1])
    rec["fq2_kernel_x_in_Fq"] = all(u ** (2 ** 131) == u for u in xs2)
    rec["fq2_kernel_poly_equals_twist_kernel_poly"] = bool(h2 == RX2([emb(c) for c in h.list()]))
    rec["fq2_seconds"] = round(time.process_time() - c2, 4)
    rec["kernel_poly_degree"] = int(h.degree())

    # ---------------- 3. Sage library isogeny from the kernel polynomial (cross-check)
    if use_sage:
        cs_, ws_ = time.process_time(), time.time()
        phiS = E.isogeny(h)
        C = phiS.codomain()
        iso = C.isomorphism_to(E0)
        rec["sage_build_seconds"] = round(time.process_time() - cs_, 3)
        rec["sage_build_wall_seconds"] = round(time.time() - ws_, 3)
        rec["sage_degree"] = int(phiS.degree())
        rec["sage_codomain_j_is_1"] = bool(C.j_invariant() == 1)
        rec["sage_codomain_a1a2a3a4a6"] = [str(int(c.to_integer())) for c in C.a_invariants()]
        rec["sage_codomain_equals_explicit"] = list(C.a_invariants()) == [1, 0, 0, v, b + v]
        urst = iso.tuple() if hasattr(iso, "tuple") else None
        rec["sage_iso_urst_is_1_0_0_v"] = bool(urst is not None and tuple(urst) == (1, 0, 0, v))

    # ---------------- 4. PLANTED SCALAR on the N-subgroup
    while True:
        R = 4 * E.random_point()
        if not R.is_zero():
            break
    assert (N * R).is_zero()
    k = rng.randrange(2, N - 1)
    S = k * R
    rec["planted_k"] = str(k)
    oe = Ops()
    ce, we = time.process_time(), time.time()
    phR = velu_eval(xs, sqs, v, R[0], R[1], oe)
    eval_cpu1, eval_wall1 = time.process_time() - ce, time.time() - we
    ops_one = oe.d()
    ce, we = time.process_time(), time.time()
    phS = velu_eval(xs, sqs, v, S[0], S[1], Ops())
    eval_cpu2, eval_wall2 = time.process_time() - ce, time.time() - we
    phR, phS = E0(phR[0], phR[1]), E0(phS[0], phS[1])  # constructor checks the point is on E0
    rec["eval_ops_per_point"] = ops_one
    rec["eval_seconds"] = round((eval_cpu1 + eval_cpu2) / 2, 5)
    rec["eval_wall_seconds"] = round((eval_wall1 + eval_wall2) / 2, 5)
    rec["phiR_nonzero"] = not phR.is_zero()
    rec["phiR_order_N"] = bool((N * phR).is_zero() and not phR.is_zero())   # N prime
    rec["phiS_eq_k_phiR"] = bool(phS == k * phR)
    if use_sage:
        ce = time.process_time()
        sR = iso(phiS(R))
        sS = iso(phiS(S))
        rec["sage_eval_seconds"] = round((time.process_time() - ce) / 2, 5)
        rec["sage_agrees_explicit"] = bool(sR == phR and sS == phS)
    rec["planted_check_ok"] = bool(rec["phiR_nonzero"] and rec["phiR_order_N"] and rec["phiS_eq_k_phiR"]
                                   and rec.get("sage_agrees_explicit", True))

    # ---------------- 5. homomorphism on the full group E(F_q) (order 4N)
    hom_ok, ord_ok = True, True
    for _ in range(3):
        Ua, Ub = E.random_point(), E.random_point()
        f = lambda P: E0(0) if P.is_zero() else E0(*velu_eval(xs, sqs, v, P[0], P[1], Ops()))
        hom_ok &= f(Ua + Ub) == f(Ua) + f(Ub)
        if not (2 * N * Ua).is_zero() and not (4 * Ua).is_zero():   # Ua of exact order 4N
            fu = f(Ua)
            ord_ok &= bool((4 * N * fu).is_zero() and not (2 * N * fu).is_zero() and not (4 * fu).is_zero())
    rec["hom_full_group_ok"] = bool(hom_ok)
    rec["order_4N_preserved"] = bool(ord_ok)

    # ---------------- 6. toy end-to-end DLP: planted small k on E, solved on E0 after transport
    ks = rng.randrange(0, 2 ** 24)
    Ss = ks * R
    phSs = E0(*velu_eval(xs, sqs, v, Ss[0], Ss[1], Ops())) if not Ss.is_zero() else E0(0)
    ct = time.process_time()
    krec = bsgs(phR, phSs, (0, 2 ** 24 - 1), operation="+")
    rec["toy_dlp_k_small"] = ks
    rec["toy_dlp_recovered_on_E0"] = int(krec) == ks
    rec["toy_dlp_seconds"] = round(time.process_time() - ct, 3)

    # ---------------- 7. dual (descending) isogeny psi : E0 -> E ; psi o phi = +-[263]
    # E0'(F_q)[263] = (Z/263)^2, so all 264 kernels from E0 have x-coords in F_q (precomputed per process
    # in DESC). Exactly one of them must give the codomain [1,0,0,vd,1+vd] ~ [1,0,0,0,1+vd+vd^2] = E.
    matches = DESC.get(int(b.to_integer()), [])
    rec["dual_n_E0_kernels_reaching_E"] = len(matches)
    rec["dual_codomain_j_eq_jE"] = len(matches) == 1
    if len(matches) == 1:
        idx, xsd, sqd, vd = matches[0]
        rec["dual_kernel_index"] = str(idx)
        back = velu_eval(xsd, sqd, vd, phR[0], phR[1], Ops())
        backE = E(back[0], back[1])
        rec["dual_psi_phi_R_eq"] = "+263R" if backE == L * R else ("-263R" if backE == -(L * R) else "FAIL")
    else:
        rec["dual_psi_phi_R_eq"] = "FAIL"
    rec["dual_ok"] = bool(rec["dual_codomain_j_eq_jE"] and rec["dual_psi_phi_R_eq"] != "FAIL")

    kernel_ok = all(rec[kk] for kk in [
        "twist_Q_order_263sq", "kernel_gen_order_263", "kernel_gen_matches_sage_mult", "kernel_xs_distinct_131",
        "kernel_pts_not_Fq_rational_on_E", "E_Fq_has_no_263_torsion", "fq2_sylow_cyclic_order_263sq",
        "fq2_kernel_galois_stable_frob_eq_minus", "fq2_kernel_y_not_in_Fq", "fq2_kernel_x_in_Fq",
        "fq2_kernel_poly_equals_twist_kernel_poly"])
    rec["kernel_ok"] = bool(kernel_ok and rec["kernel_poly_degree"] == 131)
    sage_ok = (not use_sage) or all(rec[kk] for kk in ["sage_codomain_j_is_1", "sage_codomain_equals_explicit",
                                                      "sage_iso_urst_is_1_0_0_v"]) and rec["sage_degree"] == L
    rec["transport_ok"] = bool(rec["kernel_ok"] and rec["codomain_j_is_1"] and sage_ok and rec["planted_check_ok"]
                               and rec["hom_full_group_ok"] and rec["order_4N_preserved"]
                               and rec["toy_dlp_recovered_on_E0"] and rec["dual_ok"])
    return rec, [format(int(u.to_integer()), "x") for u in xs]


def main():
    shard, nsh = int(sys.argv[1]), int(sys.argv[2])
    use_sage = "--no-sage" not in sys.argv
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--labels=")]
    K = ecc2k.field()
    E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
    E0.set_order(CARD)
    K2, emb = setup_fq2(K)
    global DESC
    DESC = precompute_E0_kernels(K)
    floor = [lab for lab in ecc2k.LABELS if lab != "E0"]
    assert len(floor) == 262
    mine = only[0].split(",") if only else floor[shard::nsh]
    tags = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--tag=")]
    tag = "%dof%d" % (shard, nsh) if not only else (tags[0] if tags else "labels")
    out_rec = os.path.join(HERE, "raw", "shard_%s.json" % tag)
    out_ker = os.path.join(HERE, "raw", "kernels_%s.json" % tag)
    recs, kers = {}, {}
    T0 = time.time()
    for i, lab in enumerate(mine):
        rec, kx = run_curve(lab, K, E0, K2, emb, use_sage)
        recs[lab], kers[lab] = rec, kx
        print("[%s %d/%d %.0fs] %s transport_ok=%s j1=%s planted=%s build=%.3fs sage=%s eval=%.4fs dual=%s"
              % (tag, i + 1, len(mine), time.time() - T0, lab, rec["transport_ok"], rec["codomain_j_is_1"],
                 rec["planted_check_ok"], rec["build_seconds"], rec.get("sage_build_seconds"),
                 rec["eval_seconds"], rec["dual_psi_phi_R_eq"]), flush=True)
        with open(out_rec + ".part", "w") as fh:
            json.dump(recs, fh, indent=1)
        with open(out_ker + ".part", "w") as fh:
            json.dump(kers, fh)
    os.replace(out_rec + ".part", out_rec)
    os.replace(out_ker + ".part", out_ker)
    print("done", tag, len(recs), "curves in %.1fs" % (time.time() - T0))


if __name__ == "__main__":
    main()
