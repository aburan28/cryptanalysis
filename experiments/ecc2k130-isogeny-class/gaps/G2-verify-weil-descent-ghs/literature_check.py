"""G2 item (10): check that the Hess 2003 Theorem 2 statement the sweep uses
(genus >= 2^128 + 1 for any Artin-Schreier construction over F_{2^131}/F_2) matches the
text in weil-descent-ghs/literature/, plus the MT eq.(5)/Remark 2 and Hess Thm 5/Cor 6
statements used for the genus rule.  Also recomputes the per-curve constants the sweep
stores next to the genus (2^128+1, rho baselines).

Plain python3:  timeout 2400 python3 literature_check.py
"""
import json, re, math, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
LIT = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/literature"
hess = open(f"{LIT}/hess-ghs-revisited-ec2003.txt", encoding="utf-8").read().split("\n")
mt = open(f"{LIT}/menezes-teske-corr2004-25.txt", encoding="utf-8").read().split("\n")


def find(lines, pat):
    return [i + 1 for i, l in enumerate(lines) if re.search(pat, l)]


res = {}
th2 = find(hess, r"^Theorem 2 ")
res["hess_theorem2_line"] = th2
i0 = th2[0] - 1
block = hess[i0:i0 + 14]
res["hess_theorem2_block_lines"] = [i0 + 1, i0 + 14]
txt = " ".join(block)
res["hess_thm2_hypotheses_present"] = {
    "deg(mf) >= 2": "deg(mf ) ≥ 2" in txt,
    "Delta_f cap K subset wp(F)": "∆f ∩ K ⊆ ℘(F )" in txt,
    "F(wp^-1(f, sigma f)) genus > 1": "genus greater than 1" in txt,
}
# the inequality line: "gEf pdeg(mf )−2 + 1 ≤ gC ≤ gEf · n (pdeg(mf ) − 1)/(p − 1)."
res["hess_thm2_lower_bound_text_present"] = any("pdeg(mf )−2 + 1 ≤ gC" in l for l in block)
res["hess_lower_bound_degree_remark_present"] = any(
    "smallest degree of a non-linear factor" in l for l in hess[i0:i0 + 20])
# numerical consequence for n = 131, p = 2, g_E = 1: m_f | t^131 - 1 = (t+1) Phi_131, Phi_131 irreducible
o = next(k for k in range(1, 200) if pow(2, k, 131) == 1)
res["ord_131(2)"] = o
min_deg_nonlinear = o                       # Phi_131 splits into (131-1)/o factors of degree o
res["min_deg_nonlinear_factor_t^131-1"] = min_deg_nonlinear
bound = 1 * 2 ** (min_deg_nonlinear - 2) + 1
res["hess_thm2_bound_for_n131"] = str(bound)
res["bound_equals_2^128+1"] = bound == 2 ** 128 + 1
pc = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/per_curve.json"))
vals = {v["genus_lower_bound_hess_artin_schreier_nontrivial"] for v in pc.values()}
res["sweep_stored_values"] = sorted(vals)
res["sweep_value_matches"] = vals == {str(2 ** 128 + 1)}
# Hess Thm 5 and Cor 6, MT eq (5) and Remark 2
th5 = find(hess, r"^Theorem 5 ")
res["hess_theorem5_line"] = th5
res["hess_thm5_formula_present"] = any("gC = 2deg(mf ) − 2deg(mf )−deg(mγ ) − 2deg(mf )−deg(mβ ) + 1" in l
                                       for l in hess[th5[0] - 1:th5[0] + 4])
cor6 = find(hess, r"^Corollary 6 ")
res["hess_cor6_line"] = cor6
res["hess_cor6_text"] = " ".join(hess[cor6[0] - 1:cor6[0] + 2]).strip()[:200]
eq3 = find(hess, r"lcm\(mγ , mβ , t \+ 1\) otherwise")
res["hess_eq3_line"] = eq3
eq5 = find(mt, r"g = 2t − 2t−s1 − 2t−s2 \+ 1")
res["mt_eq5_line"] = eq5
rem2 = find(mt, r"^Remark 2\.")
res["mt_remark2_line"] = rem2
res["mt_remark2_rule_present"] = any("2m−1 − 1, if (X + 1) - Ordb" in l for l in mt[rem2[0] - 1:rem2[0] + 16])
res["mt_decomposition_convention"] = [l.strip() for l in mt if "b = (γ1 γ2 )2" in l][:1]
res["hess_ghs_normalization"] = [l.strip() for l in hess if "y 2 + y = 1/x + α + β 1/2 x" in l][:1]
# rho baselines stored next to the genus
N = ecc2k.N
e0 = 0.5 * math.log2(math.pi * N / (4 * 131))
fl = 0.5 * math.log2(math.pi * N / 4)
res["rho_log2_E0_neg_tau"] = round(e0, 4)
res["rho_log2_floor_neg_only"] = round(fl, 4)
res["sweep_rho_values"] = sorted({(v["rho_baseline_log2_iterations"]) for v in pc.values()})
res["rho_values_match_2dp"] = sorted({round(e0, 2), round(fl, 2)}) == res["sweep_rho_values"]
res["short_quote"] = "\"any attack using an Artin-Schreier construction fails if deg(mf) is too large\" (Hess 2003, after Thm 2)"
json.dump(res, open(f"{OUT}/literature_check.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, indent=1, ensure_ascii=False))
