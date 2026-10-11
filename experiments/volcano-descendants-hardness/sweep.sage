# Hardness parameter sweep over the ECC2K-130 isogeny volcano.
#
# E0: y^2 + xy = x^3 + 1 over F_{2^131}; End(E0) = O_K = Z[(1+sqrt(-7))/2].
# Z[pi] has conductor f = 263 * P, P = 146505763881528721, so the volcano has
# levels O_c = Z + c O_K for c in {1, 263, P, 263P}.  The 263 level is
# instantiated exhaustively (all 264 degree-263 neighbours of E0); the P and
# 263P levels are classified algebraically (constructing them needs
# P-isogenies, P ~ 2^57).
#
# Run: sage sweep.sage   -> results.json, descendants.csv

import json, time
from sage.schemes.elliptic_curves.ell_curve_isogeny import EllipticCurveIsogeny
from collections import Counter

set_random_seed(20260923)
R.<x> = GF(2)[]
MOD = x^131 + x^13 + x^2 + x + 1
K.<z> = GF(2**131, modulus=MOD)
m = 131
q = 2**m
ell = 263
P_big = 146505763881528721

E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
E0t = EllipticCurve(K, [1, 1, 0, 0, 1])          # quadratic twist
n = E0.cardinality()
nt = E0t.cardinality()
t = q + 1 - n
N = n // 4
assert n % 4 == 0 and is_prime(N)
D = t^2 - 4*q
f2 = D // -7
f = isqrt(f2)
assert f^2 == f2 and f == ell * P_big and is_prime(P_big)

# ---- shared (isogeny-invariant) parameters ---------------------------------
k_emb = Mod(q, N).multiplicative_order()
nt_fact = factor(nt)
twist_prime = max(p for p, _ in nt_fact)
log2 = lambda v: float(RR(v).log(2))
rho_plain = sqrt(RR(pi) * N / 4)                  # negation map only
rho_frob = sqrt(RR(pi) * N / (4 * m))             # negation + tau orbit of size 131

def kron(a, p):
    return kronecker(a, p)

def h_order(c):
    # h(O_c) = h(O_K) * c * prod_{l | c} (1 - (dK/l)/l) / [O_K^* : O_c^*]; h(O_K)=1, units +-1.
    val = QQ(c)
    for p, _ in factor(c):
        val *= (1 - QQ(kron(-7, p)) / p)
    return ZZ(val)

levels = []
for c in [1, ell, P_big, ell * P_big]:
    disc = -7 * c^2
    levels.append({
        "conductor": str(c),
        "conductor_factors": str(factor(c)) if c > 1 else "1",
        "discriminant": str(disc),
        "class_number": str(h_order(c)),
        "class_number_log2": float(round(log2(h_order(c)), 3r)),
        "smallest_noninteger_endomorphism_degree": str(2 if c == 1 else (1 + 7 * c^2) // 4),
        "tau_in_End": c == 1,
        "instantiated": c in (1, ell),
    })

# ---- GHS / Weil-descent magic number ---------------------------------------
def magic_number(b):
    # m(b) = dim_F2 span{ (1, sigma^i(sqrt b)) : 0 <= i < m }  (Menezes-Qu / Hess).
    s = b.sqrt()
    rows = []
    for i in range(m):
        v = [1] + list((s^(2^i)).polynomial().padded_list(m))
        rows.append(v)
    return matrix(GF(2), rows).rank()

# ---- 263-torsion of the twist: E0t(F_q)[263] = (Z/263)^2 -------------------
assert nt % ell^2 == 0 and nt % ell^3 != 0
h263 = nt // ell^2

def torsion_basis(C):
    while True:
        A = C.random_point() * h263
        if A.is_zero():
            continue
        A = A * (A.order() // ell) if A.order() != ell else A
        B = C.random_point() * h263
        if B.is_zero():
            continue
        B = B * (B.order() // ell) if B.order() != ell else B
        if A.weil_pairing(B, ell) != 1:
            return A, B

A, B = torsion_basis(E0t)
kernels = [B] + [A + i * B for i in range(ell)]
assert len(kernels) == ell + 1

def ell_primary_shape(C):
    # Return the max order of 263-primary points on C(F_q) (twist side):
    # 263^2 -> cyclic Z/263^2, 263 -> (Z/263)^2.
    best = 1
    for _ in range(12):
        Q = C.random_point() * h263
        o = Q.order() if not Q.is_zero() else 1
        best = max(best, o)
        if best == ell^2:
            break
    return best

def descendant_with_trace(jv):
    # y^2 + xy = x^3 + a x^2 + 1/j with #E = n.
    b = 1 / jv
    for a in (0, 1):
        C = EllipticCurve(K, [1, a, 0, 0, b])
        if C.cardinality() == n:
            return a, b, C
    raise ValueError("no twist with trace t")

def frob_orbit_key(jv):
    return min(int((jv^(2^i)).to_integer()) for i in range(m))

# A fixed point of prime order N on E0 for the DLP-transfer check.
G0 = E0.random_point() * 4
assert not G0.is_zero() and (N * G0).is_zero()

rows = []
t_start = time.time()
for idx, Q in enumerate(kernels):
    phi = E0t.isogeny(Q)
    Ct = phi.codomain()
    jv = Ct.j_invariant()
    a, b, C = descendant_with_trace(jv)
    shape = ell_primary_shape(Ct)
    # The char-2 quadratic twist fixes x, so the same kernel polynomial defines
    # an F_q-rational 263-isogeny E0 -> C.  gcd(263, N) = 1, so it is injective
    # on <G0> and carries the ECDLP from E0 onto C and back (via the dual).
    # check=False: the polynomial is already a verified kernel on the twist.
    phi0 = EllipticCurveIsogeny(E0, phi.kernel_polynomial(), check=False)
    assert phi0.codomain().j_invariant() == jv
    img = phi0(G0)
    transfer_ok = (not img.is_zero()) and (N * img).is_zero()
    level = "crater" if shape == ell else "floor"
    rows.append({
        "kernel_index": idx,
        "j_hex": hex(jv.to_integer()),
        "b_hex": hex(b.to_integer()),
        "a": a,
        "level": level,
        "conductor": 1 if level == "crater" else ell,
        "twist_263_primary_exponent": 1 if shape == ell else 2,
        "j_in_F2": jv in (K(0), K(1)),
        "ghs_magic_number": magic_number(b),
        "card": str(C.cardinality()),
        "dlp_transfer_263_isogeny_verified": transfer_ok,
        "orbit_key": frob_orbit_key(jv),
    })
    if idx % 32 == 0:
        print(f"{idx}/{len(kernels)} {time.time()-t_start:.1f}s level={level}")

orbits = Counter(r["orbit_key"] for r in rows if r["level"] == "floor")
orbit_ids = {k: i for i, k in enumerate(sorted(orbits))}
for r in rows:
    r["frobenius_orbit"] = orbit_ids.get(r.pop("orbit_key"), None)

floor = [r for r in rows if r["level"] == "floor"]
crater = [r for r in rows if r["level"] == "crater"]
assert len(crater) == 2 and len(floor) == h_order(ell)
assert len({r["j_hex"] for r in floor}) == len(floor)
assert all(r["card"] == str(n) for r in rows)

E0_magic = magic_number(K(1))
summary = {
    "field": {"q": "2^131", "modulus": str(MOD)},
    "E0": {"equation": "y^2 + xy = x^3 + 1", "ghs_magic_number": E0_magic},
    "shared_invariants": {
        "card": str(n), "trace": str(t), "N": str(N), "N_bits": N.nbits(), "cofactor": 4,
        "frobenius_discriminant": str(D), "conductor_Z_pi": str(f),
        "embedding_degree": str(k_emb), "embedding_degree_bits": k_emb.nbits(),
        "anomalous": n == q, "supersingular": t % 2 == 0,
        "twist_card": str(nt), "twist_factorization": str(nt_fact),
        "twist_largest_prime_bits": twist_prime.nbits(),
        "rho_log2_negation_only": float(round(log2(rho_plain), 2r)),
        "rho_log2_negation_plus_tau": float(round(log2(rho_frob), 2r)),
    },
    "levels": levels,
    "sweep_263": {
        "kernels": len(rows),
        "crater_neighbours": len(crater),
        "floor_descendants": len(floor),
        "floor_distinct_j": len({r["j_hex"] for r in floor}),
        "floor_frobenius_orbits": sorted(orbits.values()),
        "floor_a_counts": {str(k): v for k, v in Counter(r["a"] for r in floor).items()},
        "floor_ghs_magic_numbers": {str(k): v for k, v in Counter(r["ghs_magic_number"] for r in floor).items()},
        "all_dlp_transfers_verified": all(r["dlp_transfer_263_isogeny_verified"] for r in rows),
        "floor_twist_263_cyclic": all(r["twist_263_primary_exponent"] == 2 for r in floor),
        "crater_j_is_1": all(r["j_hex"] == "0x1" for r in crater),
        "seconds": round(time.time() - t_start, 1),
    },
    "descendants": rows,
}
json.dump(summary, open("results.json", "w"), indent=1, default=int)
with open("descendants.csv", "w") as fh:
    cols = ["kernel_index", "level", "conductor", "frobenius_orbit", "a", "b_hex", "j_hex",
            "twist_263_primary_exponent", "ghs_magic_number"]
    fh.write(",".join(cols) + "\n")
    for r in rows:
        fh.write(",".join(str(r[c]) for c in cols) + "\n")
print(json.dumps({k: v for k, v in summary.items() if k != "descendants"}, indent=1, default=int))
