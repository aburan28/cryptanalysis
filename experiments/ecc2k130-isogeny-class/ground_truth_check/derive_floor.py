#!/usr/bin/env sage -python
"""
Independent re-derivation of the 262 conductor-263 ("floor") curves below the
ECC2K-130 Koblitz curve E0 : y^2 + xy = x^3 + 1 over F_q, q = 2^131, and a
cross-check against ../ground_truth/ground_truth.json.

Method (does NOT use the class polynomial H_D or the modular polynomial Phi_263,
which is what the ground-truth build used):

  A. Work in F_{q^2} = GF(2^262) (own modulus, minimal weight).  Frobenius pi of
     E0/F_q acts on E0[263] as the scalar t/2 mod 263 = -1, so E0[263] lies in
     E0(F_{q^2}).  Find a basis P1,P2 of E0[263] from random points times the
     cofactor, enumerate the 264 cyclic subgroups <P1>, <P2 + i P1>, and for each
     compute the codomain j of the degree-263 isogeny twice:
        (i)  Sage's E.isogeny(kernel point) (library Velu),
        (ii) a hand Velu formula: for y^2+xy = x^3+a2x^2+a6 and an odd kernel G,
             codomain = [1,a2,0,v,a6+v] with v = sum of the 131 distinct
             x-coordinates of G\\{O}; so j' = 1/(a6 + v + v^2).
     Pull the j's back to F_q through an explicit embedding F_q -> F_{q^2}
     (z -> a root of the ECC2K modulus).
  B. Work natively in F_q (ECC2K polynomial basis): the quadratic twist
     E0' : y^2+xy = x^3+x^2+1 has #E0'(F_q) = q+1+t with v_263 = 2 and Frobenius
     acting as +1 on E0'[263], so E0'[263] = E0'(F_q)[263^oo].  Enumerate the 264
     subgroups again, hand Velu + Sage isogeny.  (Twisting does not change j.)
  C. Compare A (pulled back) with B, then with the ground-truth file: j set, b = 1/j,
     a2, orbit split and Frobenius indices.
  D. Per floor curve (all 262): #E(F_q) = 4N by an explicit point of order exactly
     4N + Hasse; twist a2=1 has order q+1+t; level check (the twist's 263-Sylow is
     cyclic Z/263^2, unlike E0' where it is (Z/263)^2); the unique F_q-rational
     263-subgroup of the twist maps back up to j = 1 (ascending edge).
  E. For a sample of 12 floor curves: an explicit F_q-rational isogeny
     E0 -> E (Sage/Kohel, from the kernel polynomial over F_q) maps a point of order
     4N on E0(F_q) to a point of order 4N on E, and the codomain is F_q-isomorphic
     to the a2=0 model -- so #E = #E0 by Tate, independent of point counting.

Everything is written to this directory.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from sage.all import (GF, EllipticCurve, PolynomialRing, ZZ, Integer, Mod,
                      is_prime, valuation, matrix, vector, set_random_seed,
                      factor, isqrt, kronecker, pari, version)

HERE = Path(__file__).resolve().parent
GT = Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json")
T0 = time.time()
LOG = []


def log(name, ok, **detail):
    ok = bool(ok)
    rec = {"check": name, "ok": ok, "t": round(time.time() - T0, 2)}
    rec.update({k: (str(v) if isinstance(v, (Integer,)) or (isinstance(v, int) and abs(v) > 2**53) else v)
                for k, v in detail.items()})
    LOG.append(rec)
    print(("PASS " if ok else "FAIL ") + name + ("  " + json.dumps({k: rec[k] for k in detail}) if detail else ""),
          flush=True)
    if not ok:
        dump()
        raise SystemExit("check failed: " + name)


RESULT = {}


def dump():
    (HERE / "derive_floor_output.json").write_text(json.dumps({"log": LOG, "result": RESULT}, indent=1))


set_random_seed(20260923)

# ---------------------------------------------------------------- 0. constants
q = 2**131
# E0 over F_2: count points by brute force
F2 = GF(2)
cnt = 1 + sum(1 for X in F2 for Y in F2 if Y**2 + X * Y == X**3 + 1)
log("#E0(F_2) by brute force", cnt == 4, count=cnt)
# traces of tau^k: tau^2 + tau + 2 = 0 (a_1 = 2+1-4 = -1)
s = [2, -1]
for k in range(2, 263):
    s.append(-s[-1] - 2 * s[-2])
t = s[131]
t_q2 = s[262]
log("trace from Lucas recurrence equals task value", t == -22283658519494248867, t=t)
log("t_{q^2} = t^2 - 2q", t_q2 == t * t - 2 * q)
card = q + 1 - t
N = card // 4
log("#E0(F_q) = 4N", card == 4 * N and N == 680564733841876926932320129493409985129, N=N)
log("N prime (proof=True)", Integer(N).is_prime(proof=True), bits=float(Integer(N).nbits()))
twist_card = q + 1 + t
D = t * t - 4 * q
f = isqrt(D // -7)
log("t^2-4q = -7 f^2", D == -7 * f * f and f == 38531015900842053623, f=f)
p = f // 263
log("f = 263 p, p prime", f == 263 * p and Integer(p).is_prime(proof=True) and p == 146505763881528721, p=p)
log("kronecker(-7,263) = +1 (263 splits in Q(sqrt-7))", kronecker(-7, 263) == 1)
lam = (t * pow(2, -1, 263)) % 263
log("pi acts on E0[263] as scalar t/2 mod 263 = -1", lam == 262, scalar=int(lam), two_pow_131_mod_263=pow(2, 131, 263))
ordlam = min(k for k in range(1, 263) if pow(lam, k, 263) == 1)
log("order of scalar = 2 => E0[263] rational over F_{q^2}, not F_q", ordlam == 2, order=ordlam)
v_q2 = valuation(Integer(card * twist_card), 263)
log("v_263(#E0(F_q)) = 0, v_263(#E0'(F_q)) = v_263(#E0(F_q^2)) = 2",
    valuation(Integer(card), 263) == 0 and valuation(Integer(twist_card), 263) == 2 and v_q2 == 2)
log("#E0(F_{q^2}) = (q+1-t)(q+1+t)", q * q + 1 - t_q2 == card * twist_card)
tw_cof = twist_card // 263**2
tw_fac = factor(Integer(tw_cof))
log("factor (q+1+t)/263^2", all(Integer(pp).is_prime(proof=True) for pp, _ in tw_fac), factorization=str(tw_fac))
BIG = max(pp for pp, _ in tw_fac)
sq = isqrt(q)
hasse_lo, hasse_hi = q + 1 - 2 * (sq + 1), q + 1 + 2 * (sq + 1)
mults_N = [m for m in range(hasse_lo // N, hasse_hi // N + 2) if hasse_lo <= m * N <= hasse_hi]
log("only multiple of N in Hasse interval is 4N", mults_N == [4], multiples=mults_N)
mults_B = [m for m in range(hasse_lo // BIG, hasse_hi // BIG + 2) if hasse_lo <= m * BIG <= hasse_hi]
log("only multiple of the big prime of q+1+t in Hasse interval is q+1+t",
    len(mults_B) == 1 and mults_B[0] * BIG == twist_card)

# ---------------------------------------------------------------- fields
Rz = PolynomialRing(GF(2), "z")
z = Rz.gen()
modK = z**131 + z**13 + z**2 + z + 1
log("ECC2K modulus z^131+z^13+z^2+z+1 irreducible", modK.is_irreducible())
K = GF(2**131, "z", modulus=modK)
log("K modulus integer", Integer(modK.change_ring(ZZ)(2)) == (1 << 131) | (1 << 13) | 7)
Rw = PolynomialRing(GF(2), "w")
mod2 = Rw.irreducible_element(262, algorithm="minimal_weight")
K2 = GF(2**262, "w", modulus=mod2)
log("F_{q^2} = GF(2^262) modulus", mod2.is_irreducible(), modulus=str(mod2))
r = modK.change_ring(K2).any_root()
log("embedding root r of ECC2K modulus in F_{q^2}, lies in the order-2^131 subfield",
    modK.change_ring(K2)(r) == 0 and r.frobenius(131) == r and r not in (K2(0), K2(1)))
powers = [K2(1)]
for i in range(1, 131):
    powers.append(powers[-1] * r)
EMB = matrix(GF(2), [vector(GF(2), pw.polynomial().padded_list(262)) for pw in powers])  # 131 x 262
log("embedding matrix has rank 131", EMB.rank() == 131)


def emb(u):
    """F_q (ECC2K basis) -> F_{q^2}"""
    c = u.polynomial().padded_list(131)
    return sum((powers[i] for i in range(131) if c[i]), K2(0))


def pullback(e):
    """F_{q^2} element in the image of F_q -> F_q element (ECC2K basis)"""
    sol = EMB.solve_left(vector(GF(2), e.polynomial().padded_list(262)))
    return K(Rz(list(sol)))


def enc(u):
    return int(u.to_integer())


def in_Fq(e):
    return e.frobenius(131) == e


# sanity of emb as a ring map on random elements
okhom = True
for _ in range(20):
    a, b = K.random_element(), K.random_element()
    okhom &= emb(a * b) == emb(a) * emb(b) and emb(a + b) == emb(a) + emb(b) and pullback(emb(a)) == a
log("emb is a ring homomorphism and pullback inverts it (20 random pairs)", okhom)


# ---------------------------------------------------------------- helpers
def torsion_basis_263(E, cof, maxtries=200):
    """basis of E[263] from random points times the cofactor (E[263] assumed to be the whole 263-Sylow)"""
    P1 = None
    for _ in range(maxtries):
        Q = cof * E.random_point()
        if Q.is_zero():
            continue
        assert (263 * Q).is_zero()
        if P1 is None:
            P1 = Q
            xs1 = set(kernel_xs(P1))
            continue
        if Q[0] not in xs1:
            return P1, Q
    raise RuntimeError("no basis")


def kernel_xs(G):
    """the 131 x-coordinates of <G>\\{O}, G of order 263"""
    xs, Q = [], G
    for _ in range(131):
        xs.append(Q[0])
        Q = Q + G
    return xs


def tau(P):
    return P.curve()(P[0]**2, P[1]**2) if not P.is_zero() else P


def enumerate_kernels(E, P1, P2, label):
    """264 cyclic subgroups of E[263] = <P1,P2>; returns list of dicts"""
    gens = [("inf", P1)] + [(i, P2 + i * P1) for i in range(263)]
    a1, a2, a3, a4, a6 = E.a_invariants()
    assert (a1, a3, a4) == (1, 0, 0)
    out, xsets = [], set()
    for idx, G in gens:
        assert not G.is_zero() and (263 * G).is_zero()
        xs = kernel_xs(G)
        xset = frozenset(xs)
        assert len(xset) == 131
        xsets.add(xset)
        v = sum(xs)
        j_hand = 1 / (a6 + v + v**2)
        phi = E.isogeny(G)
        Ec = phi.codomain()
        j_lib = Ec.j_invariant()
        tg = tau(G)
        horiz = tg[0] in xset
        out.append({"idx": idx, "G": G, "xs": xs, "v": v, "j_hand": j_hand, "j_lib": j_lib,
                    "tau_stable": horiz, "codomain_a4_eq_v": Ec.a_invariants()[3] == v})
    log(label + ": 264 distinct cyclic subgroups", len(xsets) == 264)
    return out


# ---------------------------------------------------------------- A. F_{q^2}
tA = time.time()
E2 = EllipticCurve(K2, [1, 0, 0, 0, 1])
E2.set_order(card * twist_card)
cofA = card * twist_card // 263**2
P1, P2 = torsion_basis_263(E2, cofA)
log("A: P1,P2 have order 263 in E0(F_{q^2})", (263 * P1).is_zero() and (263 * P2).is_zero() and not P1.is_zero())
frob = lambda P: P.curve()(P[0].frobenius(131), P[1].frobenius(131))
log("A: q-Frobenius acts as -1 on P1, P2", frob(P1) == -P1 and frob(P2) == -P2)
log("A: P1,P2 not defined over F_q (y not in F_q), x in F_q",
    not in_Fq(P1[1]) and not in_Fq(P2[1]) and in_Fq(P1[0]) and in_Fq(P2[0]))
try:
    wp = P1.weil_pairing(P2, 263)
    log("A: Weil pairing e_263(P1,P2) nontrivial 263rd root of unity", wp != 1 and wp**263 == 1)
except Exception as ex:  # pairing is a bonus, independence is already shown via x-sets
    log("A: Weil pairing (skipped: %s)" % type(ex).__name__, True)
# tau eigenvalues mod 263
tau_eigs = [e for e in range(263) if (e * e + e + 2) % 263 == 0]
log("A: tau^2+tau+2 has two roots mod 263", len(tau_eigs) == 2, roots=tau_eigs)
kerA = enumerate_kernels(E2, P1, P2, "A")
log("A: hand Velu j == Sage isogeny j for all 264 kernels", all(k["j_hand"] == k["j_lib"] for k in kerA))
log("A: Sage codomain a4 == hand v for all 264", all(k["codomain_a4_eq_v"] for k in kerA))
log("A: every kernel x-coordinate lies in F_q (pi = -1 on E0[263])",
    all(in_Fq(xx) for k in kerA for xx in k["xs"]))
log("A: every codomain j lies in F_q", all(in_Fq(k["j_lib"]) for k in kerA))
horizA = [k for k in kerA if k["j_lib"] == 1]
tauA = [k for k in kerA if k["tau_stable"]]
log("A: exactly 2 kernels give j = 1, and they are exactly the tau-stable kernels (ker(tau - e))",
    len(horizA) == 2 and {id(k) for k in horizA} == {id(k) for k in tauA},
    idx_j1=[str(k["idx"]) for k in horizA])
# each tau-stable kernel: tau acts as one of the eigenvalues
eig_seen = []
for k in tauA:
    G = k["G"]
    for e in tau_eigs:
        if tau(G) == e * G:
            eig_seen.append(e)
log("A: the two horizontal kernels are the two tau-eigenspaces", sorted(eig_seen) == sorted(tau_eigs), eig=eig_seen)
floorA_K2 = [k["j_lib"] for k in kerA if k["j_lib"] != 1]
log("A: 262 distinct floor j's", len(floorA_K2) == 262 and len(set(floorA_K2)) == 262)
floorA = [pullback(j) for j in floorA_K2]
log("A: pulled-back j's re-embed correctly", all(emb(a) == j for a, j in zip(floorA, floorA_K2)))
xsetsA_Fq = {frozenset(enc(pullback(xx)) for xx in k["xs"]) for k in kerA}
timeA = time.time() - tA
print("A done in %.1fs" % timeA, flush=True)

# ---------------------------------------------------------------- B. twist over F_q
tB = time.time()
Et = EllipticCurve(K, [1, 1, 0, 0, 1])
log("B: E0' = [1,1,0,0,1] has j = 1", Et.j_invariant() == 1)
Et.set_order(twist_card)
T1, T2 = torsion_basis_263(Et, tw_cof)
log("B: E0'(F_q) contains two independent points of order 263 => 263-Sylow = E0'[263] = (Z/263)^2",
    (263 * T1).is_zero() and (263 * T2).is_zero())
kerB = enumerate_kernels(Et, T1, T2, "B")
log("B: hand Velu j == Sage isogeny j for all 264 kernels", all(k["j_hand"] == k["j_lib"] for k in kerB))
horizB = [k for k in kerB if k["j_lib"] == 1]
tauB = [k for k in kerB if k["tau_stable"]]
log("B: exactly 2 kernels give j = 1 = the tau-stable ones",
    len(horizB) == 2 and {id(k) for k in horizB} == {id(k) for k in tauB})
floorB = [k["j_lib"] for k in kerB if k["j_lib"] != 1]
log("B: 262 distinct floor j's", len(floorB) == 262 and len(set(floorB)) == 262)
xsetsB = {frozenset(enc(xx) for xx in k["xs"]) for k in kerB}
log("A vs B: the 264 kernel x-sets coincide (E0 ~ E0' over F_{q^2} by (x,y)->(x,y+sx))", xsetsA_Fq == xsetsB)
timeB = time.time() - tB
print("B done in %.1fs" % timeB, flush=True)

# ---------------------------------------------------------------- C. compare
setA = {enc(j) for j in floorA}
setB = {enc(j) for j in floorB}
log("A vs B: floor j sets equal", setA == setB, size=len(setA & setB))
mine = setB
log("no floor j is 0 or 1", 0 not in mine and 1 not in mine)
# Frobenius orbits of my set
jK = {enc(j): j for j in floorB}
remaining = set(mine)
orbits = []
while remaining:
    j0 = jK[min(remaining)]
    orb = [j0]
    for _ in range(130):
        orb.append(orb[-1]**2)
    log_ok = orb[-1]**2 == j0 and len({enc(u) for u in orb}) == 131 and {enc(u) for u in orb} <= remaining
    if not log_ok:
        log("Frobenius orbit closes with length 131 inside the set", False)
    remaining -= {enc(u) for u in orb}
    orbits.append(orb)
log("my 262 j's = two Frobenius orbits of length 131", len(orbits) == 2 and all(len(o) == 131 for o in orbits),
    orbit_sizes=[len(o) for o in orbits])
Ry = PolynomialRing(K, "Y")
Y = Ry.gen()
minpolys = []
for orb in orbits:
    prod_ = Ry(1)
    for u in orb:
        prod_ = prod_ * (Y - u)
    cl = prod_.list()
    mpF2 = PolynomialRing(GF(2), "Y")([1 if c == 1 else 0 for c in cl]) if all(c in (K(0), K(1)) for c in cl) else None
    minpolys.append(mpF2)
log("each orbit's product (Y - j) has F_2 coefficients", all(m is not None for m in minpolys))
log("each orbit minimal polynomial irreducible of degree 131 over F_2",
    all(m.degree() == 131 and m.is_irreducible() for m in minpolys))

# ground truth
gt = json.loads(GT.read_text())
gt_meta = gt["meta"]
gt_curves = gt["curves"]
log("GT modulus is the ECC2K modulus", int(gt_meta["modulus_int"]) == (1 << 131) | (1 << 13) | 7)
gt_floor = [c for c in gt_curves if c["level"] == 263]
gt_E0 = [c for c in gt_curves if c["label"] == "E0"]
log("GT E0 record: j = b = 1, a2 = 0", len(gt_E0) == 1 and gt_E0[0]["j_int"] == "1" and gt_E0[0]["b_int"] == "1"
    and int(gt_E0[0]["a2"]) == 0)
gt_set = {int(c["j_int"]) for c in gt_floor}
agree = len(mine & gt_set)
log("GT has 262 distinct floor j's", len(gt_floor) == 262 and len(gt_set) == 262)
only_mine = sorted(mine - gt_set)
only_gt = sorted(gt_set - mine)
log("SET AGREEMENT my floor j's == GT floor j's", mine == gt_set, agree=agree, only_mine=len(only_mine),
    only_gt=len(only_gt))
bad_b = [c["label"] for c in gt_floor if enc(1 / K.from_integer(int(c["j_int"]))) != int(c["b_int"])]
log("GT b = 1/j for every floor record", not bad_b, bad=bad_b)
bad_a2 = [c["label"] for c in gt_floor if int(c["a2"]) != 0]
log("GT a2 = 0 for every floor record (my F_q-rational isogeny from E0 lands on [1,0,0,v,1+v] ~ [1,0,0,0,1+v+v^2])",
    not bad_a2, bad=bad_a2)
# my own b from Velu on E0 directly: b = 1 + v + v^2 (A-side, pulled back), compare with GT b
myb_A = {enc(pullback(1 + k["v"] + k["v"]**2)) for k in kerA if k["j_lib"] != 1}
log("my b = 1+v+v^2 (Velu on E0, pulled back) equals GT b set", myb_A == {int(c["b_int"]) for c in gt_floor})
# orbit / label consistency
gt_orb = {"A": {int(c["j_int"]) for c in gt_floor if c["orbit"] == "A"},
          "B": {int(c["j_int"]) for c in gt_floor if c["orbit"] == "B"}}
my_orb_sets = [{enc(u) for u in o} for o in orbits]
log("my two orbits equal GT orbits A and B as sets",
    sorted(map(sorted, my_orb_sets)) == sorted(map(sorted, gt_orb.values())))
lab_bad = []
for name in "AB":
    base = K.from_integer(min(gt_orb[name]))
    powj = base
    for k in range(131):
        rec = next(c for c in gt_floor if c["label"] == "%s%03d" % (name, k))
        if int(rec["j_int"]) != enc(powj) or int(rec["frob_index"]) != k or rec["orbit"] != name:
            lab_bad.append(rec["label"])
        powj = powj**2
log("GT labels: X000 = min-int root of its orbit and j(X_k) = j(X000)^(2^k)", not lab_bad, bad=lab_bad[:10])
# which of my minimal polynomials is 'A' (GT: first factor in Sage factor() order of H_D mod 2)
mp_by_orbit = {}
for o, m in zip(my_orb_sets, minpolys):
    mp_by_orbit["A" if o == gt_orb["A"] else "B"] = m
HD2 = mp_by_orbit["A"] * mp_by_orbit["B"]
# compare with the class polynomial file mod 2 (parity of each hex coefficient)
hexfile = GT.parent / "class_polynomial_D-484183.hex"
if hexfile.exists():
    coeffs = [int(l.strip(), 16) for l in hexfile.read_text().split() if l.strip()]
    HDmod2 = PolynomialRing(GF(2), "Y")([c % 2 for c in coeffs])
    log("prod over my 262 floor j of (Y - j) == H_D mod 2 from the GT hex file", HD2 == HDmod2,
        deg=HDmod2.degree())
    fac = HDmod2.factor()
    log("Sage factor() order of H_D mod 2: first factor = my orbit that GT calls A",
        list(fac)[0][0] == mp_by_orbit["A"])
    # a check that does not rely on GT at all: the product equals Sage/PARI's own class polynomial mod 2
tC = time.time()
HD = pari("polclass(-484183)")
HDs = PolynomialRing(GF(2), "Y")([int(c) % 2 for c in HD.Vecrev()])
log("prod (Y - j) == PARI polclass(-7*263^2) mod 2 (freshly computed)", HD2 == HDs)
RESULT["time_polclass"] = round(time.time() - tC, 1)
RESULT["time_A"] = round(timeA, 1)
RESULT["time_B"] = round(timeB, 1)

# ---------------------------------------------------------------- D. per-curve group order / level / ascent
tD = time.time()
order_ok, twist_ok, level_ok, ascent_ok = [], [], [], []
for jj in floorB:
    b = 1 / jj
    Ef = EllipticCurve(K, [1, 0, 0, 0, b])
    assert Ef.j_invariant() == jj
    # point of exact order 4N  (4N = 2^2 * N, N prime: maximal proper divisors are 2N and 4)
    found = False
    for _ in range(40):
        P = Ef.random_point()
        if (4 * N * P).is_zero() and not (2 * N * P).is_zero() and not (4 * P).is_zero():
            found = True
            break
        assert (4 * N * P).is_zero(), "point not killed by 4N"
    order_ok.append(found)
    # twist a2 = 1: a point whose order is divisible by BIG, and killed by q+1+t
    Eft = EllipticCurve(K, [1, 1, 0, 0, b])
    ok_tw = False
    for _ in range(20):
        P = Eft.random_point()
        assert (twist_card * P).is_zero(), "twist point not killed by q+1+t"
        if not ((twist_card // BIG) * P).is_zero():
            ok_tw = True
            break
    twist_ok.append(ok_tw)
    # level: twist's 263-Sylow (order 263^2) is cyclic: exists point of order 263^2
    lv = False
    for _ in range(20):
        Q = tw_cof * Eft.random_point()
        if not (263 * Q).is_zero():
            assert (263 * 263 * Q).is_zero()
            lv = True
            break
    level_ok.append(lv)
    # ascent: unique rational 263-subgroup <263 Q> -> Velu codomain j must be 1
    if lv:
        R = 263 * Q
        v = sum(kernel_xs(R))
        ascent_ok.append(1 / (b + v + v**2) == 1)
    else:
        ascent_ok.append(False)
log("D: all 262 floor curves [1,0,0,0,1/j] have a point of exact order 4N  => #E(F_q) = 4N (Hasse)",
    all(order_ok), count=sum(order_ok))
log("D: all 262 twists [1,1,0,0,1/j] have #=q+1+t (point order divisible by the 114-bit prime)",
    all(twist_ok), count=sum(twist_ok))
log("D: all 262 floor twists have a point of order 263^2 (cyclic 263-Sylow => pi not scalar mod 263 => not on crater)",
    all(level_ok), count=sum(level_ok))
# contrast: E0' has no point of order 263^2 (checked on 30 random points; proven by the basis in B)
e0_cyc = any(not (263 * (tw_cof * Et.random_point())).is_zero() for _ in range(30))
log("D: contrast E0': no point of order 263^2 among 30 random points", not e0_cyc)
log("D: for all 262 floor curves the unique F_q-rational 263-subgroup of the twist maps to j = 1 (ascending edge)",
    all(ascent_ok), count=sum(ascent_ok))
RESULT["time_D"] = round(time.time() - tD, 1)

# ---------------------------------------------------------------- E. explicit F_q-isogeny for a sample
tE = time.time()
E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
E0.set_order(card)
while True:
    P0 = E0.random_point()
    if not (2 * N * P0).is_zero() and not (4 * P0).is_zero():
        break
log("E: P0 in E0(F_q) has exact order 4N", (4 * N * P0).is_zero())
floor_k = [k for k in kerB if k["j_lib"] != 1]
jidx = {enc(k["j_lib"]): k for k in floor_k}
gt_by_label = {c["label"]: c for c in gt_floor}
sample_labels = ["A000", "A001", "A010", "A064", "A090", "A112", "A127", "B000", "B021", "B064", "B095", "B130"]
sample = []
RX = PolynomialRing(K, "X")
for lab in sample_labels:
    jint = int(gt_by_label[lab]["j_int"])
    k = jidx[jint]
    hker = RX(1)
    for xx in k["xs"]:
        hker *= RX.gen() - xx
    t1 = time.time()
    phi = E0.isogeny(hker)  # F_q-rational, from the kernel polynomial (x's of E0[263]-subgroup = those of E0')
    Ec = phi.codomain()
    img = phi(P0)
    Ef = EllipticCurve(K, [1, 0, 0, 0, K.from_integer(int(gt_by_label[lab]["b_int"]))])
    rec = {"label": lab, "degree": int(phi.degree()),
           "codomain_j_eq_gt": enc(Ec.j_invariant()) == jint,
           "image_order_4N": (4 * N * img).is_zero() and not (2 * N * img).is_zero() and not (4 * img).is_zero(),
           "codomain_Fq_isomorphic_to_gt_model": Ec.is_isomorphic(Ef),
           "codomain_not_isomorphic_to_twist": not Ec.is_isomorphic(EllipticCurve(K, [1, 1, 0, 0, Ef.a6()])),
           "seconds": round(time.time() - t1, 2)}
    sample.append(rec)
    print("  E sample", rec, flush=True)
log("E: 12 sampled floor curves: explicit F_q-rational 263-isogeny E0 -> E maps a 4N-order point to a 4N-order point "
    "and lands on GT's a2=0 model (so #E = #E0 = 4N by Tate)",
    all(r["degree"] == 263 and r["codomain_j_eq_gt"] and r["image_order_4N"] and r["codomain_Fq_isomorphic_to_gt_model"]
        and r["codomain_not_isomorphic_to_twist"] for r in sample), n=len(sample))
RESULT["time_E"] = round(time.time() - tE, 1)

# ---------------------------------------------------------------- output
my_sorted = sorted(mine)
RESULT.update({
    "sage_version": version(),
    "field_Fq_modulus": "z^131+z^13+z^2+z+1",
    "field_Fq2_modulus": str(mod2),
    "embedding_root_int_in_Fq2": int(r.to_integer()),
    "t": str(t), "N": str(N), "f": str(f), "p": str(p),
    "pi_scalar_on_E0_263": int(lam),
    "tau_eigenvalues_mod_263": tau_eigs,
    "twist_card_factorization": str(tw_fac),
    "n_kernels": 264, "n_horizontal": len(horizB), "n_floor": len(floorB),
    "orbit_sizes": [len(o) for o in orbits],
    "set_agreement": "%d/262" % agree,
    "only_mine": [str(x) for x in only_mine], "only_gt": [str(x) for x in only_gt],
    "floor_j_sorted_sha256": hashlib.sha256(",".join(map(str, my_sorted)).encode()).hexdigest(),
    "sample_isogeny_checks": sample,
    "total_seconds": round(time.time() - T0, 1),
})
(HERE / "my_floor_j.json").write_text(json.dumps({
    "note": "floor j-invariants derived by Velu from E0[263] (method B, native ECC2K basis); integers = bitmask, bit i = z^i",
    "orbits": [[str(enc(u)) for u in o] for o in orbits],
    "sorted": [str(x) for x in my_sorted]}, indent=0))
dump()
print("ALL CHECKS PASSED in %.1fs; set agreement %d/262" % (time.time() - T0, agree))
