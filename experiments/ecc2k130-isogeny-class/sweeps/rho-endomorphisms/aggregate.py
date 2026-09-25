"""Cross-check the searches and write per_curve.json + summary.json"""
import sys, json, math
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import common_rho as C
import ecc2k

N = C.N
L = lambda f: json.load(open(f))
st, c263, cok = L("structural.json"), L("cvp_O263.json"), L("cvp_OK.json")
e263_40, e263_72, eok40 = L("enum_O263_40.json"), L("enum_O263_72.json"), L("enum_OK_40.json")
cheap, toy = L("cheap_family.json"), L("orbit_union_toy.json")
tr = {lab: L("transfer_%s.json" % lab) for lab in ["A000", "A064", "B000", "B097"]}
S = {}

# --- cross-check enumeration vs CVP
def cvp_hits_below(cv, X):
    return sorted((int(r["x"]), int(r["y"])) for r in cv["kept_targets_norm_below_2^100"]
                  if int(r["norm"]) <= X and int(r["y"]) != 0)
enum_ok = sorted((r["x"], r["y"]) for r in eok40["hits_y_nonzero"])
S["OK_enum2^40_equals_cvp_set"] = enum_ok == cvp_hits_below(cok, 2 ** 40)
S["OK_enum2^40_hits"] = len(enum_ok)
# all O_K hits are +-tau^k : check eigenvalue = +-lam^k with norm 2^k
lam = C.LAM
ok_tau = True
for r in eok40["hits_y_nonzero"]:
    k = round(r["norm_log2"])
    e = (r["x"] + r["y"] * C.W_OK) % N
    ok_tau &= (int(r["norm"]) == 2 ** k) and e in (pow(lam, k, N), (-pow(lam, k, N)) % N)
S["OK_enum_hits_all_pm_tau^k"] = ok_tau
S["OK_cvp_kept_below_2^100"] = len(cok["kept_targets_norm_below_2^100"])
S["OK_cvp_kept_all_pm1_or_pm_tau^k"] = all(
    (int(r["norm"]) == 1) or (int(r["norm"]) == 2 ** round(r["norm_log2"]) and int(r["h"]) in
     (pow(lam, round(r["norm_log2"]), N), (-pow(lam, round(r["norm_log2"]), N)) % N))
    for r in cok["kept_targets_norm_below_2^100"])
S["O263_enum2^40_points"] = e263_40["points_enumerated_incl_y0"]
S["O263_enum2^40_hits_y_nonzero"] = len(e263_40["hits_y_nonzero"])
S["O263_enum2^72_points"] = e263_72["points_enumerated_incl_y0"]
S["O263_enum2^72_hits_y_nonzero"] = len(e263_72["hits_y_nonzero"])
S["O263_cvp_kept_below_2^100"] = [(r["x"], r["y"]) for r in c263["kept_targets_norm_below_2^100"]]
best = c263["smallest_norm_over_all_orders_3..2^20_y_nonzero"]
S["O263_cvp_min_norm_log2_orders_3_to_2^20"] = best["min_norm_y_nonzero_log2"]
S["O263_cvp_argmin"] = best
S["O263_consistent_enum_vs_cvp"] = (S["O263_enum2^72_hits_y_nonzero"] == 0 and best["min_norm_y_nonzero_log2"] > 72)

# --- tradeoff: min norm over orders 3 <= d < B (y != 0)
def tradeoff(cv, exclude=()):
    rows = []
    tab = [r for r in cv["per_order_table"] if r["d"] > 2 and r["d"] not in exclude]
    for kb in range(2, 21):
        sub = [r for r in tab if r["d"] < 2 ** kb]
        if sub:
            m = min(sub, key=lambda r: r["min_norm_y_nonzero_log2"])
            rows.append({"orders_below": "2^%d" % kb, "min_norm_log2": round(m["min_norm_y_nonzero_log2"], 3),
                         "at_order": m["d"]})
    return rows
S["O263_tradeoff"] = tradeoff(c263)
S["OK_tradeoff_excluding_131_262"] = tradeoff(cok, exclude=(131, 262))
S["OK_order131_min_norm_log2"] = [r["min_norm_y_nonzero_log2"] for r in cok["per_order_table"] if r["d"] == 131][0]
S["OK_best_nontau_orders_multiple_of_131"] = sorted(
    [(r["d"], round(r["min_norm_y_nonzero_log2"], 2)) for r in cok["per_order_table"]
     if r["d"] % 131 == 0 and r["d"] not in (131, 262)], key=lambda t: t[1])[:5]
# heuristic expectation of overall min in O_263: sqrt(|D|) N / (2 pi K)
K = c263["num_targets"]
S["O263_heuristic_expected_overall_min_log2"] = math.log2(math.sqrt(484183) * N / (2 * math.pi * K))
S["OK_heuristic_expected_num_elements_norm_below_2^100"] = (2 * math.pi * 2 ** 100 / math.sqrt(7)) * K / N
# --- cheap family & small-norm region
S["cheap_family_min_order_log2"] = cheap["cheap_family"]["min_order_log2"]
S["cheap_family_num"] = cheap["cheap_family"]["num_elements"]
S["norm_le_2^28_num"] = cheap["all_y_nonzero_norm_le_2^28"]["num_elements"]
S["norm_le_2^28_min_order_log2"] = cheap["all_y_nonzero_norm_le_2^28"]["smallest_orders"][0]["order_log2"]
S["codex_psi_order_log2"] = st["codex_psi_candidates"]["774,1"]["order_log2"]
S["pm2^s_order_log2"] = [st["O263_norm_2^k_elements"]["order_of_2_mod_N_log2"], st["O263_norm_2^k_elements"]["order_of_-2_mod_N_log2"]]
S["sandwich_263tau^k_min_order_log2"] = st["sandwich_263tau^k"]["min_order_log2"]
import os
for lm in (20, 22):
    fn = "cheap_complete_%d.json" % lm
    if os.path.exists(fn):
        cc = L(fn)
        S["sepdeg_search_%d" % lm] = {k: v for k, v in cc.items() if k != "hits_order_lt_2^20"}
        S["sepdeg_search_%d" % lm]["hits"] = len(cc["hits_order_lt_2^20"])
psi = {}
for i in range(6):
    psi.update(L("psi_all_%d.json" % i))
S["psi_all_curves_checked"] = len(psi)
S["psi_all_ok"] = sum(1 for v in psi.values() if v["ok"])
S["psi_sign_counts"] = {str(sg): sum(1 for v in psi.values() if v["signs"][0] == sg) for sg in (1, -1)}
va = L("verify_argmin.json")
S["argmin_pari_check"] = va
S["toy_orbit_union_all_equal"] = all(r["equal"] for r in toy)
S["transfer_all_ok"] = all(v["phi(Q) == [k]phi(P)"] and v["tau(phi(P)) == [lambda]phi(P)"] and v["codomain_Fq_isomorphic_to_E0"] for v in tr.values())

R262, R2, R1 = C.rho_log2(262), C.rho_log2(2), C.rho_log2(1)
S["rho_log2"] = {"class262": R262, "class2": R2, "class1": R1}
print(json.dumps(S, indent=1, default=str))
json.dump(S, open("summary.json", "w"), indent=1, default=str)

# --- per-curve
pc = {}
for lab in ecc2k.LABELS:
    rec = ecc2k.RECORDS[lab]
    if lab == "E0":
        pc[lab] = {"level": 1, "orbit": "crater", "End": "O_K = Z[(1+sqrt(-7))/2]",
                   "Aut_order": 2, "rho_group": "<-1, tau>", "class_size": 262,
                   "intrinsic_rho_log2": round(R262, 3),
                   "intrinsic_rho_formula": "sqrt(pi*N/(2*262))",
                   "practical_walk_reference_log2": 60.9,
                   "practical_walk_reference_source": "repo ecc2k130/runner/ENGINE.md (Bailey et al. iteration function)",
                   "min_norm_nontrivial_endo_with_eigen_order_lt_2^20_log2": 1.0,
                   "that_endomorphism": "tau (x->x^2), eigenvalue order 131; -tau order 262",
                   "effective_rho_log2": round(R262, 3)}
    else:
        pc[lab] = {"level": 263, "orbit": rec["orbit"], "frob_index": rec["frob_index"],
                   "End": "O_263 = Z[(1+263*sqrt(-7))/2]",
                   "Aut_order": 2, "rho_group": "<-1>", "class_size": 2,
                   "intrinsic_rho_log2": round(R2, 3),
                   "intrinsic_rho_formula": "sqrt(pi*N/(2*2))",
                   "min_norm_nontrivial_endo_with_eigen_order_lt_2^20_log2": round(best["min_norm_y_nonzero_log2"], 3),
                   "sepdeg_search": "no endomorphism with separable degree 2^b*m (b<=130, m<=2^%d, any inseparable degree) has eigenvalue order in (2, 2^20)" % max([lm for lm in (20, 22) if ("sepdeg_search_%d" % lm) in S and S["sepdeg_search_%d" % lm]["hits"] == 0] or [0]),
                   "cheapest_explicit_endo": "+-(774+omega_263) = 11-isogeny o Frob^16, eigenvalue order (N-1)/3 = 2^%.3f" % S["codex_psi_order_log2"],
                   "effective_rho_log2": round(R262, 3),
                   "effective_rho_note": "one F_q-rational 263-isogeny E -> E0 (ascending edge; exists for all 262 per ground_truth_check PASS D, demonstrated with DLP transfer on A000,A064,B000,B097) then <-1,tau> rho on E0",
                   "psi_774+omega263_verified_on_points": bool(psi[lab]["ok"]),
                   "transfer_demo_run": lab in tr}
json.dump(pc, open("per_curve.json", "w"), indent=1)
print("per_curve entries:", len(pc))
