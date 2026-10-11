"""Collect the G2 outputs into results.json with per-claim verdicts (plain python3)."""
import json, hashlib, os
OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
WD = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs"
J = lambda f: json.load(open(os.path.join(OUT, f)))
pc = J("per_curve_G2.json"); S = pc["summary"]; C = pc["curves"]
wit = J("gghs_witness_check.json")["summary"]
ht = J("halving_and_trace.json")
wr = J("weil_restriction_poly.json")
lit = J("literature_check.json")
toy = J("toy_hess_genus.json")["summary"]
tf = open(os.path.join(OUT, "test_f2lin.log")).read().strip()
floor = [l for l in C if l != "E0"]
G130 = str(2 ** 130); G130m1 = str(2 ** 130 - 1)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


r = {"task": "G2-verify-weil-descent-ghs",
     "inputs": {"ground_truth.json_sha256": sha("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json"),
                "sweep_per_curve.json_sha256": sha(f"{WD}/per_curve.json"),
                "sweep_raw_magic_numbers.json_sha256": sha(f"{WD}/raw_magic_numbers.json"),
                "sweep_verify_independent.json_sha256": sha(f"{WD}/verify_independent.json"),
                "sweep_SHA256SUMS_all_OK_when_checked": True},
     "implementation": "own pure-Python F_2[z]/(z^131+z^13+z^2+z+1) arithmetic and F_2 Gaussian elimination (f2lin.py), "
                       "tested against Sage on 300 random field ops and 200 poly ops (test_f2lin.log: " + tf + "); "
                       "second implementation for Ord/m with Sage GF(2) matrices of the squaring map; nothing from "
                       "weil-descent-ghs/*.py imported",
     "curves_covered": len(C)}

items = {}
items["1_trace_b"] = {"counts": S["counts"]["trace_b"], "verdict": "CONFIRMED" if S["counts"]["trace_b"] == {"1": 263} else "MISMATCH"}
items["2_Ord_b"] = {"counts": S["counts"]["Ord_b"],
                    "verdict": "CONFIRMED" if S["counts"]["Ord_b"] == {"x + 1": 1, "x^131 + 1": 262} else "MISMATCH",
                    "note": "E0 (b=1): x+1; all 262 floor b are normal elements (Ord = x^131+1). Own Krylov and Sage d(M)v agree on 263/263."}
items["3_Ord_sqrt_b"] = {"counts": S["counts"]["Ord_sqrt_b"], "verdict": "CONFIRMED (equals Ord_b on all 263, as expected since sqrt = sigma^130 commutes with sigma)"}
items["4_magic_number"] = {"counts": S["counts"]["magic_number"],
                           "verdict": "CONFIRMED" if S["counts"]["magic_number"] == {"1": 1, "131": 262} else "MISMATCH"}
items["5_ghs_genus"] = {"counts": S["counts"]["ghs_genus"], "formula_counts": S["counts"]["ghs_genus_formula"],
                        "verdict": "CONFIRMED" if S["counts"]["ghs_genus"] == {"1": 1, G130: 262} else "MISMATCH",
                        "note": "x+1 | Ord_sqrt(b) on all 263 so the rule gives 2^(m-1): 1 for E0, 2^130 for every floor curve. "
                                "MT rule equals Hess Thm 5 with (gamma1, gamma2) = (1, sqrt b) on all 263."}
items["6_x131p1_and_gGHS"] = {
    "factorization": wit["factorization"], "ord_131(2)": wit["ord_131(2)"], "Phi131_irreducible_rabin": wit["Phi131_irreducible_rabin"],
    "sage_factor": "(x+1) * (deg 130)" if S["divisors_of_x131p1_degrees"] == [0, 1, 130, 131] else S["x131p1_factorization_sage"],
    "min_genus_over_all_type_pairs_except_(x+1,x+1)": wit["min_genus_Tr(a)=0_excluding_(x+1,x+1)"],
    "argument": wit["argument"],
    "per_curve_min_genus_counts": S["counts"]["gghs_min_genus"],
    "per_curve_min_pairs_counts": S["counts"]["gghs_min_pairs"],
    "stored_witnesses_checked": wit["witnesses_checked"], "stored_witnesses_all_ok": wit["witness_all_ok"],
    "E0_nontrivial_decomposition_ok": wit["E0_nontrivial_decomposition"]["g1*g2==sqrt(b)"] and wit["E0_nontrivial_decomposition"]["genus_match"],
    "verdict": "CONFIRMED" if (wit["witness_all_ok"] and S["counts"]["gghs_min_genus"] == {"1": 1, G130m1: 262}) else "MISMATCH",
    "minor_anomaly": "raw_magic_numbers.json lists gghs_min_pairs [[Phi131,Phi131],[Phi131,x+1]] for all 262 floor curves; "
                     "the pair (Phi131, x+1) is not realizable: Ord_gamma2 = x+1 forces gamma2 = 1, so gamma1 = sqrt(b) "
                     "with Ord x^131+1. Only (Phi131, Phi131) attains 2^130-1. The min genus value is unaffected."}
items["7_halving"] = {
    "all_263": S["counts"]["halving_criterion_consistent"],
    "random_a2=0": {k: ht["7b_random_curves"][k] for k in ("a2=0_curves", "a2=0_trace_b_split", "a2=0_card_mod_8_histogram",
                                                           "a2=0_criterion_holds_all", "a2=0_direct_halving_consistent_all")},
    "random_a2=1_control": {k: ht["7b_random_curves"][k] for k in ("a2=1_curves", "a2=1_card_mod_4_histogram", "a2=1_criterion_holds_all")},
    "verdict": "CONFIRMED" if (ht["7b_random_curves"]["a2=0_criterion_holds_all"] and S["counts"]["halving_criterion_consistent"] == {"True": 263}) else "MISMATCH",
    "note": "8 | #E iff Tr(b) = 0 (a2 = 0); #E = 4N with N odd for all 263 curves, so Tr(b) = 1 class-wide, and with b not in F_2 "
            "this alone forces Ord_b = x^131+1 (Ord_b | x^131+1, Tr(b) = Phi_131(sigma)(b) != 0 excludes Phi_131, b != 1 excludes x+1)."}
items["8_E0_trace_map"] = {"scalar": ht["8_scalar"], "points": len(ht["8_E0_points"]), "all_ok": ht["8_all_ok"],
                           "#E0(F_2)": ht["8_E0_F2_points"], "verdict": "CONFIRMED" if ht["8_all_ok"] else "MISMATCH"}
items["9_weil_restriction"] = {k: wr[k] for k in ("t_from_lucas", "t_equals_ground_truth", "card_equals_4N", "P_131(T)", "deg_P_R",
                                                   "P_divides_P_R", "deg_A", "A(1)", "A(1)==N", "P_R(1)==4N",
                                                   "A_irreducible_pari_polisirreducible", "A_irreducible_sage", "A_norm_route_equals_A",
                                                   "A_d_irreducible", "A_d_split", "toy_weil_restriction_formula")}
items["9_weil_restriction"]["verdict"] = "CONFIRMED" if (wr["A(1)==N"] and wr["A_irreducible_pari_polisirreducible"] and wr["deg_A"] == 260
                                                           and wr["P_divides_P_R"] and wr["A_norm_route_equals_A"]) else "MISMATCH"
items["9_weil_restriction"]["note"] = ("Res(E) ~ E0/F_2 x A over F_2 for all 263 curves (same P_131, Tate). A simple over F_{2^d} for every "
                                       "d with 131 !| d (computed d = 1..24, 65, 130; Galois argument for all), but A ~ E^130 over F_q.")
items["10_literature"] = {k: lit[k] for k in ("hess_theorem2_line", "hess_thm2_hypotheses_present", "hess_thm2_lower_bound_text_present",
                                              "hess_lower_bound_degree_remark_present", "hess_thm2_bound_for_n131", "sweep_value_matches",
                                              "hess_theorem5_line", "hess_thm5_formula_present", "hess_cor6_line", "mt_eq5_line",
                                              "mt_remark2_line", "mt_remark2_rule_present", "short_quote")}
items["10_literature"]["verdict"] = ("CONFIRMED with caveat: Thm 2 gives g_C >= g_E p^(deg m_f - 2) + 1 under three hypotheses "
                                     "(deg m_f >= 2, Delta_f cap K in wp(F), genus of F(wp^-1(f, sigma f)) > 1). With n = 131, m_f | t^131 - 1 "
                                     "= (t+1)Phi_131, so deg m_f >= 2 implies deg m_f >= 130 and g_C >= 2^128 + 1. The bound covers "
                                     "constructions satisfying those hypotheses, not every conceivable cover.")
items["supplementary_toy_genus_formula"] = dict(toy, verdict="CONFIRMED" if (toy["all_match_subfield_sum"] and toy["all_match_direct"] and toy["all_rule_match"]) else "MISMATCH",
                                                note="Hess Thm 5 / MT rule vs Sage genus of every quadratic subextension (summed) for n = 3, 5, 7; "
                                                     "direct Sage compositum genus only for t <= 2. n = 5 is the closest analogue of 131 "
                                                     "(x^5+1 = (x+1)Phi_5, Phi_5 irreducible): b normal gives genus 16 = 2^4, (Phi5,Phi5) gives 15.")
r["items"] = items

claims = {
    "C1_magic_numbers (E0 m=1, floor m=131)": items["4_magic_number"]["verdict"],
    "C2_Tr(b)=1 and Ord_b=x^131+1 on every floor curve": "CONFIRMED" if items["1_trace_b"]["verdict"] == items["2_Ord_b"]["verdict"] == "CONFIRMED" else "MISMATCH",
    "C3_GHS genus 2^130; gGHS min 2^130-1; explicit decompositions": items["6_x131p1_and_gGHS"]["verdict"] if items["5_ghs_genus"]["verdict"] == "CONFIRMED" else "MISMATCH",
    "C4_E0 trace map kills the N-subgroup": items["8_E0_trace_map"]["verdict"],
    "C5_Res(E) ~ E0/F_2 x A, A simple dim 130, A(1)=N": items["9_weil_restriction"]["verdict"],
    "Hess Thm 2 bound 2^128+1 as stated": "CONFIRMED (with hypotheses caveat)",
}
r["claim_verdicts"] = claims
r["per_curve_mismatches_numeric"] = S["mismatches_vs_sweep_numeric_fields"]
r["per_curve_min_pair_listing_differences"] = {"count": len(S["min_pairs_differences"]),
                                               "all_same": len({json.dumps(v) for v in S["min_pairs_differences"].values()}) == 1,
                                               "example": next(iter(S["min_pairs_differences"].items()))}
r["hardness_effect"] = ("GHS/gGHS Weil descent gives no speed-up on any of the 263 curves: floor curves' smallest cover over F_2 "
                        "from GHS has genus 2^130 and from any gGHS decomposition >= 2^130 - 1 (any Hess AS construction >= 2^128 + 1); "
                        "E0's genus-1 GHS cover is E0/F_2 whose map kills the N-subgroup, and its nontrivial decompositions give "
                        ">= 2^130 - 1. Reduction 0 bits; rho baselines stand (log2 60.81 for E0 with tau, 64.33 negation only).")
r["files"] = sorted(f for f in os.listdir(OUT) if not f.startswith(".") and f not in ("__pycache__", "SHA256SUMS"))
json.dump(r, open(os.path.join(OUT, "results.json"), "w"), indent=1)
print(json.dumps(r["claim_verdicts"], indent=1))
print("numeric mismatches:", len(r["per_curve_mismatches_numeric"]))
