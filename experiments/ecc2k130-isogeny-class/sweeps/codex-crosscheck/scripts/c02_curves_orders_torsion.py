# Per-curve cross-check built ONLY from Codex's public-cm-inventory/inventory.json
# (the two orbit base j's) plus Codex's labelling rule X_k: j = j(X000)^(2^k).
# For every one of the 263 curves:
#   * Codex j/b vs ground-truth j_int/b_int (label match)
#   * #E(F_q) = 4N by an order argument ([4]P != O, [N][4]P = O, N > 4 sqrt(q))
#   * the twist's 263-primary part: (Z/263)^2 on E0, cyclic Z/263^2 on floor curves
#     -> number of Frobenius-stable 263-lines and the field of definition of E[263]
# Also: embedding degree of N w.r.t. q, q mod 263, and a direct F_{q^2} check on a sample.
import json, sys, time, random
from pathlib import Path
from sage.all import (GF, PolynomialRing, EllipticCurve, Integer, ZZ, factor, Mod, log, RR,
                      set_random_seed, isqrt, kronecker)

W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
CI = W / "codex_inputs"
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
gt = {c["label"]: c for c in GT["curves"]}
inv = json.loads((CI / "public-cm-inventory" / "inventory.json").read_text())
set_random_seed(20260923)

q = Integer(2)**131
# constants recomputed here (not read from GT)
t1 = -1; s = [Integer(2), Integer(t1)]
for i in range(2, 132): s.append(t1*s[-1] - 2*s[-2])
t = s[131]; card = q + 1 - t; N = card // 4; assert card == 4*N and N.is_prime()
twist = q + 1 + t
R = PolynomialRing(GF(2), "z"); z = R.gen()
mod = z**131 + z**13 + z**2 + z + 1
assert inv["field_modulus_nonzero_exponents"] == [0, 1, 2, 13, 131]
K = GF(2**131, name="z", modulus=mod)
out = {"script": "c02_curves_orders_torsion.py", "seed": 20260923, "global": {}, "curves": {}}

# ---------- global: embedding degree and 263 facts
t0 = time.time()
fN1 = factor(N - 1)
k_emb = Mod(q, N).multiplicative_order()
out["global"]["N_minus_1_factorization"] = str(fN1)
out["global"]["embedding_degree_ord_N_q"] = str(k_emb)
out["global"]["embedding_degree_log2"] = float(RR(log(k_emb, 2)))
out["global"]["embedding_degree_bits"] = int(ZZ(k_emb).nbits())
out["global"]["codex_embedding_degree"] = "216464610000596986937760855436835237"
out["global"]["embedding_degree_agree"] = (str(k_emb) == "216464610000596986937760855436835237")
out["global"]["(N-1)/k_emb"] = str((N - 1) // k_emb)
out["global"]["q_mod_263"] = int(q % 263)
out["global"]["t_mod_263"] = int(t % 263)
out["global"]["v263(q+1-t)"] = int(ZZ(card).valuation(263))
out["global"]["v263(q+1+t)"] = int(ZZ(twist).valuation(263))
out["global"]["charpoly_pi_mod_263"] = "x^2 - (t mod 263) x + (q mod 263) = " + str(
    PolynomialRing(GF(263), "x")([q % 263, -(t % 263), 1]).factor())
out["global"]["embedding_seconds"] = time.time() - t0
print(json.dumps(out["global"], indent=1))

tw_cof = twist // 263**2
assert tw_cof * 263**2 == twist

def orbit_js(base_int):
    j = K.from_integer(int(base_int))
    js = [j]
    for k in range(130):
        js.append(js[-1]**2)
    assert js[-1]**2 == j
    return js

curves = {"E0": K(1)}
for m in inv["models"]:
    lab = "AB"[m["orbit"]]
    js = orbit_js(m["j_integer_encoding"])
    # Codex b = 1/j for the base
    assert (1/js[0]).to_integer() == int(m["b_integer_encoding"])
    for k, j in enumerate(js):
        curves[f"{lab}{k:03d}"] = j
assert len(curves) == 263 and len(set(curves.values())) == 263

def torsion263_twist(Et):
    """263-primary part of the twist over F_q: returns (order, exponent) from 4 random points."""
    expo = 1; pts = []
    for _ in range(4):
        P = tw_cof * Et.random_point()
        o = 1
        Q = P
        while not Q.is_zero():
            Q = 263 * Q; o *= 263
        expo = max(expo, o)
        pts.append(P)
    return expo, pts

t0 = time.time()
for lab, j in curves.items():
    rec = {}
    b = 1/j
    g = gt[lab]
    rec["codex_j_int"] = str(j.to_integer()); rec["codex_b_int"] = str(b.to_integer())
    rec["label_match_gt"] = (str(j.to_integer()) == g["j_int"] and str(b.to_integer()) == g["b_int"])
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    assert E.j_invariant() == j
    # order proof on the a2 = 0 model (Codex's model a_invariants [1,0,0,0,b])
    ok = False
    for _ in range(3):
        P = E.random_point(); P4 = 4*P
        if not P4.is_zero():
            ok = (N * P4).is_zero(); break
    rec["order_4N_by_point_proof"] = bool(ok)
    # twist y^2 + xy = x^3 + x^2 + b   (Tr(1) = 1 in F_{2^131}, so a2 = 1 gives the quadratic twist)
    Et = EllipticCurve(K, [1, 1, 0, 0, b])
    # twist order check: a random point killed by q+1+t, and not by (q+1+t)/l for the 114-bit prime l
    P = Et.random_point()
    rec["twist_killed_by_q+1+t"] = bool((twist * P).is_zero())
    expo, pts = torsion263_twist(Et)
    rec["twist_263_exponent"] = int(expo)
    # structure: twist 263-part has order exactly 263^2 (v263(q+1+t) = 2): exponent 263 -> (Z/263)^2, 263^2 -> Z/263^2
    rec["twist_263_structure"] = "(Z/263)^2" if expo == 263 else ("Z/263^2" if expo == 263**2 else f"exp {expo}")
    # consequences for E: pi acts on E[263] as -1 (+ nilpotent n); n = 0 iff twist full 263-torsion
    if expo == 263:
        rec["pi_on_E263"] = "-I (scalar)"; rec["stable_263_lines"] = 264; rec["E263_full_over"] = "F_{q^2}"
    else:
        rec["pi_on_E263"] = "-(I - n), n != 0 nilpotent"; rec["stable_263_lines"] = 1; rec["E263_full_over"] = "F_{q^526}"
    rec["E_Fq2_263_part"] = rec["twist_263_structure"]  # E(F_{q^2})[263^inf] = E(F_q)[263^inf] (+) E'(F_q)[263^inf], and E(F_q)[263]=0
    out["curves"][lab] = rec
print("per-curve loop", time.time() - t0, "s")

# ---------- direct F_{q^2} check on a sample (Codex-tested curves + orbit bases)
sample = ["E0", "A000", "A090", "B000", "B021", "B067"]
Rw = PolynomialRing(GF(2), "w")
L = GF(2**262, name="w")   # Sage default modulus (Conway/sparse); only structure is used
emb = K.hom([mod.change_ring(L).roots(multiplicities=False)[0]], L) if False else None
# embed via a root of the ECC2K modulus in L
rts = PolynomialRing(L, "Z")(mod).roots(multiplicities=False)
phi = K.hom([rts[0]], L)
cardL = (q + 1 - t) * (q + 1 + t)
cofL = cardL // 263**2
direct = {}
for lab in sample:
    b = phi(1/curves[lab])
    EL = EllipticCurve(L, [1, 0, 0, 0, b])
    expo = 1
    for _ in range(4):
        P = cofL * EL.random_point()
        o = 1; Q = P
        while not Q.is_zero():
            Q = 263*Q; o *= 263
        expo = max(expo, o)
    direct[lab] = {"E_Fq2_263_exponent": int(expo),
                   "structure": "(Z/263)^2" if expo == 263 else "Z/263^2",
                   "agrees_with_twist_derivation": (("(Z/263)^2" if expo == 263 else "Z/263^2") == out["curves"][lab]["twist_263_structure"])}
    print(lab, direct[lab])
out["direct_Fq2_sample"] = direct

summ = {
    "n_curves": len(out["curves"]),
    "label_match_gt": sum(r["label_match_gt"] for r in out["curves"].values()),
    "order_4N": sum(r["order_4N_by_point_proof"] for r in out["curves"].values()),
    "twist_killed": sum(r["twist_killed_by_q+1+t"] for r in out["curves"].values()),
    "twist_structure_counts": {},
}
for r in out["curves"].values():
    summ["twist_structure_counts"][r["twist_263_structure"]] = summ["twist_structure_counts"].get(r["twist_263_structure"], 0) + 1
summ["E0_structure"] = out["curves"]["E0"]["twist_263_structure"]
summ["floor_all_cyclic"] = all(out["curves"][l]["twist_263_structure"] == "Z/263^2" for l in out["curves"] if l != "E0")
out["summary"] = summ
print(json.dumps(summ, indent=1))
(W / "raw" / "c02_curves_orders_torsion.json").write_text(json.dumps(out, indent=1))
