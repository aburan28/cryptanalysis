"""Merge raw/pure_results.json (own AGM + point orders), raw/sage_crosscheck.json (Sage/PARI) and
the Pratt certificates into per_curve.json keyed by ground-truth label.  Plain python3."""
import json
import math

D = "/Volumes/SSD990/ecdlp-hardness-work/group-order/"
gt = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json"))
pure = json.load(open(D + "raw/pure_results.json"))["curves"]
sage = json.load(open(D + "raw/sage_crosscheck.json"))["curves"]
q = 2 ** 131
N = int(gt["meta"]["N"])
t = int(gt["meta"]["t"])
P114 = 19678316408850118605767852657510239
assert q + 1 + t == 2 * 263 ** 2 * P114 and q + 1 - t == 4 * N

rho_neg = 0.5 * math.log2(math.pi * N / 4)
rho_tau = 0.5 * math.log2(math.pi * N / (4 * 131))
rho_tw_neg = 0.5 * math.log2(math.pi * P114 / 4)
rho_tw_tau = 0.5 * math.log2(math.pi * P114 / (4 * 131))

out = {}
problems = []
for c in gt["curves"]:
    lab = c["label"]
    pr, sg = pure[lab], sage[lab]
    gt_order = int(c["order_pari"])
    order_ok = (pr["j_ok"] and pr["agm_order_is_4N"] and pr["agm_prec80_in_Z2"] and pr["agm_prec96_in_Z2"]
                and pr["agm_two_precisions_agree"] and pr["order_proof_4N"] and sg["order_ok"]
                and gt_order == 4 * N)
    struct_ok = pr["two_primary"] == "Z/4" and pr["T2_on_curve"] and sg["cyclic_Z4N"]
    tw = pr["twist"]
    twist_ok = pr["twist_order_ok"] and sg["twist_order_ok"] and tw["ok_sylow"] and int(c["twist_order_pari"]) == q + 1 + t
    pure_tw_struct = ("Z/263 x Z/(2*263*P114)" if tw["sylow263"] == "(Z/263)^2"
                      else "cyclic Z/(2*263^2*P114)" if tw["sylow263"] == "Z/263^2" else "?")
    # Sylow-2 of the twist is Z/2 (2 || #E', one 2-torsion point), Sylow-P114 is Z/P114, so the twist is
    # cyclic iff its 263-Sylow is; tw["cyclic_point"] (a sampled point of exact order q+1+t) is extra evidence.
    twist_struct_agree = (pure_tw_struct == sg["twist_structure"])
    is_E0 = lab == "E0"
    rec = {
        "order_ok": bool(order_ok),
        "order": str(4 * N),
        "order_factorization": "2^2 * N (N prime, 129.0 bits)",
        "structure": "Z/4 x Z/N = Z/4N (cyclic)" if struct_ok else "?",
        "two_primary": pr["two_primary"],
        "two_torsion_points": 1,
        "twist_order_ok": bool(twist_ok),
        "twist_order": str(q + 1 + t),
        "twist_factorization": "2 * 263^2 * P114 (P114 = %d, prime, 113.9 bits)" % P114,
        "twist_structure": sg["twist_structure"] if twist_struct_agree else "DISAGREE",
        "evidence": {
            "agm_trace_prec80": pr["agm_t_prec80"], "agm_trace_prec96": pr["agm_t_prec96"],
            "agm_norm_in_Z2": pr["agm_prec80_in_Z2"] and pr["agm_prec96_in_Z2"],
            "points_sampled": len(pr["points_sampled"]),
            "points_exact_order_4N": sum(p["order_4N"] for p in pr["points_sampled"]),
            "two_part_order_counts": pr["two_part_order_counts"],
            "explicit_order4_point_x_eq_b^(1/4)": pr["P4_exists"] and pr["P4_double_is_T2"] and pr["P4_order_4"],
            "sage_default_algorithm": sg["sage_algorithm"], "sage_card_ok": int(sg["sage_card"]) == 4 * N,
            "pari_ellgroup": sg["pari_group"], "pari_twist_ellgroup": sg["pari_twist_group"],
            "twist_P114_point": tw["P114_point"], "twist_sylow263": tw["sylow263"],
            "twist_no_order4_point": not tw["P4_exists_on_twist"],
            "twist_sampled_point_of_exact_order_q+1+t": tw["cyclic_point"],
            "ground_truth_order_pari_matches": gt_order == 4 * N,
        },
        "pohlig_hellman": {
            "largest_prime_subgroup_bits": 129.0,
            "cofactor": 4,
            "ph_saving_bits": 0.0,
            "note": "PH splits the DLP into log mod 4 (2 bits, trivial) and log mod N; the N part is the whole large-prime part, so PH gives no reduction",
            "generic_rho_log2_iterations_on_this_curve_alone": round(rho_tau if is_E0 else rho_neg, 2),
            "automorphisms_used": "negation + tau (orbit 2*131)" if is_E0 else "negation only (no F_2-model, no tau)",
            "context_not_this_sweep": None if is_E0 else "floor curve is F_q-263-isogenous to E0 (ground_truth_check); the dual isogeny is injective on the order-N part (263 != N), so this ECDLP maps to E0's (about 2^%.2f with tau); the isogeny-transfer dimension quantifies that" % rho_tau,
        },
        "twist_pohlig_hellman": {
            "largest_prime_subgroup_bits": round(math.log2(P114), 2),
            "generic_rho_log2_iterations": round(rho_tw_tau if is_E0 else rho_tw_neg, 2),
            "note": "relevant only to twist/invalid-point attacks on x-only implementations, not to the ECDLP on E",
        },
    }
    if not (order_ok and struct_ok and twist_ok and twist_struct_agree):
        problems.append(lab)
    out[lab] = rec

json.dump(out, open(D + "per_curve.json", "w"), indent=1)
from collections import Counter
print("curves", len(out), "problems", problems)
print("structure", Counter(r["structure"] for r in out.values()))
print("twist_structure", Counter(r["twist_structure"] for r in out.values()))
print("rho", round(rho_neg, 3), round(rho_tau, 3), "twist rho", round(rho_tw_neg, 3), round(rho_tw_tau, 3))
print("two-part order counts total", sum(sum(r["evidence"]["two_part_order_counts"].values()) for r in out.values()),
      Counter(k for r in out.values() for k, v in r["evidence"]["two_part_order_counts"].items() for _ in range(v)))
