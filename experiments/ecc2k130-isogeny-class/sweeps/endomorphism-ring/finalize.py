# Merge per_curve_stage1.json + phi_roots_*_of_4.json (+ irreducibility sample, transfer demo)
# into per_curve.json with a level verdict and the list of criteria that certify it.
# Plain python3.
import json, glob, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
D = "/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/"
st = json.load(open(D + "per_curve_stage1.json"))
phi = {}
for fn in sorted(glob.glob(D + "phi_roots_*_of_4.json")):
    phi.update(json.load(open(fn)))
irr = {}
for fn in sorted(glob.glob(D + "phi_irreducible_*.json")):
    irr.update(json.load(open(fn)))
alg = json.load(open(D + "algebra_output.json"))
LABELS = ecc2k.LABELS
missing_phi = [l for l in LABELS if l not in phi]
out = {}
for lab in LABELS:
    r = dict(st[lab])
    ph = phi.get(lab)
    if ph:
        r["phi263_Fq_rational_263_isogenies"] = ph["num_Fq_roots_with_mult"]
        r["phi263_distinct_Fq_roots"] = ph["num_distinct_Fq_roots"]
        r["phi263_mult_root_j=1"] = ph["mult_of_root_Y=1"]
    if lab in irr:
        r["phi263_cofactor_irreducible_deg263"] = irr[lab]["irreducible_deg263"]
    methods = []
    if lab == "E0":
        methods.append("M1 tau: (x,y)->(x^2,y^2) satisfies tau^2+tau+2=0 on E0 (checked on points); "
                       "Z[tau] has discriminant -7 = d_K, so O_K = Z[tau] <= End(E0) <= O_K")
        if r["sylow263_structure_q2"] == "Z/263 x Z/263" and r["sylow263_pari"] == "Z/263xZ/263":
            methods.append("M2 torsion: E0(F_{q^2})[263^inf] = (Z/263)^2 (PARI ellgroup; own arithmetic + Weil pairing)")
        if r["H_minus7_mod2_at_j_is_zero(j==1)"]:
            methods.append("M3 CM: j = 1 is the root of H_{-7} = X + 3375 = X + 1 (mod 2)")
        if ph and ph["num_Fq_roots_with_mult"] == 264 and ph.get("Fq_roots_are_1_and_exactly_the_262_floor_j"):
            methods.append("M4 modular polynomial: Phi_263(1,Y) mod 2 has all 264 roots in F_q "
                           "(Y=1 double = 2 horizontal; the 262 floor j simple = 262 descending): crater")
        level = 1 if len(methods) >= 2 else "UNCERTIFIED"
        r.update(level=level, end_ring="O_K = Z[(1+sqrt(-7))/2] = Z[tau]", conductor="1")
    else:
        c1 = r["HD_mod2_at_j_is_zero"] and not r["H_minus7_mod2_at_j_is_zero(j==1)"]
        if c1:
            methods.append("C1 CM: H_{-7*263^2}(j) = 0 mod 2 and j != 1 (Deuring: conductor 263 is prime to 2, so End = O_263)")
        c2 = r["sylow263_structure_q2"].startswith("Z/263^2") and r["sylow263_pari"] == "Z/263^2"
        c3 = r.get("velu_up_to_j1") is True
        if c2 and c3:
            methods.append("C2+C3 torsion+isogeny: E(F_{q^2})[263^inf] = Z/263^2 cyclic (PARI ellgroup and own arithmetic), "
                           "so pi is not scalar on E[263] and 263 | conductor; an F_q-rational 263-isogeny to j=1 (Velu) "
                           "gives p-part(cond) = p-part(cond E0) = 1 and v_263(cond) <= 1; so conductor = 263")
        c4 = bool(ph) and ph["num_Fq_roots_with_mult"] == 1 and ph.get("only_Fq_root_is_j=1") is True
        if c4:
            methods.append("C4 volcano degree: Phi_263(j,Y) mod 2 has exactly one F_q-root (Y=1, simple): one rational "
                           "263-isogeny, to E0; a crater vertex here has 264. So 263-level = floor")
        level = 263 if (c1 and c2 and c3 and c4) else ("263 (C4 pending)" if (c1 and c2 and c3) else "UNCERTIFIED")
        r.update(level=level, end_ring="O_263 = Z + 263*O_K" if level == 263 else "?", conductor="263" if level == 263 else "?")
    r["end_ring_cert_methods"] = methods
    r["num_independent_criteria"] = len(methods)
    out[lab] = r
floor = [l for l in LABELS if l != "E0"]
summary = {
    "E0_level": out["E0"]["level"], "E0_num_criteria": out["E0"]["num_independent_criteria"],
    "floor_certified_level_263": sum(1 for l in floor if out[l]["level"] == 263),
    "floor_total": len(floor),
    "floor_min_num_criteria": min(out[l]["num_independent_criteria"] for l in floor),
    "floor_sylow_q2_cyclic": sum(1 for l in floor if out[l]["sylow263_pari"] == "Z/263^2" and out[l]["sylow263_structure_q2"].startswith("Z/263^2")),
    "floor_j_degree_131": sum(1 for l in floor if out[l]["j_degree_over_F2"] == 131),
    "floor_HD_root": sum(1 for l in floor if out[l]["HD_mod2_at_j_is_zero"]),
    "floor_velu_up_to_j1": sum(1 for l in floor if out[l].get("velu_up_to_j1")),
    "floor_phi263_single_rational_isogeny": sum(1 for l in floor if out[l].get("phi263_Fq_rational_263_isogenies") == 1),
    "phi_missing": missing_phi,
    "irreducible_deg263_sample": {k: v["irreducible_deg263"] for k, v in irr.items()},
    "curves_per_level": {"c=1": 1, "c=263": 262,
                         "c=p": alg["class_numbers"]["p"]["h_formula"], "c=263p": alg["class_numbers"]["263p"]["h_formula"]},
}
json.dump(out, open(D + "per_curve.json", "w"), indent=1)
json.dump(summary, open(D + "summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
