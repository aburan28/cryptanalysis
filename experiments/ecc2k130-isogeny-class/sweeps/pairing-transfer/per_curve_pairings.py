# Pairing / transfer sweep, per-curve evaluation for all 263 curves (parts 1, 3, 4).
#   export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
#   sage -python per_curve_pairings.py [label ...]      (no labels = all 263)
# Writes per_curve.json (all labels) or per_curve_subset.json (when labels are given).
#
# For every curve E = [1,0,0,0,b] (ground-truth a2 = 0 model, #E(F_q) = 4N):
#  (1) N_E := order_pari/4; prove prime; factor N_E - 1 (PARI) and compute ord_{N_E}(q) three
#      ways (PARI znorder, factorisation descent in plain Python ints, Sage multiplicative_order);
#      check q^k = 1 and q^(k/r) != 1 for every prime r | k.  Point check: random P, Q = 4P != O,
#      N*Q = O (so the N-subgroup the ECDLP lives in really exists on this curve).
#  (3) twist order from ground truth; check [TW]R' = O for a random point of the twist
#      [1,1,0,0,b]; factor TW; embedding degree ord_r(q) of each odd prime factor r.
#  (4) over L = F_(q^2) = GF(2^262) (263 | q - 1, so mu_263 is already in F_q):
#      - determine E(L)[263^inf]: E0 -> (Z/263)^2 (two points with Weil pairing != 1),
#        floor -> cyclic Z/263^2 (a point of order 263^2; #E(L) has 263-valuation exactly 2);
#      - reduced Tate pairing t_263(P, Q_N) for P of order 263 and Q_N of order N (the ECDLP
#        subgroup, lifted from F_q): two implementations (PARI elltatepairing via Sage
#        tate_pairing, and Sage's own Miller loop P._miller_) -> must be 1;
#      - controls showing the pairing is NOT degenerate on the 263-part (so the "1" above is
#        not an artefact): floor: t_263(P, T) != 1 with T of order 263^2; E0: Weil
#        e_263(P1,P2) != 1 and the 2x2 Tate matrix on (P1,P2) has nonzero determinant mod 263;
#      - blindness: t_263(P, T + c*Q_N) = t_263(P, T) for random c, i.e. the pairing value
#        does not depend on the N-component at all.
import json, sys, time, random
from pathlib import Path
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import (Integer, GF, PolynomialRing, EllipticCurve, pari, Mod, gcd, factor,
                      set_random_seed, log, Zmod)

HERE = Path(__file__).resolve().parent
q = Integer(ecc2k.q); t = Integer(ecc2k.t); N = Integer(ecc2k.N)
CARD = Integer(ecc2k.CARD); TW = Integer(ecc2k.TWIST_CARD)
ELL = Integer(263)
QL = q * q                                  # |L| = 2^262
K = ecc2k.field()
L = GF(2**262, "w")
r_emb = K.modulus().change_ring(L).roots()[0][0]
phi = K.hom([r_emb], L)
# sanity of the embedding
for _ in range(5):
    a, b = K.random_element(), K.random_element()
    assert phi(a * b) == phi(a) * phi(b) and phi(a + b) == phi(a) + phi(b)
assert (QL - 1) % ELL == 0 and (q - 1) % ELL == 0
assert gcd(N, q - 1) == 1 and gcd(N, QL - 1) == 1     # mu_N not in F_q nor in F_(q^2)
CARD_L = CARD * TW                                    # #E(F_(q^2)) = (q+1-t)(q+1+t)
assert CARD_L == (q + 1)**2 - t**2
assert CARD_L.valuation(ELL) == 2
H263 = CARD_L // ELL**2
EXP_L = (QL - 1) // ELL

# factorisation of N-1 (reference, from embedding_degrees.json computed by embedding_degrees.py)
REF = json.loads((HERE / "embedding_degrees.json").read_text())
K_REF = Integer(REF["N"]["embedding_degree_k_ord_n_q"])
TW_REF = {r: v for r, v in REF["twist_factors"].items()}


def py_order(g, n, fac):
    g = int(g) % int(n); n = int(n); k = n - 1
    for (r, e) in fac:
        r = int(r)
        for _ in range(int(e)):
            if pow(g, k // r, n) == 1:
                k //= r
            else:
                break
    assert pow(g, k, n) == 1
    return k


def emb_degree(n):
    """(k, factorisation of n-1) with three-way cross-check; n must be prime."""
    n = Integer(n)
    fac = [(Integer(a), Integer(b)) for a, b in zip(*pari(n - 1).factor())]
    prod = 1
    for (r, e) in fac:
        prod *= r**e
        assert pari(r).isprime()
    assert prod == n - 1
    k1 = Integer(pari(f"znorder(Mod({q % n},{n}))"))
    k2 = Integer(py_order(q, n, fac))
    k3 = Mod(q, n).multiplicative_order()
    assert k1 == k2 == k3
    assert pow(q, k1, n) == 1
    for (r, e) in factor(k1):
        assert pow(q, k1 // r, n) != 1
    return k1, fac


def tate(P, Q):
    """reduced Tate pairing t_263(P,Q) over L, two implementations; returns (value, agree)."""
    v1 = P.tate_pairing(Q, ELL, 1, q=QL)             # PARI elltatepairing + final exp
    v2 = P._miller_(Q, ELL) ** EXP_L                 # Sage's own Miller loop
    return v1, bool(v1 == v2)


def tate_self(P, EL):
    """t_263(P,P) via a random offset: t(P,P+R)/t(P,R)."""
    while True:
        R = EL.random_point()
        try:
            a, ok1 = tate(P, P + R)
            b, ok2 = tate(P, R)
            return a / b, ok1 and ok2
        except (ZeroDivisionError, ValueError):
            continue


def mu_log(z, zeta):
    """discrete log of z in <zeta> (order 263), brute force."""
    x = L(1)
    for i in range(ELL):
        if x == z:
            return i
        x *= zeta
    raise ValueError("not in <zeta>")


# a fixed primitive 263rd root of unity in F_q (mu_263 subset F_q since 263 | q-1)
zeta = None
for c0 in range(2, 50):
    zz = phi(K.from_integer(c0)) ** EXP_L
    if zz != 1:
        zeta = zz; break
assert zeta**ELL == 1 and zeta != 1
# (2^262-1)/263 = (q+1)*(q-1)/263 and x^(q+1) = x^2 for x in F_q, so zeta = (x^2)^((q-1)/263) lies in F_q
assert phi(K.from_integer(c0) ** 2) ** ((q - 1) // ELL) == zeta


def do_curve(lab):
    t0 = time.time()
    rec = ecc2k.RECORDS[lab]
    idx = ecc2k.LABELS.index(lab)
    set_random_seed(20260923 + idx)
    b = ecc2k.dec(rec["b_int"])
    assert int(rec["a2"]) == 0
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    assert ecc2k.enc(E.j_invariant()) == int(rec["j_int"])
    out = {"orbit": rec["orbit"], "level": rec["level"]}

    # ---- (1) N-subgroup and its embedding degree
    card = Integer(rec["order_pari"])
    assert card == CARD and card % 4 == 0
    NE = card // 4
    assert pari(NE).isprime()
    kE, facE = emb_degree(NE)
    assert kE == K_REF
    while True:
        P = E.random_point(); Q = 4 * P
        if not Q.is_zero():
            break
    assert (NE * Q).is_zero()
    out["N"] = str(NE)
    out["embedding_degree_N"] = str(kE)
    out["embedding_degree_N_bits"] = int(kE.nbits())
    out["embedding_degree_N_log2"] = round(float(log(kE, 2).n(60)), 4)
    out["ord_N_2"] = str(Mod(2, NE).multiplicative_order())
    out["N_minus_1_factorization"] = "*".join(f"{r}^{e}" if e > 1 else f"{r}" for r, e in facE)
    out["N_subgroup_point_check"] = True

    # ---- (3) twist
    tw = Integer(rec["twist_order_pari"])
    assert tw == TW
    Et = EllipticCurve(K, [1, 1, 0, 0, b])
    Rt = Et.random_point()
    assert (tw * Rt).is_zero()
    twk = {}
    for (r, e) in factor(tw):
        if r == 2:
            twk["2"] = {"exp": int(e), "ord_r_q": None}
            continue
        kr = Mod(q, r).multiplicative_order()
        assert str(kr) == TW_REF[str(r)].get("embedding_degree_k_ord_n_q", TW_REF[str(r)].get("ord_r_q"))
        d = {"exp": int(e), "ord_r_q": str(kr)}
        if e > 1:
            d["ord_r^e_q"] = str(Mod(q, r**e).multiplicative_order())
        twk[str(r)] = d
    out["twist_order"] = str(tw)
    out["twist_prime_embedding_degrees"] = twk

    # ---- (4) 263-torsion pairings over L = F_(q^2)
    bL = phi(b)
    EL = EllipticCurve(L, [1, 0, 0, 0, bL])
    QN = EL(phi(Q[0]), phi(Q[1]))
    assert (NE * QN).is_zero() and not QN.is_zero()
    pr = {}
    if rec["orbit"] == "crater":
        # find a basis of E[263] inside E(L)
        pts = []
        while len(pts) < 2:
            T = H263 * EL.random_point()
            if T.is_zero():
                continue
            assert (ELL * T).is_zero()           # exponent-263 witness (structure proved below)
            if not pts:
                pts.append(T)
            else:
                w = pts[0].weil_pairing(T, ELL)
                if w != 1:
                    pts.append(T)
        P1, P2 = pts
        w12 = P1.weil_pairing(P2, ELL)
        assert w12 != 1 and w12**ELL == 1
        pr["structure_E(L)[263^inf]"] = "(Z/263)^2"
        pr["structure_proof"] = "v_263(#E(L))=2 and Weil e_263(P1,P2) != 1 => E[263] subset E(L), = the whole 263-part"
        pr["weil_e263(P1,P2)_log_zeta"] = mu_log(w12, zeta)
        # Tate matrix
        t11, ok11 = tate_self(P1, EL)
        t22, ok22 = tate_self(P2, EL)
        t12, ok12 = tate(P1, P2)
        t21, ok21 = tate(P2, P1)
        M = [[mu_log(t11, zeta), mu_log(t12, zeta)], [mu_log(t21, zeta), mu_log(t22, zeta)]]
        det = (M[0][0] * M[1][1] - M[0][1] * M[1][0]) % ELL
        assert det != 0 and ok11 and ok22 and ok12 and ok21
        pr["tate_matrix_logs_mod_263"] = M
        pr["tate_matrix_det_mod_263"] = int(det)
        Ptors, Tgen = P1, P2
        ctrl, okc = t12, ok12
    else:
        tries = 0
        while True:
            tries += 1
            T = H263 * EL.random_point()
            if not (ELL * T).is_zero():
                break
            assert tries < 20
        assert (ELL**2 * T).is_zero()
        Ptors = ELL * T
        assert not Ptors.is_zero()
        pr["structure_E(L)[263^inf]"] = "Z/263^2 (cyclic)"
        pr["structure_proof"] = "v_263(#E(L))=2 and a point T of exact order 263^2 exists"
        ctrl, okc = tate(Ptors, T)
        assert ctrl != 1 and okc
        Tgen = T
        pr["tate_self_t263(263T,T)_log_zeta"] = mu_log(ctrl, zeta)
    # the pairing with the ECDLP subgroup
    tN, okN = tate(Ptors, QN)
    assert okN
    pr["tate_t263(P,Q_N)"] = "1" if tN == 1 else "NOT 1"
    assert tN == 1
    c = Integer(random.Random(idx).randrange(1, int(NE)))
    tmix, okm = tate(Ptors, Tgen + c * QN)
    assert okm
    pr["tate_t263(P,T+c*Q_N)==tate_t263(P,T)"] = bool(tmix == ctrl)
    assert tmix == ctrl
    tN2, ok2 = tate(Ptors, c * QN)
    assert ok2 and tN2 == 1
    pr["tate_t263(P,c*Q_N)==1"] = True
    pr["two_implementations_agree"] = True
    out["pairing_263"] = pr
    out["seconds"] = round(time.time() - t0, 2)
    return out


if __name__ == "__main__":
    labels = sys.argv[1:] or ecc2k.LABELS
    res = {}
    T0 = time.time()
    for i, lab in enumerate(labels):
        res[lab] = do_curve(lab)
        if i < 3 or i % 20 == 0 or i == len(labels) - 1:
            print(lab, res[lab]["embedding_degree_N_bits"], res[lab]["pairing_263"]["structure_E(L)[263^inf]"],
                  res[lab]["pairing_263"]["tate_t263(P,Q_N)"], res[lab]["seconds"], "s", flush=True)
    meta = {
        "script": "per_curve_pairings.py", "n_curves": len(res), "elapsed_s": round(time.time() - T0, 1),
        "L": "GF(2^262) (Sage default modulus), F_q embedded by z -> root of z^131+z^13+z^2+z+1",
        "zeta_263": "fixed generator of mu_263: phi(K.from_integer(%d))^((2^262-1)/263)" % c0,
        "all_embedding_degrees_equal": len({v["embedding_degree_N"] for v in res.values()}) == 1,
        "all_tate_263_with_N_subgroup_trivial": all(v["pairing_263"]["tate_t263(P,Q_N)"] == "1" for v in res.values()),
    }
    name = "per_curve" if len(sys.argv) == 1 else "per_curve_subset"
    (HERE / (name + ".json")).write_text(json.dumps(res, indent=1))          # {label: {...}}
    (HERE / (name + "_meta.json")).write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))
