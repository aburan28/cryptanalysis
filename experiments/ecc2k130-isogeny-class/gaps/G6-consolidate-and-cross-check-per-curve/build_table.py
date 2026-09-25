"""G6 steps (3) and (4): consolidated per-curve hardness table.

Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 python3 build_table.py
Needs nt_checks.json, crosscheck_report.json, pairing_c3_check.json (same directory).
Writes per_curve_hardness.json: one row per curve (E0, A000..A130, B000..B130) plus two
level rows (conductor p and 263p).  Every field is {value, provenance[{file,key}],
verified_by[dirs], recomputed_here?, crosscheck_ids?, note?}.  verified_by lists only
independent verification directories whose on-disk outputs cover that label (per-label)
or the whole class (marked "(class-wide)"); G6's own recomputation is in recomputed_here.
"""
import json, os, math, hashlib, time
HERE = os.path.dirname(os.path.abspath(__file__))
W = "/Volumes/SSD990/ecdlp-hardness-work"
T0 = time.time()

def P(*a):
    return os.path.join(W, *a)

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

INPUTS = {}
def jl(rel):
    INPUTS[rel] = sha(P(rel))
    return json.load(open(P(rel)))

gt = jl("ground_truth/ground_truth.json")
REC = {c["label"]: c for c in gt["curves"]}
LABELS = [c["label"] for c in gt["curves"]]
SW = ["group-order", "endomorphism-ring", "pairing-transfer", "weil-descent-ghs", "rho-endomorphisms",
      "transport-263", "index-calculus", "codex-crosscheck", "p-levels", "literature", "toy-analogue-a"]
sw = {s: jl(s + "/per_curve.json") for s in SW}
nt = json.load(open(os.path.join(HERE, "nt_checks.json")))
cc = json.load(open(os.path.join(HERE, "crosscheck_report.json")))
pc3 = json.load(open(os.path.join(HERE, "pairing_c3_check.json")))
for f in ("nt_checks.json", "crosscheck_report.json", "pairing_c3_check.json"):
    INPUTS["gaps/G6-consolidate-and-cross-check-per-curve/" + f] = sha(os.path.join(HERE, f))
cov = cc["verify_coverage"]["per_field_label"]
RHO_E0 = nt["rho_log2"]["E0_neg_tau_class_262"]; RHO_NEG = nt["rho_log2"]["neg_only_class_2"]
N = int(nt["N"]); P114 = int(nt["P114"]); p = int(nt["p"])

def pv(f, k):
    return {"file": f, "key": k}

def covd(field, label):
    return list(cov.get(field, {}).get(label, []))

def fld(value, prov, verified_by=(), recomputed=None, checks=None, note=None):
    d = {"value": value, "provenance": prov, "verified_by": sorted(set(verified_by))}
    if recomputed is not None:
        d["recomputed_here"] = recomputed
    if checks:
        d["crosscheck_ids"] = checks
    if note:
        d["note"] = note
    return d

def passed(l, ids):
    """True iff every listed crosscheck id exists and has no disagreement for this label"""
    return all(i in cc["checks"] for i in ids) and not any(d["check"] in ids for d in dis_by_label.get(l, []))

dis_by_label = {}
for d in cc["disagreements"]:
    dis_by_label.setdefault(d["label"], []).append({k: d[k] for k in ("check", "file", "key", "value", "reference_value")})

# optional sibling-gap verifications (only used if present and consistent)
G2 = None
g2p = P("gaps/G2-verify-weil-descent-ghs/per_curve_G2.json")
if os.path.exists(g2p):
    try:
        G2 = json.load(open(g2p)); INPUTS["gaps/G2-verify-weil-descent-ghs/per_curve_G2.json"] = sha(g2p)
    except Exception:
        G2 = None
def g2_confirms(label, m):
    if not G2 or "curves" not in G2 or label not in G2["curves"]:
        return False
    r = G2["curves"][label]
    for k in ("magic_number", "m"):
        if k in r:
            return r[k] == m
    return False

CLASS_RHO_VERIFY = ["verify/transport-263/C4-audit (class-wide: rho log2 formula recomputed to 90 digits)",
                    "verify/transport-263/C4-recompute (class-wide: rho log2 formula recomputed)",
                    "verify/toy-analogue-a/C1-audit (class-wide: toy analogues, native floor/E0 rho ratio ~ sqrt(n))",
                    "verify/toy-analogue-a/C1-recompute (class-wide: toy analogues)",
                    "verify/toy-analogue-a/C4-audit (class-wide: toy rho iteration counts vs theory)",
                    "verify/toy-analogue-a/C4-recompute (class-wide: toy rho iteration counts vs theory)"]
CLASS_TRANSPORT_VERIFY = ["verify/toy-analogue-a/C2-audit (class-wide: toy transport + E0 rho == E0 rho)",
                          "verify/toy-analogue-a/C2-recompute (class-wide: toy transport + E0 rho == E0 rho)",
                          "verify/transport-263/C4-audit (class-wide: transport op counts and cost increment)"]
IC_CLASS_VERIFY = ["verify/index-calculus/C2-codex-run08-is-winners-curse-audit: (class-wide)",
                   "verify/index-calculus/C2-codex-run08-is-winners-curse-recompute: (class-wide)",
                   "verify/index-calculus/C3-descendant-choice-equals-subspace-choice-audit: (class-wide)",
                   "verify/index-calculus/C3-descendant-choice-equals-subspace-choice-recompute: (class-wide)",
                   "verify/index-calculus/C5-tau-factor-base-E0-only-and-unrealisable-at-131-audit: (class-wide)",
                   "verify/index-calculus/C5-tau-factor-base-E0-only-and-unrealisable-at-131-recompute: (class-wide)"]

cm = jl("index-calculus/costmodel.json")["table"]
def best(prefix):
    ks = [k for k in cm if k.startswith(prefix)]
    k = min(ks, key=lambda k_: cm[k_]["log2_total"])
    return k, cm[k]["log2_total"]
IC_BEST = {pre: best(pre) for pre in ("mitm|plain", "mitm|GGMP-hyp(E0)", "table|plain", "table|GGMP-hyp(E0)", "free|plain", "free|GGMP-hyp(E0)")}
rt08 = jl("verify/redteam/RT0-8-1/s1_structure.json")
rt08m = jl("verify/redteam/RT0-8-1/s3_models.json")
tsum = jl("transport-263/summary.json")
ca = jl("verify/transport-263/C4-audit/count_ops.json")

rows = {}
for l in LABELS:
    g = REC[l]; lvl = g["level"]; floor = l != "E0"
    rc = cc["recomputed_per_curve"][l]
    go, er, pt, wd = sw["group-order"][l], sw["endomorphism-ring"][l], sw["pairing-transfer"][l], sw["weil-descent-ghs"][l]
    re_, tr, ic, lit, ta, pl = sw["rho-endomorphisms"][l], sw["transport-263"][l], sw["index-calculus"][l], sw["literature"][l], sw["toy-analogue-a"][l], sw["p-levels"][l]
    row = {"label": l, "orbit": g["orbit"], "frob_index": g["frob_index"],
           "curve": fld({"a_invariants": [1, g["a2"], 0, 0, "b"], "b_int": g["b_int"], "j_int": g["j_int"]},
                        [pv("ground_truth/ground_truth.json", "curves[label=%s].{a2,b_int,j_int}" % l)],
                        covd("curve_model", l) + ["ground_truth_check" if floor else "ground_truth_check (E0 constants)"],
                        recomputed={"j*b==1": rc["j_times_b_is_1"], "j_in_F2": rc["j_in_F2"], "H_D(j)==0 mod 2": rc["HD_mod2_at_j_is_zero"]},
                        checks=["B0_a2", "B1_j_times_b", "B2_j_in_F2_iff_E0", "B2b_HD_root", "B3_frobenius_labels", "B4_b_raw_magic", "B5_j_derive_floor", "B6_j_codex_C1"])}
    row["conductor"] = fld({"conductor": str(lvl), "volcano_level": "crater" if not floor else "floor of the 263-volcano",
                            "End": er["end_ring"]},
                           [pv("ground_truth/ground_truth.json", "curves[label=%s].level" % l),
                            pv("endomorphism-ring/per_curve.json", "%s.conductor" % l), pv("endomorphism-ring/per_curve.json", "%s.end_ring" % l)],
                           covd("level_263_structure", l) + covd("level_phi263", l) + ["ground_truth_check"],
                           recomputed={"H_D(j)=0 mod 2 (conductor-263 CM)": rc["HD_mod2_at_j_is_zero"], "j in F_2 (O_K, Koblitz)": rc["j_in_F2"]},
                           checks=["A3_level", "E1_conductor", "E2_end_ring", "E3_j_degree", "E4_HD_root", "E6_phi263_rational", "E6b_phi263_roots", "E7_sylow263"],
                           note="Sylow-263 of E(F_{q^2}): %s; F_q-rational 263-isogenies: %s" % (er["sylow263_structure_q2"], er["phi263_Fq_rational_263_isogenies"]))
    row["group_order"] = fld({"order": g["order_pari"], "factorization": "2^2 * N", "N": str(N), "N_log2": nt["N_log2"],
                              "structure": go["structure"], "trace_t": nt["t"]},
                             [pv("ground_truth/ground_truth.json", "curves[label=%s].order_pari" % l), pv("group-order/per_curve.json", "%s.order" % l),
                              pv("group-order/per_curve.json", "%s.structure" % l), pv("group-order/per_curve.json", "%s.evidence.agm_trace_prec96" % l)],
                             covd("order", l), recomputed={"card (Lucas t, nt_checks)": nt["card"], "N_prime_proof": nt["primes_proof_True"]["N"], "checks_passed": passed(l, ["C1_order", "C2_trace", "C4_structure", "C6_card_Fq2"])},
                             checks=["C1_order", "C2_trace", "C4_structure", "C6_card_Fq2"])
    row["pohlig_hellman"] = fld({"largest_prime_subgroup_bits": go["pohlig_hellman"]["largest_prime_subgroup_bits"],
                                 "cofactor": go["pohlig_hellman"]["cofactor"], "gain_bits": go["pohlig_hellman"]["ph_saving_bits"]},
                                [pv("group-order/per_curve.json", "%s.pohlig_hellman" % l)], covd("order", l),
                                recomputed={"N_prime_proof": nt["primes_proof_True"]["N"], "hasse_multiples_of_N": nt["hasse_multiples_of_N"], "checks_passed": passed(l, ["C5_PH"])}, checks=["C5_PH"],
                                note="PH splits off only the 2-bit Z/4 part; the order-N part is the whole problem")
    row["embedding_degree"] = fld({"k": pt["embedding_degree_N"], "log2_k": nt["embedding_degree_log2"], "(N-1)/k": nt["(N-1)/k"]},
                                  [pv("pairing-transfer/per_curve.json", "%s.embedding_degree_N" % l)],
                                  covd("embedding_degree", l), recomputed={"ord_N(q) (Sage)": nt["embedding_degree_ord_N_q"]},
                                  checks=["D1_embedding_degree"], note="MOV/Frey-Rueck target F_{q^k} with k ~ 2^117.4: infeasible")
    tate_ver = covd("tate_263_QN_trivial", l)
    rec_tate = None
    if l in pc3["pairing_c3_check_gp"]["results"]:
        rec_tate = {"G6 pairing_c3_check.gp (PARI) t_263(P,Q_N)=1": pc3["pairing_c3_check_gp"]["results"][l].get("tate_P_QN_all_1")}
    row["pairing_263"] = fld({"tate_t263(P,Q_N)": pt["pairing_263"]["tate_t263(P,Q_N)"], "structure_E(F_q2)[263^inf]": pt["pairing_263"]["structure_E(L)[263^inf]"]},
                             [pv("pairing-transfer/per_curve.json", "%s.pairing_263" % l)], tate_ver, recomputed=rec_tate, checks=["D3_tate_QN", "E7_sylow263"],
                             note="the 263-part pairing carries no information about log mod N")
    m = rc["mq_magic_number"]
    ghs_ver = ["gaps/G2-verify-weil-descent-ghs"] if g2_confirms(l, m) else []
    row["ghs"] = fld({"magic_number_m": wd["magic_number"], "ghs_genus": wd["ghs_genus"], "ghs_genus_log2": wd["ghs_genus_log2"],
                      "gghs_min_genus": wd["genus_lower_bound"], "cover_carries_N_subgroup": wd["ghs_cover_carries_N_subgroup"],
                      "hardness_reduction_log2": wd["hardness_reduction_log2"]},
                     [pv("weil-descent-ghs/per_curve.json", "%s.{magic_number,ghs_genus,ghs_genus_log2,genus_lower_bound,ghs_cover_carries_N_subgroup,hardness_reduction_log2}" % l)],
                     ghs_ver, recomputed={"m (Menezes-Qu rank)": m, "deg Ord_b": rc["conj_rank_b"], "Tr(b)": rc["Tr_b"],
                                          "gGHS witness checks passed": passed(l, ["G7_gghs_witness"]), "m/genus/Ord/Tr checks passed": passed(l, ["G1_ghs_m", "G2_ord_b", "G3_ghs_genus", "G4_trace_b"])},
                     checks=["G1_ghs_m", "G2_ord_b", "G3_ghs_genus", "G4_trace_b", "G7_gghs_witness", "G8_gghs_pairs_realizable"],
                     note=("no verify/weil-descent-ghs directory exists; values recomputed here (pure-python GF(2^131)). " +
                           ("E0: genus-1 cover is E0/F_2 itself (order 4), cannot carry N" if not floor else
                            "genus 2^130 (gGHS 2^130-1): useless. raw_magic_numbers lists an unrealizable min pair (Phi131,x+1) - see errata")))
    native = RHO_E0 if not floor else RHO_NEG
    row["native_rho_log2"] = fld({"log2_iterations": round(native, 2), "exact": native,
                                  "equivalence_class": re_["rho_group"] + " (size %d)" % re_["class_size"],
                                  "formula": "sqrt(pi*N/(2*%d))" % re_["class_size"]},
                                 [pv("rho-endomorphisms/per_curve.json", "%s.intrinsic_rho_log2" % l), pv("literature/per_curve.json", "%s.native_log2_iterations" % l),
                                  pv("group-order/per_curve.json", "%s.pohlig_hellman.generic_rho_log2_iterations_on_this_curve_alone" % l),
                                  pv("transport-263/per_curve.json", "%s.rho_direct_log2" % l), pv("toy-analogue-a/per_curve.json", "%s.native_rho_log2_iters" % l)],
                                 CLASS_RHO_VERIFY, recomputed={"nt_checks 200-bit": native}, checks=["R1_rho_native", "R4_class_size"],
                                 note=("E0: Frobenius tau (eigenvalue order 131) + negation" if not floor else
                                       "floor: j has degree 131 over F_2, no tau; only +-1 (rho-endomorphisms found no cheap endomorphism with small eigenvalue order). "
                                       "No verify/rho-endomorphisms directory exists (gaps/G1 in progress)"))
    if not floor:
        eff_status = "native (crater curve, no transport needed)"
        eff_ver = CLASS_RHO_VERIFY
    else:
        eff_status = ("transport implemented and verified: unique F_q-rational ascending 263-isogeny to E0 (kernel x in F_q, points over F_{q^2}), "
                      "build %s M/%s S/%s I, eval per point %s (sweep counter; audit: A=788)" %
                      (tr["build_ops"]["M"], tr["build_ops"]["S"], tr["build_ops"]["I"],
                       "%dM+%dS+%dI+%dA" % (tr["eval_ops_per_point"]["M"], tr["eval_ops_per_point"]["S"], tr["eval_ops_per_point"]["I"], tr["eval_ops_per_point"]["A"])))
        eff_ver = covd("transport", l) + CLASS_TRANSPORT_VERIFY
    row["effective_rho_log2"] = fld({"log2_iterations": round(RHO_E0, 2), "exact": RHO_E0,
                                     "transport_stored_effective_log2": tr["effective_log2"],
                                     "transport_increment_bits": tr.get("effective_minus_E0_log2", 0.0),
                                     "transport_status": eff_status,
                                     "native_minus_effective_bits": round(native - RHO_E0, 4)},
                                    [pv("transport-263/per_curve.json", "%s.effective_log2" % l), pv("rho-endomorphisms/per_curve.json", "%s.effective_rho_log2" % l),
                                     pv("literature/per_curve.json", "%s.effective_log2_iterations_best_known" % l), pv("toy-analogue-a/per_curve.json", "%s.effective_log2_iters" % l)],
                                    eff_ver, recomputed=({"kernel checks passed (131 distinct x, b+v+v^2=1, Tr(x+b/x^2)=1, x-doubling 131-cycle, Frobenius-equivariant, v equal in 5 audit files)":
                                                              passed(l, ["T1_kernel_shape", "T2_b_v_v2", "T3_kernel_not_rational", "T4_doubling_cycle", "T5_kernel_frobenius", "T6_v_cross_source"]),
                                                          "transport_v_int": rc.get("transport_v_int")} if floor else None),
                                    checks=["R1_rho_effective", "R2_transport_increment", "T1_kernel_shape", "T2_b_v_v2", "T3_kernel_not_rational", "T4_doubling_cycle", "T5_kernel_frobenius", "T6_v_cross_source", "T7_transport_flags"] if floor else ["R1_rho_effective"])
    ic_models = {"mitm|plain": IC_BEST["mitm|plain"][1], "table|plain": IC_BEST["table|plain"][1]}
    if not floor:   # a Frobenius-invariant (GGMP) factor base exists only on E0 (hypothetical, verify/index-calculus C5)
        ic_models.update({"mitm|GGMP-hyp(E0)": IC_BEST["mitm|GGMP-hyp(E0)"][1], "table|GGMP-hyp(E0)": IC_BEST["table|GGMP-hyp(E0)"][1]})
    row["index_calculus"] = fld({"Tr_b": ic["Tr_b"], "canon_density": {k: ic["density_k%d" % k] for k in (8, 10, 12, 14, 16)},
                                 "max_abs_z": ic["max_abs_z"],
                                 "best_realizable_cost_model_log2": ic_models,
                                 "min_modelled_log2": min(v for v in ic_models.values()),
                                 "note": ("summation-polynomial index calculus: factor-base densities match the null model (max |z| %.2f); "
                                          "best modelled realizable decomposition 2^%.2f (mitm) / 2^%.2f (table), both above rho; "
                                          "free-PDP-oracle bounds (2^%.2f plain, 2^%.2f GGMP-hyp) assume a zero-cost point decomposition that no measured engine achieves" %
                                          (ic["max_abs_z"], IC_BEST["mitm|plain"][1], IC_BEST["table|plain"][1], IC_BEST["free|plain"][1], IC_BEST["free|GGMP-hyp(E0)"][1]))
                                          + ("; tau-invariant factor base exists only on E0 (hypothetical GGMP)" if not floor else "")
                                          + "; caveat: the model covers m <= 7 and its table variant still decreases at m = 7 (%s), so the minimum is over the modelled range only (gaps/G3 audits this cost model)"
                                          % ", ".join("m%d %.2f" % (mm, cm["table|plain|m%d" % mm]["log2_total"]) for mm in (5, 6, 7))},
                                [pv("index-calculus/per_curve.json", "%s.{Tr_b,density_k*,max_abs_z}" % l),
                                 pv("index-calculus/costmodel.json", "table[%s,%s,%s]" % (IC_BEST["mitm|plain"][0], IC_BEST["table|plain"][0], IC_BEST["free|plain"][0]))],
                                covd("index_calculus_density", l) + covd("Tr_b", l) + IC_CLASS_VERIFY,
                                recomputed={"Tr(b)": rc["Tr_b"], "canon count k8": rc.get("canon_count_k8"), "canon count k10": rc.get("canon_count_k10")},
                                checks=["G4_trace_b", "I1_density", "I2_counts_vs_audit", "I3_counts_recount"])
    tw_struct = go["twist_structure"]
    row["twist"] = fld({"twist_order": g["twist_order_pari"], "factorization": "2 * 263^2 * P114", "P114": str(P114),
                        "structure": tw_struct, "twist_rho_log2_on_P114": go["twist_pohlig_hellman"]["generic_rho_log2_iterations"],
                        "invalid_curve_note": ("x-only E0 implementation queried on the twist leaks k mod 2*263*P114 (log2 %.2f); "
                                               "k mod 263^2 is NOT obtainable because E0'(F_q) = Z/(2*263*P114) x Z/263 (RT0-8 correction); residual %.2f bits"
                                               % (rt08["G"]["E0_impl_leak_modulus_log2"], rt08["G"]["E0_impl_residual_log2"])) if not floor else
                                              ("x-only floor implementation queried on its cyclic twist leaks k mod 2*263^2*P114 (log2 %.1f >= log2 N): full key at twist-rho cost 2^%.2f (via E0' with tau) or 2^%.2f (direct)"
                                               % (rt08["G"]["floor_impl_leak_modulus_log2"], rt08m["M1_raw_output"]["floor_impl_via_E0t"], rt08m["M1_raw_output"]["floor_impl_no_transport_neg_only"]))},
                       [pv("ground_truth/ground_truth.json", "curves[label=%s].twist_order_pari" % l), pv("group-order/per_curve.json", "%s.twist_structure" % l),
                        pv("group-order/per_curve.json", "%s.twist_pohlig_hellman" % l), pv("verify/redteam/RT0-8-1/s1_structure.json", "G"),
                        pv("verify/redteam/RT0-8-1/s3_models.json", "M1_raw_output")],
                       covd("twist_order", l) + covd("level_263_structure", l) + ["verify/redteam/RT0-8-0 (class-wide)", "verify/redteam/RT0-8-1 (class-wide)"],
                       recomputed={"twist (nt_checks)": nt["twist_card"], "P114_prime_proof": nt["primes_proof_True"]["P114"], "checks_passed": passed(l, ["C3_twist", "C4_twist_group", "C4_twist_structure", "C5_twist_PH", "R5_twist_rho"]), "twist rho": nt["rho_log2"]["twist_P114_neg_tau_class_262" if not floor else "twist_P114_neg_only_class_2"]},
                       checks=["C3_twist", "C4_twist_group", "C4_twist_structure", "C5_twist_PH", "R5_twist_rho"],
                       note="relevant only to implementation (invalid-curve / x-only) attacks, not to the ECDLP on E itself")
    row["p_structure"] = fld({"pi_on_E[p]": pl["pi_on_E[p]"], "p_isogenies": pl["num_p_isogenies"], "lands_on": pl["p_isogenies_land_on_level"],
                              "kernel_point_field_degree": pl["p_kernel_point_field_degree_over_Fq"]},
                             [pv("p-levels/per_curve.json", l)], ["verify/p-levels/C1-audit (class-wide)", "verify/p-levels/C1-recompute (class-wide)",
                                                                   "verify/p-levels/C3-audit (class-wide)", "verify/p-levels/C3-recompute (class-wide)"],
                             recomputed={"c = t/2 mod p": nt["c_t_over_2_mod_p"], "r = ord_p(c)": nt["r_ord_p_c"]}, checks=["P1_c", "P2_num_p_isog", "P3_horizontal", "P4_r", "P5_land"])
    row["small_isogeny_neighbours"] = fld(lit["small_isogeny_neighbours_computed"], [pv("literature/per_curve.json", "%s.small_isogeny_neighbours_computed" % l)],
                                          [], recomputed={"Phi_l mod 2 roots (Sage)": {k: v["Fq_roots_with_mult"] for k, v in nt["small_isogeny_neighbours"][l].items()}},
                                          checks=["L1_neighbours", "L2_11_isogeny_shift16"] if floor else ["L1_neighbours"],
                                          note="no verify/literature output on disk (verify/literature/L1-recompute is empty); recomputed here")
    row["hardness_summary"] = {"best_known_attack": ("parallel Pollard rho with negation + Frobenius on E0" if not floor else
                                                     "map (P,Q) to E0 by the ascending 263-isogeny, then rho with negation + Frobenius on E0"),
                               "log2_iterations": round(RHO_E0, 2),
                               "native_log2_iterations": round(native, 2),
                               "no_shortcut_from": ["Pohlig-Hellman (gain 0)", "MOV/FR (k ~ 2^117.4)", "GHS/gGHS (genus >= 2^130 or cover of order 4)",
                                                    "index calculus (cost model >= 2^%.2f over its range m <= 7; see index_calculus.note)" % min(ic_models.values()), "263-pairing (trivial on N-part)"],
                               "provenance": [pv("per_curve_hardness.json", "curves.%s.{effective_rho_log2,native_rho_log2,pohlig_hellman,embedding_degree,ghs,index_calculus}" % l)]}
    row["crosscheck"] = {"disagreements_for_this_label": dis_by_label.get(l, []),
                         "source": "gaps/G6-consolidate-and-cross-check-per-curve/crosscheck_report.json"}
    rows[l] = row

# ------------------------------------------------------------------ level rows
lv = jl("p-levels/levels.json")["levels"]
concl = jl("p-levels/conclusions.json")
litlv = jl("literature/levels.json")
rt15 = jl("verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_summary.json")
rt15core = jl("verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_core.json")
rt15k = jl("verify/redteam/RT15-presented-level-p-and-263p-curves-0/s2_kani_params.json")
rt201 = jl("verify/redteam/RT2-01-1/raw/s6_summary.json")
rt200 = jl("verify/redteam/RT2-01-0/raw/s3_cost.json")
c4a = jl("verify/p-levels/C4-audit/c4_numbers.json")
c5r = jl("verify/index-calculus/C5-tau-factor-base-E0-only-and-unrealisable-at-131-recompute:/check131.json")
rec_path = P("verify/b2-reconcile/levels_reconciled.json")
reconciled = json.load(open(rec_path)) if os.path.exists(rec_path) else None
if reconciled is not None:
    INPUTS["verify/b2-reconcile/levels_reconciled.json"] = sha(rec_path)

dim2_eff = []
for case in ("proposer_dim2_c81", "best_split_le_1e5", "best_split_le_1e6"):
    for model, v in rt201[case].items():
        if isinstance(v, dict) and "eff_iters_C100_C1000_C10000" in v:
            dim2_eff.extend(v["eff_iters_C100_C1000_C10000"])
dim2_corr = [v["eff_iter_corrected"] for k, v in rt200["proposer_cases"]["dim2_c81_A=29.71.137.179"].items() if isinstance(v, dict) and "eff_iter_corrected" in v]
v4best = rt15k["V4_two_squares_dim4"]["best"]["ell^G"]
conditional = {
    "log2_iterations_range": [round(min([rt15["dim2 optimistic (best a<2^30)"]["log2 total (E0 rho + transport), rho-its"], min(dim2_eff), min(dim2_corr)]), 2),
                              rt15["dim2 Robert-notes (best a<2^30)"]["log2 total (E0 rho + transport), rho-its"]],
    "range_basis": "low end = min over the dim-2 audit figures (RT15 dim2 optimistic, RT2-01-1 min, RT2-01-0 corrected min); high end = RT15 dim2 Robert-notes cost model. "
                   "RT2-01-1 cost models with a large per-step constant C (up to 10^4) reach %.3f; dim-4 (RT15 optimistic) %.2f; dim-8 (Thm 1 as proved) %.2f." %
                   (max(dim2_eff), rt15["dim4 optimistic (C4 example M)"]["log2 total (E0 rho + transport), rho-its"], rt15["dim8 optimistic (C4 example M; Thm 1 as proved)"]["log2 total (E0 rho + transport), rho-its"]),
    "assumption": "Galbraith (2024) dimension-2 Kani-lemma transport of a level-p/263p instance to E0; not implemented in characteristic 2 (unimplemented, conditional)",
    "components": {
        "RT15 dim2 optimistic total": rt15["dim2 optimistic (best a<2^30)"]["log2 total (E0 rho + transport), rho-its"],
        "RT15 dim2 Robert-notes total": rt15["dim2 Robert-notes (best a<2^30)"]["log2 total (E0 rho + transport), rho-its"],
        "RT15 dim4 optimistic total": rt15["dim4 optimistic (C4 example M)"]["log2 total (E0 rho + transport), rho-its"],
        "RT15 dim8 (Thm 1 as proved) total": rt15["dim8 optimistic (C4 example M; Thm 1 as proved)"]["log2 total (E0 rho + transport), rho-its"],
        "RT15-0 two-squares dim4 best effective (c=5)": v4best["effective_log2_its_c5"],
        "RT2-01-1 dim2 cases, eff iterations over C in {100,1000,10000} and 4 cost models (min,max)": [min(dim2_eff), max(dim2_eff)],
        "RT2-01-0 dim2_c81 eff_iter_corrected over C in {9,100,1000,10000}": dim2_corr,
    },
    "provenance": [pv("verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_summary.json", "dim2 optimistic / dim2 Robert-notes / dim4 / dim8 .log2 total"),
                   pv("verify/redteam/RT15-presented-level-p-and-263p-curves-0/s2_kani_params.json", "V4_two_squares_dim4.best.ell^G.effective_log2_its_c5"),
                   pv("verify/redteam/RT2-01-1/raw/s6_summary.json", "*.eff_iters_C100_C1000_C10000"),
                   pv("verify/redteam/RT2-01-0/raw/s3_cost.json", "proposer_cases.dim2_c81_A=29.71.137.179.*.eff_iter_corrected")],
    "verified_by": ["verify/redteam/RT15-presented-level-p-and-263p-curves-0", "verify/redteam/RT15-presented-level-p-and-263p-curves-1",
                    "verify/redteam/RT2-01-0", "verify/redteam/RT2-01-1", "verify/p-levels/C4-audit"],
}
c4_note = {"claimed transport lower bounds (log2 F_q ops)": {"sqrt-Velu over F_{q^(r/2)}": c4a["log2(sqrt(p) * r/2)  [claimed sqrt-Velu LB]"],
                                                             "cofactor multiplication": c4a["log2(131 * r^2)      [claimed cofactor LB, y-coords over F_{q^r}]"],
                                                             "Phi_p route": c4a["log2(p^3)            [Phi_p route]"]},
           "audit additions (log2 F_q ops)": {"x-only ladder over F_{q^(r/2)}": c4a["log2(131 * (r/2)^2)  [x-only ladder over F_{q^{r/2}} instead]"],
                                              "Couveignes/De Feo O~(l^2) (not listed in C4)": c4a["log2(p^2)            [Couveignes/De Feo O~(l^2) route, not listed in C4]"],
                                              "trace-Velu, linear model": c4a["trace-Velu: log2 F_q-ops, linear model (r per F_{q^r} op)"],
                                              "trace-Velu, M(r)=r log r model": c4a["trace-Velu: log2 F_q-ops, M(r)=r*log2(r) model"],
                                              "Galbraith Thm 1 O~(p^(1/2))": c4a["log2 sqrt(p) (Galbraith Thm 1: O~(N^(1/2)) F_q-ops)"]},
           "provenance": pv("verify/p-levels/C4-audit/c4_numbers.json", "log2(...) keys")}

def level_row(key, lvkey, conductor, litkey, h_key, h_log2_key, endo_log2_key, conclkey, nf_key):
    L = lv[lvkey]
    nf = c5r["norm_form_min"][nf_key]["min_norm_nonscalar"]
    fcond = p if nf_key == "p" else int(nt["f"])
    # nonscalar elements of Z + f*O_K are a + c*f*w (c != 0), w = (1+sqrt(-7))/2, norm a^2 + a*c*f + 2*c^2*f^2;
    # the minimum (c = +-1, a = -(f+-1)/2) is (1 + 7 f^2)/4 for odd f; brute-check the two nearest a as well
    nf_mine = (1 + 7 * fcond * fcond) // 4
    nf_brute = min(a_ * a_ + a_ * fcond + 2 * fcond * fcond for a_ in (-(fcond // 2), -(fcond // 2) - 1))
    row = {
        "label": "level_" + key, "conductor": fld(conductor, [pv("p-levels/levels.json", "levels.%s.conductor" % lvkey), pv("literature/levels.json", "%s.conductor" % litkey)],
                                                 ["verify/p-levels/C2-audit", "verify/p-levels/C2-recompute"], recomputed={"f": nt["f"], "p": nt["p"], "p_prime_proof": nt["primes_proof_True"]["p"]}),
        "End": fld(L["End"], [pv("p-levels/levels.json", "levels.%s.End" % lvkey), pv("literature/levels.json", "%s.end_ring" % litkey)], []),
        "class_number": fld(L["num_classes_h"], [pv("p-levels/levels.json", "levels.%s.num_classes_h" % lvkey), pv("literature/levels.json", "%s.class_number" % litkey)],
                            ["verify/p-levels/C2-audit", "verify/p-levels/C2-recompute", "verify/p-levels/C5-audit"],
                            recomputed={"h (formula, kronecker(-7,p)=%d)" % nt["kronecker_-7_p"]: nt[h_key], "log2": nt[h_log2_key]},
                            note="consistent" if str(nt[h_key]) == str(L["num_classes_h"]) == str(litlv[litkey]["class_number"]) else "MISMATCH"),
        "explicit_curves_known": fld(False, [pv("p-levels/levels.json", "levels.%s.explicit_curve_known" % lvkey) if "explicit_curve_known" in L else pv("literature/levels.json", "%s.explicitly_constructible" % litkey),
                                              pv("p-levels/conclusions.json", "constructing_any_level_p_or_263p_curve")], ["verify/redteam/RT15-presented-level-p-and-263p-curves-1"],
                                     note="random search: 2^%.2f trials per level-p curve, 2^%.2f per level-p-or-263p curve (RT15 core)" %
                                          (rt15core["log2 (2q/(p+1)) random (b,a2) trials per level-p curve"], rt15core["log2 (2q/(263(p+1))) random trials per level-p-or-263p curve"])),
        "native_rho_log2": fld({"log2_iterations": round(L["log2_rho_intrinsic"], 2), "exact": L["log2_rho_intrinsic"], "equivalence_class": "<-1> (j not in F_2, no tau)",
                                "min_nonscalar_endomorphism_degree_log2": L["min_nonscalar_endo_log2_degree"]},
                               [pv("p-levels/levels.json", "levels.%s.{log2_rho_intrinsic,min_nonscalar_endo_log2_degree}" % lvkey), pv("literature/levels.json", "global.rho_log2.neg_only")],
                               ["verify/p-levels/C4-audit", "verify/index-calculus/C5-tau-factor-base-E0-only-and-unrealisable-at-131-recompute:"],
                               recomputed={"rho neg-only (nt_checks)": RHO_NEG, "min nonscalar norm (1+7f^2)/4": str(nf_mine), "equals brute min over nearest a": nf_mine == nf_brute,
                                           "log2": math.log2(nf_mine), "equals verify/index-calculus C5-recompute norm_form_min": nf_mine == int(nf),
                                           "matches p-levels levels.json log2 (1e-9)": abs(math.log2(nf_mine) - L["min_nonscalar_endo_log2_degree"]) < 1e-9}),
        "effective_rho_log2": {
            "sweep_figure": fld({"log2_iterations": concl["per_level"][conclkey]["effective_log2"], "transport_status": "no implemented transport; vertical p-isogeny kernel lives over F_{q^r}, r = %s (2^%.2f)" % (nt["r_ord_p_c"], math.log2(int(nt["r_ord_p_c"])))},
                                [pv("p-levels/conclusions.json", "per_level.%s.effective_log2" % conclkey), pv("literature/levels.json", "%s.log2_iterations_best_known" % litkey)],
                                ["verify/p-levels/C1-audit", "verify/p-levels/C1-recompute", "verify/p-levels/C3-audit", "verify/p-levels/C3-recompute", "verify/p-levels/C4-recompute"]),
            "audited_conditional_figure": conditional,
            "p_levels_C4_audit_transport_costs": c4_note,
            "reconciled": reconciled,
            "reconciled_note": "verify/b2-reconcile/levels_reconciled.json not present at build time" if reconciled is None else "from verify/b2-reconcile/levels_reconciled.json",
        },
        "notes": ("fraction of all curves in the isogeny class at levels p and 263p ~ 1 - 2^%.2f; " % litlv["global"]["log2_fraction_in_block_B1"]) +
                 ("the 263-step up to level p is cheap (kernel over F_{q^2}) but the p-step has the same F_{q^r} obstruction; the conditional figure applies after it" if key == "263p" else
                  "reachable from E0 only through one degree-p isogeny"),
    }
    return row

levels = {"p": level_row("p", "LEVEL_p", "p = %d" % p, str(p), "h_O_p", "log2_h_O_p", None, "conductor_p", "p"),
          "263p": level_row("263p", "LEVEL_263p", "263*p = %s" % nt["f"], nt["f"], "h_O_263p", "log2_h_O_263p", None, "conductor_263p", "263p")}

out = {
    "meta": {
        "generated_by": "gaps/G6-consolidate-and-cross-check-per-curve/build_table.py",
        "description": "Consolidated per-curve ECDLP hardness for the F_{2^131}-isogeny class of ECC2K-130 (E0 + 262 conductor-263 floor curves) plus the two unenumerated levels (conductor p, 263p).",
        "field_format": "each field = {value, provenance:[{file,key}], verified_by:[verify dirs whose on-disk outputs cover this label, or '(class-wide)'], recomputed_here, crosscheck_ids, note}",
        "constants": {"q": "2^131", "t": nt["t"], "N": nt["N"], "N_log2": nt["N_log2"], "card": nt["card"], "twist_card": nt["twist_card"], "f": nt["f"], "p": nt["p"], "P114": nt["P114"],
                      "rho_E0_log2": RHO_E0, "rho_neg_only_log2": RHO_NEG, "provenance": pv("gaps/G6-consolidate-and-cross-check-per-curve/nt_checks.json", "*")},
        "crosscheck_summary": {"n_checks": cc["n_checks"], "n_comparisons": cc["n_comparisons"], "n_disagreements": cc["n_disagreements"],
                               "disagreement_classes": sorted({d["check"] for d in cc["disagreements"]})},
        "verify_dirs_missing": {"group-order": "no verify/ directory", "endomorphism-ring": "no verify/ directory", "weil-descent-ghs": "no verify/ directory (gaps/G2 in progress)",
                                "rho-endomorphisms": "no verify/ directory (gaps/G1 in progress)", "literature": "verify/literature/L1-recompute is empty"},
        "inputs_sha256": INPUTS,
        "seconds": None,
    },
    "curves": rows,
    "levels": levels,
}
out["meta"]["seconds"] = round(time.time() - T0, 1)
json.dump(out, open(os.path.join(HERE, "per_curve_hardness.json"), "w"), indent=1, default=str)
print("rows", len(rows), "levels", list(levels), "seconds", out["meta"]["seconds"])
print("E0 effective", rows["E0"]["effective_rho_log2"]["value"]["log2_iterations"], "A000 native", rows["A000"]["native_rho_log2"]["value"]["log2_iterations"])
print("conditional", conditional["log2_iterations_range"], conditional["components"])
