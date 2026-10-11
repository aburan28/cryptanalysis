"""Build the ground truth for the 263 curves E0 + 262 conductor-263 floor curves
of the F_{2^131}-isogeny class of the Certicom ECC2K-130 Koblitz curve.

Run:  export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
      sage -python build_ground_truth.py
Writes ground_truth.json, build_log.json, primality_certificates.json,
class_polynomial_D-484183.hex next to this file.
"""
import hashlib
import json
import random
import time
from pathlib import Path

from sage.all import (GF, ZZ, Integer, PolynomialRing, EllipticCurve, pari,
                      kronecker, hilbert_class_polynomial, version, Mod)

HERE = Path(__file__).resolve().parent
T0 = time.time()
LOG = {"sage": version(), "steps": []}


def step(name, **data):
    rec = {"step": name, "elapsed_s": round(time.time() - T0, 3), **data}
    LOG["steps"].append(rec)
    print(json.dumps(rec, default=str), flush=True)


# ---------------------------------------------------------------- field
R2 = PolynomialRing(GF(2), "z")
zz = R2.gen()
MOD = zz**131 + zz**13 + zz**2 + zz + 1
assert MOD.is_irreducible()
MOD_INT = sum(1 << i for i, c in enumerate(MOD.list()) if c)
K = GF(2**131, name="z", modulus=MOD)
q = Integer(2)**131
enc = lambda u: int(u.to_integer())
dec = lambda n: K.from_integer(int(n))
step("field", modulus="z^131+z^13+z^2+z+1", modulus_int=MOD_INT, irreducible=True)

# ---------------------------------------------------------------- E0, t, N
N = Integer(680564733841876926932320129493409985129)
t_given = Integer(-22283658519494248867)
f_given = Integer(38531015900842053623)
p_given = Integer(146505763881528721)

# Lucas recurrence for the trace of tau^131, tau^2 + tau + 2 = 0 (t_1 = -1)
a, b_ = Integer(2), Integer(-1)     # t_0, t_1
for _ in range(130):
    a, b_ = b_, -b_ - 2 * a
t_lucas = b_
assert t_lucas == t_given, (t_lucas, t_given)
card = q + 1 - t_lucas
assert card == 4 * N

E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
tt = time.time()
card_E0_pari = E0.cardinality(algorithm="pari")
assert card_E0_pari == card
# #E0(F_2) = 4 check
E0_2 = EllipticCurve(GF(2), [1, 0, 0, 0, 1])
assert E0_2.cardinality() == 4
step("E0_order", t=t_lucas, card=card, pari_card_matches=True,
     pari_seconds=round(time.time() - tt, 4), card_over_F2=4)

# Certicom generator (from repo ecc2k130/metal/selection-20260921.json and
# research/step_table/*/coefficients.json "generatorPolynomial", stated in the
# polynomial basis z^131+z^13+z^2+z+1).  On-curve + order-N check confirms the
# modulus / representation.  (No DLP is attempted.)
GX = 0x51c99bfa6f18de467c80c23b98c7994aa
GY = 0x42ea2d112ecec71fcf7e000d7efc978bd
G = E0(dec(GX), dec(GY))           # raises if not on curve
assert not G.is_zero() and (N * G).is_zero()
step("certicom_generator_check", on_curve=True, order_is_N=True,
     source="ecc2k130/metal/selection-20260921.json domain.generatorPolynomial")

# tau (x,y)->(x^2,y^2) on E0 acts on the order-N subgroup as [s], s^2+s+2 = 0 mod N
RN = PolynomialRing(GF(N), "s")
s_roots = sorted(int(r) for r in (RN.gen()**2 + RN.gen() + 2).roots(multiplicities=False))
assert len(s_roots) == 2
tauG = E0(G[0]**2, G[1]**2)
tau_s = [s for s in s_roots if s * G == tauG]
assert len(tau_s) == 1
TAU_EIGEN = tau_s[0]
step("E0_tau_eigenvalue", s=TAU_EIGEN, other_root=[s for s in s_roots if s != TAU_EIGEN][0],
     matches_repo_frobeniusEigenvalue=(TAU_EIGEN == 196511074115861092422032515080945363956))

# discriminant / conductor
disc = t_lucas**2 - 4 * q
assert disc % 7 == 0 and (-disc) % 7 == 0
f2 = (-disc) // 7
f = f2.isqrt()
assert f * f == f2 and f == f_given
assert f == 263 * p_given
kron = kronecker(-7, 263)
assert kron == 1
step("frobenius_discriminant", t2_minus_4q=disc, f=f, f_eq_263_p=True,
     kronecker_m7_263=int(kron))

# primality (Sage is_prime -> PARI isprime: unconditional proof)
prim = {}
for name, n in [("N", N), ("p", p_given), ("263", Integer(263))]:
    tt = time.time()
    ok = n.is_prime(proof=True)
    ok_pari = bool(pari(n).isprime())
    assert ok and ok_pari, name
    prim[name] = {"value": str(n), "bits": float(n.nbits()), "is_prime": True,
                  "seconds": round(time.time() - tt, 4)}
# ECPP certificates via PARI primecert + primecertisvalid
certs = {}
for name, n in [("N", N), ("p", p_given)]:
    c = pari.primecert(n)
    valid = bool(pari.primecertisvalid(c))
    assert valid, name
    certs[name] = {"value": str(n), "pari_primecert": str(c),
                   "pari_primecertisvalid": valid}
    prim[name]["ecpp_certificate_valid"] = valid
(HERE / "primality_certificates.json").write_text(json.dumps(certs, indent=1) + "\n")
import math
step("primality", **{k: v for k, v in prim.items()},
     log2_N=math.log2(int(N)), log2_p=math.log2(int(p_given)))

ord131 = Mod(2, 131).multiplicative_order()
assert ord131 == 130
hD = int(pari.qfbclassno(-7 * 263**2))
h7 = int(pari.qfbclassno(-7))
step("class_numbers", h_minus7=h7, h_D=hD, ord_131_of_2=int(ord131))
assert h7 == 1 and hD == 262

# ---------------------------------------------------------------- H_D
D = -7 * 263**2
assert D == -484183
tt = time.time()
Hp = pari.polclass(D)            # ring class polynomial, j-invariant
RZ = PolynomialRing(ZZ, "X")
H = RZ([Integer(c) for c in pari.Vecrev(Hp)])
t_polclass = time.time() - tt
tt = time.time()
H_sage = hilbert_class_polynomial(D)
t_sage = time.time() - tt
assert RZ(list(H_sage)) == H, "PARI polclass and Sage hilbert_class_polynomial disagree"
assert H.degree() == 262 and H.is_monic()
hexenc = ("\n".join(format(int(c), "x") for c in H.list()) + "\n").encode()
(HERE / "class_polynomial_D-484183.hex").write_bytes(hexenc)
H_sha = hashlib.sha256(hexenc).hexdigest()
step("class_polynomial", degree=int(H.degree()), pari_seconds=round(t_polclass, 3),
     sage_seconds=round(t_sage, 3), pari_equals_sage=True,
     coeff_hex_sha256=H_sha, max_coeff_bits=max(int(abs(c)).bit_length() for c in H.list()))

H2 = R2(H)
assert H2.degree() == 262
assert H2.gcd(H2.derivative()) == 1
facs = list(H2.factor())
fac_degs = [(int(g.degree()), int(e)) for g, e in facs]
step("H_mod_2_factorization", factors=fac_degs,
     nonzero_exponents_H2=[i for i, c in enumerate(H2.list()) if c])
assert sorted(fac_degs) == [(131, 1), (131, 1)], fac_degs

# ---------------------------------------------------------------- Phi_263(1,Y) mod 2
tt = time.time()
Phi = pari("polmodular(263,0,Mod(1,2))")      # Phi_263(1, y) over F_2
Phi2 = R2([Integer(c.lift()) for c in pari.Vecrev(Phi)])
Y1 = zz + 1
phi_ok = (Phi2 == Y1**2 * H2)
step("modular_polynomial_check", phi263_at_j1_deg=int(Phi2.degree()),
     equals_Yplus1_squared_times_HD_mod2=bool(phi_ok), seconds=round(time.time() - tt, 2))
assert phi_ok

# ---------------------------------------------------------------- Codex labels
codex_inv_path = Path("/Users/adamburan/Documents/Codex/2026-09-22/"
                      "prior-conversation-with-codex-conversation-role-2/outputs/"
                      "public-cm-inventory/inventory.json")
codex = json.loads(codex_inv_path.read_text())
codex_exps = {m["orbit"]: m["j_minpoly_nonzero_exponents"] for m in codex["models"]}
codex_j = {m["orbit"]: int(m["j_integer_encoding"]) for m in codex["models"]}
codex_b = {m["orbit"]: int(m["b_integer_encoding"]) for m in codex["models"]}
assert codex["field_modulus_nonzero_exponents"] == [0, 1, 2, 13, 131]
match_H2 = codex["mod_2_polynomial_nonzero_exponents"] == [i for i, c in enumerate(H2.list()) if c]
match_Hsha = codex["integer_polynomial_coefficients_sha256"] == H_sha

orbit_of_factor = {}
for idx, (g, e) in enumerate(facs):
    exps = [i for i, c in enumerate(g.list()) if c]
    for o, ce in codex_exps.items():
        if ce == exps:
            orbit_of_factor[idx] = "A" if o == 0 else "B"
assert sorted(orbit_of_factor.values()) == ["A", "B"], orbit_of_factor
step("codex_factor_match", H2_exponents_match=match_H2, H_coeff_sha256_match=match_Hsha,
     sage_factor_order=[orbit_of_factor[i] for i in range(len(facs))])

RK = PolynomialRing(K, "J")
orbits = {}
for idx, (g, e) in enumerate(facs):
    lab = orbit_of_factor[idx]
    tt = time.time()
    roots = RK(g).roots(multiplicities=False)
    assert len(roots) == 131 and len(set(roots)) == 131
    base = min(roots, key=enc)
    conj = [base]
    for k in range(130):
        conj.append(conj[-1] ** 2)
    assert base ** (2**131) == base
    assert set(conj) == set(roots)
    orbits[lab] = {"poly": g, "base": base, "conj": conj,
                   "root_seconds": time.time() - tt}
    codex_o = 0 if lab == "A" else 1
    step("orbit_roots", orbit=lab, n_roots=131, base_j_int=enc(base),
         base_is_min_integer_root=True,
         matches_codex_j=(enc(base) == codex_j[codex_o]),
         matches_codex_b=(enc(1 / base) == codex_b[codex_o]),
         seconds=round(time.time() - tt, 2))
    assert enc(base) == codex_j[codex_o] and enc(1 / base) == codex_b[codex_o]

alljs = orbits["A"]["conj"] + orbits["B"]["conj"]
assert len(set(alljs)) == 262 and K(1) not in alljs and K(0) not in alljs

# ---------------------------------------------------------------- curves
rng = random.Random(20260923)
alt_card = 2 * q + 2 - card        # order of the quadratic twist
curves = []


def order_proof(E):
    """[4]P != O and [N][4]P == O for a random P: N | #E, and 4N is the only
    multiple of N in the Hasse interval (N > 4*sqrt(q)), so #E = 4N."""
    for _ in range(10):
        x = dec(rng.getrandbits(131))
        pts = E.lift_x(x, all=True)
        if not pts:
            continue
        Q = 4 * pts[0]
        if Q.is_zero():
            continue
        return (N * Q).is_zero()
    raise RuntimeError("no point found")


def build_curve(label, orbit, k, level, j):
    bb = 1 / j if j != 1 else K(1)
    rec = {"label": label, "orbit": orbit, "frob_index": k, "level": level,
           "j_int": str(enc(j)), "b_int": str(enc(bb))}
    cards = {}
    for a2 in (0, 1):
        E = EllipticCurve(K, [1, a2, 0, 0, bb])
        assert E.j_invariant() == j
        cards[a2] = Integer(E.cardinality(algorithm="pari"))
    assert cards[0] + cards[1] == 2 * q + 2
    good = [a2 for a2 in (0, 1) if cards[a2] == card]
    assert len(good) == 1, (label, cards)
    a2 = good[0]
    E = EllipticCurve(K, [1, a2, 0, 0, bb])
    proof = order_proof(E)
    assert proof
    rec.update({"a2": a2, "order_verified": True,
                "order_pari": str(cards[a2]), "twist_order_pari": str(cards[1 - a2]),
                "order_point_proof": bool(proof)})
    return rec


tt = time.time()
curves.append(build_curve("E0", "crater", 0, 1, K(1)))
for lab in ("A", "B"):
    for k, j in enumerate(orbits[lab]["conj"]):
        curves.append(build_curve(f"{lab}{k:03d}", lab, k, 263, j))
step("curves_built", count=len(curves), seconds=round(time.time() - tt, 2),
     a2_values=sorted(set(c["a2"] for c in curves)),
     all_order_4N=all(c["order_pari"] == str(card) for c in curves))
assert len(curves) == 263

# ---------------------------------------------------------------- Codex run-03 fingerprints
run03 = Path("/Users/adamburan/Documents/Codex/2026-09-22/"
             "prior-conversation-with-codex-conversation-role-2/outputs/"
             "curve-comparison/run-03-scaling")
bylabel = {c["label"]: c for c in curves}
fp_results = []
for fn in sorted(run03.glob("*.jsonl")):
    if not fn.name[0] in "AEB" or fn.name.startswith("all"):
        continue
    for line in fn.read_text().splitlines():
        r = json.loads(line)
        c = bylabel[r["curve_id"]]
        bb = dec(c["b_int"])
        E = EllipticCurve(K, [1, 0, 0, 0, bb])   # Codex used a2 = 0
        kk = r["k"]
        W = K.gen()
        cnt = 0
        for mask in range(1, 1 << kk):
            x = sum((W**i for i in range(kk) if mask >> i & 1), K(0))
            if (x + K(0) + bb / x**2).trace() == 0:
                cnt += 1
        tx = dec(int(r["target_x_integer"]))
        pts = E.lift_x(tx, all=True)
        in_sub = bool(pts) and (N * pts[0]).is_zero()
        fp_results.append({"curve": r["curve_id"], "k": kk,
                           "codex_x_count": r["factor_base_x_count"], "our_x_count": cnt,
                           "target_x_in_N_subgroup": in_sub})
fp_ok = all(r["codex_x_count"] == r["our_x_count"] and r["target_x_in_N_subgroup"]
            for r in fp_results)
step("codex_run03_fingerprints", all_match=fp_ok, rows=fp_results)

# ---------------------------------------------------------------- write
labels_source = (
    "Codex labels reproduced exactly. Codex's public-cm-inventory/build_inventory.py "
    "(read) labels orbit 0 = A, 1 = B in Sage's H_D-mod-2 factor order, takes the "
    "smallest-integer root j of each factor (polynomial basis z^131+z^13+z^2+z+1, "
    "integer bit i = z^i) as index 000 and sets X_k: j = j(X000)^(2^k) "
    "(run-01/executed-source.py curve_inventory). Our min-integer roots equal "
    "Codex's inventory.json j/b for both orbits, the A factor's exponent list equals "
    "Codex's orbit-0 j_minpoly, and factor_base_x_count / target_x fingerprints in "
    "run-03-scaling/{E0,A010,A112,A127,B000,B095}.jsonl all match.")
meta = {
    "modulus_int": str(MOD_INT),
    "modulus": "z^131+z^13+z^2+z+1",
    "encoding": "field element = integer bitmask, bit i = coefficient of z^i",
    "curve_form": "y^2 + x*y = x^3 + a2*x^2 + b  (Sage a-invariants [1,a2,0,0,b]); j = 1/b",
    "q": str(q), "t": str(t_lucas), "N": str(N), "f": str(f), "p": str(p_given),
    "card": str(card), "twist_card": str(alt_card),
    "D_frobenius": str(disc), "D_ring_class": str(D), "h_D": hD,
    "class_polynomial_coeff_hex_sha256": H_sha,
    "labels_source": labels_source,
    "method": (
        "Sage 10.9 / PARI. t by Lucas recurrence (t1=-1) and PARI ellcard on E0; N, p, 263 "
        "prime by Sage is_prime(proof=True)=PARI isprime plus PARI primecert ECPP certificates "
        "validated with primecertisvalid; H_D = PARI polclass(-484183), equal to Sage "
        "hilbert_class_polynomial; H_D mod 2 squarefree, two irreducible degree-131 factors; "
        "Phi_263(1,Y) mod 2 (PARI polmodular) == (Y+1)^2 * H_D(Y) mod 2; roots in F_q by Sage "
        "root finding, equal to the 131 Frobenius conjugates of the base root; for every "
        "curve both twists a2 in {0,1} point-counted with PARI (cardinality(algorithm='pari')), "
        "exactly one has order 4N, plus an independent random-point order proof "
        "([4]P != O, [N][4]P = O). Certicom generator (repo) lies on E0 and has order N."),
    "E0_tau_eigenvalue": str(TAU_EIGEN),
    "E0_tau_eigenvalue_note": "tau(x,y)=(x^2,y^2) on E0 equals [s] on the order-N subgroup; s^2+s+2=0 mod N",
    "floor_curve_notes": "each floor j generates F_q over F_2 (degree 131), so floor curves have no F_2-model and no tau endomorphism; Frobenius x->x^2 maps X_k to X_{k+1 mod 131}; End = Z + 263*O_K (conductor 263, from H_D)",
    "sage_version": version(),
}
out = {"meta": meta, "curves": curves}
(HERE / "ground_truth.json").write_text(json.dumps(out, indent=1) + "\n")
LOG["total_seconds"] = time.time() - T0
(HERE / "build_log.json").write_text(json.dumps(LOG, indent=1, default=str) + "\n")
print("DONE", len(curves), "curves in", round(time.time() - T0, 1), "s")
