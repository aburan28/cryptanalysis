# p-levels, part 2:
#  - tau (the F_2-Frobenius of E0) modulo p, computed in F_{p^2} = F_p[x]/(x^2+x+2) (no use of t):
#    checks tau^131 == c = t/2 in F_p, ord(tau) = 131*r, tau not in F_p  (=> E0[p] points need F_{2^(131 r)},
#    Frobenius orbits of p-lines have size 131).
#  - per-curve file for the 263 ground-truth curves (their p-structure) + levels.json for the unlabeled levels.
import json, sys, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
T0 = time.time()
q, t, N, f, p = ecc2k.q, ecc2k.t, ecc2k.N, ecc2k.f, ecc2k.p
num = json.load(open("raw/p_levels_numbers.json"))
r = Integer(num["r = ord_p(c)"]); c_int = Integer(num["c = t/2 mod p"])
Fp = GF(p)
R.<x> = Fp[]
g = x^2 + x + 2
assert g.is_irreducible()          # (-7|p) = -1  <=>  x^2+x+2 irreducible mod p (disc -7)
F2.<a> = GF(p^2, modulus=g)       # a = tau mod p
tau131 = a^131
out = {}
out["x^2+x+2 irreducible mod p"] = True
out["tau^131 in F_p"] = bool(tau131.polynomial().degree() <= 0)
out["tau^131 == c"] = bool(tau131 == F2(c_int))
out["tau in F_p"] = bool(a.polynomial().degree() <= 0)
# order of tau in F_{p^2}^*: must be 131*r
o = a.multiplicative_order()
out["ord(tau) in F_{p^2}^*"] = str(o)
out["ord(tau) == 131*r"] = bool(o == 131*r)
# image of tau in F_{p^2}^*/F_p^* has order 131: tau^131 in F_p, tau not in F_p, 131 prime
out["ord of tau in F_{p^2}^*/F_p^* == 131"] = bool(out["tau^131 in F_p"] and not out["tau in F_p"])
assert out["tau^131 == c"] and out["ord(tau) == 131*r"] and not out["tau in F_p"]
# same for 263 (split): tau mod 263 lies in F_263 (x^2+x+2 has roots mod 263)
R263.<y> = GF(263)[]
rts = (y^2 + y + 2).roots(multiplicities=False)
out["tau mod 263 roots (split)"] = [int(z) for z in rts]
out["tau^131 mod 263 for both roots"] = [int(z^131) for z in rts]
out["t/2 mod 263"] = int(GF(263)(t)/2)
for k, v in out.items(): print(k, "=", v)

# ---------------- per-curve (263 labeled curves) ----------------
K, curves = ecc2k.load()
rx = r // 2
rho_neg = float(num["log2 rho neg only"]); rho_e0 = float(num["log2 rho E0 (neg+tau)"])
per = {}
for lab in ecc2k.LABELS:
    recd = ecc2k.RECORDS[lab]
    E = curves[lab]
    j = E.j_invariant()
    j_in_F2 = bool(j^2 == j)
    lvl263 = 1 if recd["orbit"] == "crater" else 263
    per[lab] = {
        "orbit": recd["orbit"],
        "conductor": "1" if lvl263 == 1 else "263",
        "j_in_F2 (computed)": j_in_F2,
        "tau_endomorphism_available": j_in_F2,
        "p_volcano_position": "crater (conductor prime to p)",
        "pi_on_E[p]": f"scalar c = {c_int} (t/2 mod p)",
        "num_p_isogenies": str(p + 1),
        "num_p_isogenies_Fq_rational": str(p + 1),
        "num_p_isogenies_horizontal": int(0),
        "p_isogenies_land_on_level": "p (conductor p)" if lvl263 == 1 else "263p (conductor 263p)",
        "p_kernel_point_field_degree_over_Fq": str(r),
        "p_kernel_x_field_degree_over_Fq": str(rx),
        "log2_rho_intrinsic": rho_e0 if j_in_F2 else rho_neg,
        "note": "p-structure derived from End(E) (conductor 1 or 263, prime to p) and the global computation of c, r; "
                "only j_in_F2 is recomputed per curve here",
    }
    assert (lab == "E0") == j_in_F2
json.dump(per, open("per_curve.json", "w"), indent=1, default=str)

levels = {
    "LEVEL_p": {
        "conductor": "p", "End": "Z + p O_K", "num_classes_h": str(p + 1),
        "log2_num_classes": float(log(p + 1, 2)),
        "frobenius_sigma_orbits": str((p + 1)//131), "orbit_size": int(131),
        "j_in_F2": False, "min_nonscalar_endo_log2_degree": float(log(7*p^2/4, 2)),
        "log2_rho_intrinsic": rho_neg,
        "ascending_p_kernel": "unique F_q-rational p-subgroup = ker(pi - c) on E[p]; points over F_{q^r}, x over F_{q^(r/2)}",
        "full_E[p]_field_degree_over_Fq": str(r * p),
        "r": str(r), "r_x": str(rx),
        "reachable_from_E0_by": "exactly one p-isogeny (all p+1 p-isogenies of E0 descend here, one per class)",
        "explicit_curve_known": False,
    },
    "LEVEL_263p": {
        "conductor": "263p", "End": "Z + 263p O_K", "num_classes_h": str(262*(p + 1)),
        "log2_num_classes": float(log(262*(p + 1), 2)),
        "class_group": "Z/262 x Z/(p+1) (exponent p+1 checked via prime-form orders)",
        "frobenius_sigma_orbits": str(262*(p + 1)//131), "orbit_size": int(131),
        "j_in_F2": False, "min_nonscalar_endo_log2_degree": float(log(7*(263*p)^2/4, 2)),
        "log2_rho_intrinsic": rho_neg,
        "ascending_263_kernel": "points over F_{q^2} (eigenvalue t/2 = -1 mod 263) -> cheap step to level p (does not help)",
        "ascending_p_kernel": "points over F_{q^r}, x over F_{q^(r/2)} -> to level 263",
        "explicit_curve_known": False,
    },
}
json.dump({"tau_mod_p_checks": out, "levels": levels}, open("levels.json", "w"), indent=1, default=str)
print("elapsed", round(time.time() - T0, 1), "s; wrote per_curve.json, levels.json")
