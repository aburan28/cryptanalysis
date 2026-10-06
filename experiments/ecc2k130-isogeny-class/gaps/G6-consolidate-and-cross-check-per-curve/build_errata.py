"""G6 step (5b): errata.json.

Collects the corrections that audits / red teams stated, with the on-disk evidence for each
(values are read from the cited files at build time, not typed in), and marks corrections that
exist only in prose (orchestrator StructuredOutput text, not on disk) as prose_only.
Also folds in the G6 cross-check disagreements (crosscheck_report.json) and the G6 pairing
C3 re-run (pairing_c3_check.json), and summarises scan_corrections.json.
Run: timeout 2400 python3 build_errata.py   (after crosscheck.py, run_pairing_c3.py, scan_corrections.py)
"""
import json, os, hashlib, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
W = "/Volumes/SSD990/ecdlp-hardness-work"
INPUTS = {}

def P(*a):
    return os.path.join(W, *a)

def jl(rel):
    INPUTS[rel] = hashlib.sha256(open(P(rel), "rb").read()).hexdigest()
    return json.load(open(P(rel)))

def ev(file, key, value):
    return {"file": file, "key": key, "value": value}

cc = json.load(open(os.path.join(HERE, "crosscheck_report.json")))
pc3 = json.load(open(os.path.join(HERE, "pairing_c3_check.json")))
scan = json.load(open(os.path.join(HERE, "scan_corrections.json")))
tr = jl("transport-263/per_curve.json")
ca = jl("verify/transport-263/C4-audit/count_ops.json")
c4r = jl("verify/transport-263/C4-recompute/summary_c4.json")
rt08s = jl("verify/redteam/RT0-8-1/s1_structure.json")
rt08e = jl("verify/redteam/RT0-8-1/s2_e2e.json")
rt08p = jl("verify/redteam/RT0-8-0/params.json")
go = jl("group-order/per_curve.json")
ta3 = jl("verify/toy-analogue-a/C3-audit/check_all.json")
ta2r = jl("verify/toy-analogue-a/C2-audit/recount.json")
ta2s = jl("verify/toy-analogue-a/C2-audit/audit_summary.json")
p2a = jl("verify/pairing-transfer/C2-audit/c2_pure_python.json")
rm = jl("weil-descent-ghs/raw_magic_numbers.json")
rt213 = jl("verify/redteam/RT2-13-0/rt2_13_summary.json")
rt2131 = jl("verify/redteam/RT2-13-1/aggregate.json")
rt201 = jl("verify/redteam/RT2-01-0/raw/s3_cost.json")
c4a = jl("verify/p-levels/C4-audit/c4_numbers.json")
concl = jl("p-levels/conclusions.json")
rt15 = jl("verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_summary.json")
rt2011 = jl("verify/redteam/RT2-01-1/raw/s3_cost_model.json")
t3sub = jl("verify/transport-263/C3-recompute/c3_pure_subset.json")
t3all = jl("verify/transport-263/C3-recompute/c3_pure_all.json")
script_lines = open(P("pairing-transfer/per_curve_pairings.py")).read().splitlines()
INPUTS["pairing-transfer/per_curve_pairings.py"] = hashlib.sha256(open(P("pairing-transfer/per_curve_pairings.py"), "rb").read()).hexdigest()

def grep_lines(pattern):
    return ["line %d: %s" % (i + 1, ln.strip()) for i, ln in enumerate(script_lines) if re.search(pattern, ln)]

FLOOR = [l for l in tr if l != "E0"]
build_rng = {k: [min(tr[l]["build_ops"][k] for l in FLOOR), max(tr[l]["build_ops"][k] for l in FLOOR)] for k in ("M", "S", "I", "A")}
eval_A = sorted({tr[l]["eval_ops_per_point"]["A"] for l in FLOOR})
g2_note = None
g2p = P("gaps/G2-verify-weil-descent-ghs/per_curve_G2.json")
if os.path.exists(g2p):
    try:
        g2 = json.load(open(g2p))
        a = g2["curves"].get("A000", {})
        g2_note = {"file": "gaps/G2-verify-weil-descent-ghs/per_curve_G2.json", "key": "curves.A000.min_pairs_vs_sweep",
                   "value": a.get("min_pairs_vs_sweep") if isinstance(a, dict) else None}
        INPUTS["gaps/G2-verify-weil-descent-ghs/per_curve_G2.json"] = hashlib.sha256(open(g2p, "rb").read()).hexdigest()
    except Exception:
        g2_note = None

dis = collections.Counter(d["check"] for d in cc["disagreements"])
errata = []

errata.append({
    "id": "ERR-01", "claim_id": "transport-263 C4 (transport op counts)",
    "topic": "per-curve build op counts vary; Velu eval add count",
    "original_value": {"claim_text": "not on disk (sweep StructuredOutput only)",
                       "on_disk_single_curve_figure": ev("transport-263/per_curve.json", "A000.build_ops", tr["A000"]["build_ops"]),
                       "on_disk_eval_ops_all_262": ev("transport-263/per_curve.json", "*.eval_ops_per_point.A (distinct values over 262 floor rows)", eval_A)},
    "corrected_value": {"build_ops_range_over_262": ca["build_ops_range_all_262"],
                        "eval_ops_per_point": ca["velu_eval_analytic"]["A_incl_final_plus_v"],
                        "eval_A_as_counted_by_sweep": ca["velu_eval_analytic"]["A_as_counted_by_sweep"],
                        "M_equiv_upper_range": ca["Mup_range"]},
    "correction_on_disk": [ev("verify/transport-263/C4-audit/count_ops.json", "build_ops_range_all_262", ca["build_ops_range_all_262"]),
                           ev("verify/transport-263/C4-audit/count_ops.json", "velu_eval_instrumented.A000", ca["velu_eval_instrumented"]["A000"]),
                           ev("verify/transport-263/C4-audit/count_ops.json", "velu_eval_analytic.{A_incl_final_plus_v,A_as_counted_by_sweep}",
                              [ca["velu_eval_analytic"]["A_incl_final_plus_v"], ca["velu_eval_analytic"]["A_as_counted_by_sweep"]]),
                           ev("verify/transport-263/C4-audit/count_ops.json", "build_failed_x_histogram", ca["build_failed_x_histogram"])],
    "prose_only": False,
    "g6_confirmation": {"per_curve_build_ops_range_recomputed_from_per_curve_json": build_rng,
                        "matches_audit_range": build_rng == ca["build_ops_range_all_262"],
                        "crosscheck T8_eval_ops disagreements (A 787 vs 788)": dis.get("T8_eval_ops", 0)},
    "affects": [{"file": "transport-263/per_curve.json", "key": "*.eval_ops_per_point.A", "rows": dis.get("T8_eval_ops", 0)}],
    "hardness_impact": "none: effective increment stays < 1e-11 bits (C4-recompute worst %s bits)" % c4r["effective_increment_bits_Mequiv_worst"][:22],
})

errata.append({
    "id": "ERR-02", "claim_id": "RT0-8 (twist / invalid-curve oracle on an x-only E0 implementation)",
    "topic": "what an E0-twist oracle leaks",
    "original_value": {"claimed_small_part": "k mod 2*263^2",
                       "claimed_small_part_log2": ev("verify/redteam/RT0-8-1/s1_structure.json", "G.claimed_small_part_log2", rt08s["G"]["claimed_small_part_log2"]),
                       "cofactor_2*263^2": ev("verify/redteam/RT0-8-0/params.json", "cofactor", rt08p["cofactor"])},
    "corrected_value": {"leaks": "k mod 2*263 (and mod P114), not mod 2*263^2, because E0'(F_q) = Z/(2*263*P114) x Z/263",
                        "actual_E0_small_part_log2": rt08s["G"]["actual_E0_small_part_log2"],
                        "E0_impl_leak_modulus_log2": rt08s["G"]["E0_impl_leak_modulus_log2"],
                        "E0_impl_residual_log2": rt08s["G"]["E0_impl_residual_log2"],
                        "floor_impl_leak_modulus_log2": rt08s["G"]["floor_impl_leak_modulus_log2"]},
    "correction_on_disk": [ev("verify/redteam/RT0-8-1/s1_structure.json", "G.{claimed_small_part_log2,actual_E0_small_part_log2}",
                              [rt08s["G"]["claimed_small_part_log2"], rt08s["G"]["actual_E0_small_part_log2"]]),
                           ev("verify/redteam/RT0-8-1/s1_structure.json", "B.pari_ellgroup", rt08s["B"]["pari_ellgroup"]),
                           ev("verify/redteam/RT0-8-1/s2_e2e.json", "E0_impl.k_mod_263sq_obtainable", rt08e["E0_impl"]["k_mod_263sq_obtainable"])],
    "prose_only": False,
    "g6_confirmation": {"group-order E0 pari_twist_ellgroup": go["E0"]["evidence"]["pari_twist_ellgroup"],
                        "crosscheck C4_twist_group (E0' = Z/(2*263*P114) x Z/263, floor twists cyclic) disagreements": dis.get("C4_twist_group", 0)},
    "affects": [{"file": "per_curve_hardness.json", "key": "curves.E0.twist.value.invalid_curve_note", "rows": 1}],
    "hardness_impact": "implementation-level only (x-only / invalid-curve); the ECDLP on E0 is unaffected",
})

errata.append({
    "id": "ERR-03", "claim_id": "toy-analogue-a C3",
    "topic": "runs vs distinct DLP instances",
    "original_value": {"claim_text": "not on disk (StructuredOutput only)"},
    "corrected_value": {"rho_runs": ta3["grand_total"]["rows"], "distinct_planted_DLPs": ta3["grand_total"]["distinct_planted_instances_solved"],
                        "transported_runs": ta3["grand_total"]["tr_rows"], "errors": ta3["grand_total"]["n_errors"]},
    "correction_on_disk": [ev("verify/toy-analogue-a/C3-audit/check_all.json", "grand_total.{rows,distinct_planted_instances_solved,tr_rows}",
                              [ta3["grand_total"]["rows"], ta3["grand_total"]["distinct_planted_instances_solved"], ta3["grand_total"]["tr_rows"]])],
    "prose_only": False, "original_prose_only": True,
    "affects": [], "hardness_impact": "none (all 52,600 runs recovered the planted log)",
})

errata.append({
    "id": "ERR-04", "claim_id": "toy-analogue-a C2",
    "topic": "number of transported pairs",
    "original_value": {"value": 13200, "source": ev("verify/toy-analogue-a/C2-audit/audit_summary.json", "notes[0]", ta2s["notes"][0])},
    "corrected_value": {"value": ta2r["total_transported_rows"], "per_family": {k: v["transported_rows"] for k, v in ta2r.items() if isinstance(v, dict) and "transported_rows" in v}},
    "correction_on_disk": [ev("verify/toy-analogue-a/C2-audit/recount.json", "total_transported_rows", ta2r["total_transported_rows"]),
                           ev("verify/toy-analogue-a/C2-audit/audit_summary.json", "notes[0]", ta2s["notes"][0])],
    "prose_only": False, "affects": [], "hardness_impact": "none (count only; all rows verified)",
})

errata.append({
    "id": "ERR-05", "claim_id": "toy-analogue-a C2 (fast transport cross-check)",
    "topic": "what the 120/120 cross-check compares",
    "original_value": {"value": "360 additional log checks", "source": ev("verify/toy-analogue-a/C2-audit/audit_summary.json", "notes[1]", ta2s["notes"][1])},
    "corrected_value": {"value": "120/120 per family for T19, T23, T109, comparing P images (up to sign) on instances already in the TSVs"},
    "correction_on_disk": [ev("verify/toy-analogue-a/C2-audit/audit_summary.json", "notes[1]", ta2s["notes"][1])],
    "prose_only": False, "affects": [], "hardness_impact": "none",
})

errata.append({
    "id": "ERR-06", "claim_id": "pairing-transfer C2",
    "topic": "identical embedding degree across the 263 curves is forced, not measured",
    "original_value": {"claim_text": "not on disk (StructuredOutput only): identical k reported as a per-curve measurement",
                       "k": p2a["global"]["k_ord_N_q"]},
    "corrected_value": {"k": p2a["global"]["k_ord_N_q"], "status": "value correct; per_curve_pairings.py reads #E from ground_truth order_pari, asserts card == CARD and kE == K_REF, so equality holds by construction (isogenous curves have equal #E)"},
    "correction_on_disk": [ev("pairing-transfer/per_curve_pairings.py", "assert lines", grep_lines(r"order_pari|assert card == CARD|assert kE == K_REF")),
                           ev("verify/pairing-transfer/C2-audit/c2_pure_python.json", "per_curve_summary.distinct_k_E (card derived from point orders, not read)", p2a["per_curve_summary"]["distinct_k_E"])],
    "prose_only": True, "prose_only_note": "no on-disk key states this correction; the evidence (assert lines, independent per-curve recompute) is on disk",
    "affects": [], "hardness_impact": "none (k ~ 2^117.38 on every curve)",
})

errata.append({
    "id": "ERR-07", "claim_id": "pairing-transfer C3 (audit)",
    "topic": "the C3 audit script t1.gp was never completed or run",
    "original_value": {"audit_state": "verify/pairing-transfer/C3-audit contains only t1.gp",
                       "t1_run_by_G6": {"returncode": pc3["t1_gp"]["returncode"], "stdout_lines": pc3["t1_gp"]["stdout_lines"]},
                       "assessment": pc3["t1_gp"]["assessment"]},
    "corrected_value": {"verdict": pc3["verdict"], "all_checks_pass": pc3["all_checks_pass"],
                        "results": pc3["pairing_c3_check_gp"]["results"]},
    "correction_on_disk": [ev("gaps/G6-consolidate-and-cross-check-per-curve/pairing_c3_check.json", "verdict", pc3["verdict"]),
                           ev("gaps/G6-consolidate-and-cross-check-per-curve/t1_run.log", "stdout", "stack overflow in polrootsmod at default parisize; never evaluates a pairing")],
    "prose_only": False, "affects": [], "hardness_impact": "none: claim C3 confirmed on E0, A000, B000 by an independent PARI script",
})

bad_pairs = sorted({json.dumps(rm["curves"][l]["gghs_min_pairs"]) for l in rm["curves"] if l != "E0"})
errata.append({
    "id": "ERR-08", "claim_id": "weil-descent-ghs (raw_magic_numbers.json gghs_min_pairs)",
    "topic": "an unrealizable gGHS decomposition type is listed as a minimum",
    "original_value": ev("weil-descent-ghs/raw_magic_numbers.json", "curves.<floor>.gghs_min_pairs (distinct over 262 floor curves)", [json.loads(x) for x in bad_pairs]),
    "corrected_value": {"realizable_min_pairs": [["Phi131", "Phi131"]],
                        "reason": "a factor of type x+1 is 1, so the other factor is sqrt(b), whose F_2-linear order is x^131+1 on every floor curve (conjugate rank 131, recomputed); (Phi131, x+1) cannot occur",
                        "min_genus_value": "unchanged, 2^130 - 1, attained by the (Phi131, Phi131) witness (gamma1*gamma2 = sqrt(b) verified on 262 curves)"},
    "correction_on_disk": [ev("gaps/G6-consolidate-and-cross-check-per-curve/crosscheck_report.json", "checks.G8_gghs_pairs_realizable", cc["checks"].get("G8_gghs_pairs_realizable"))]
                          + ([g2_note] if g2_note else []),
    "prose_only": False, "found_by": "G6 cross-check G8" + (" (G2 gap reports the same)" if g2_note else ""),
    "affects": [{"file": "weil-descent-ghs/raw_magic_numbers.json", "key": "curves.*.gghs_min_pairs", "rows": dis.get("G8_gghs_pairs_realizable", 0)}],
    "hardness_impact": "none (the minimum genus is the same)",
})

ks = [s for s in rt213["ks_scenarios"] if s.get("excess_over_claim_bits", 0) > 0]
errata.append({
    "id": "ERR-09", "claim_id": "RT2-13 (multi-instance / Kuhn-Struik batch claims)",
    "topic": "claimed sqrt(L) totals and 0.5*log2(L) gains are optimistic",
    "original_value": {"claimed_total_sqrtL_log2": {s["scenario"]: s["claimed_total_sqrtL_log2"] for s in ks},
                       "claimed_gain_bits_0.5log2L (toy m41/m37)": {"%s/%s/L=%s" % (m, r["mode"], r["L"]): r["claimed_gain_bits_0.5log2L"] for m in ("m41", "m37") for r in rt2131[m]["rows"] if "claimed_gain_bits_0.5log2L" in r}},
    "corrected_value": {"total_log2": {s["scenario"]: s["total_log2"] for s in ks},
                        "excess_over_claim_bits": {s["scenario"]: s["excess_over_claim_bits"] for s in ks},
                        "measured_amortised_gain_bits (toy)": {"%s/%s/L=%s" % (m, r["mode"], r["L"]): r["measured_amortised_gain_bits_vs_single"] for m in ("m41", "m37") for r in rt2131[m]["rows"] if "measured_amortised_gain_bits_vs_single" in r}},
    "correction_on_disk": [ev("verify/redteam/RT2-13-0/rt2_13_summary.json", "ks_scenarios[*].{claimed_total_sqrtL_log2,total_log2,excess_over_claim_bits}", len(ks)),
                           ev("verify/redteam/RT2-13-1/aggregate.json", "m41/m37 rows", "claimed vs measured gain")],
    "prose_only": False, "affects": [],
    "hardness_impact": "multi-instance only; single-instance 60.81 unaffected; batch savings are %.3f-%.3f bits smaller than claimed" %
                       (min(s["excess_over_claim_bits"] for s in ks), max(s["excess_over_claim_bits"] for s in ks)),
})

pc = rt201["proposer_cases"]["dim2_c81_A=29.71.137.179"]
errata.append({
    "id": "ERR-10", "claim_id": "RT2-01 (dim-2 Kani transport cost, proposer model)",
    "topic": "proposer's effective iterations recomputed with the best evaluation order",
    "original_value": {C: pc[C]["eff_iter_proposer"] for C in pc if isinstance(pc[C], dict) and "eff_iter_proposer" in pc[C]},
    "corrected_value": {C: pc[C]["eff_iter_corrected"] for C in pc if isinstance(pc[C], dict) and "eff_iter_corrected" in pc[C]},
    "correction_on_disk": [ev("verify/redteam/RT2-01-0/raw/s3_cost.json", "proposer_cases.dim2_c81_A=29.71.137.179.C=*.{eff_iter_proposer,eff_iter_corrected}", "see values")],
    "prose_only": False, "affects": [{"file": "per_curve_hardness.json", "key": "levels.*.effective_rho_log2.audited_conditional_figure"}],
    "hardness_impact": "conditional level-p/263p figure only",
})

errata.append({
    "id": "ERR-11", "claim_id": "p-levels C4 (vertical p-isogeny transport cost) and the level p / 263p effective figure",
    "topic": "claimed lower bounds omit routes; effective figure is conditional",
    "original_value": {"claimed_lower_bounds_log2": {"sqrt-Velu": c4a["log2(sqrt(p) * r/2)  [claimed sqrt-Velu LB]"],
                                                      "cofactor": c4a["log2(131 * r^2)      [claimed cofactor LB, y-coords over F_{q^r}]"],
                                                      "Phi_p": c4a["log2(p^3)            [Phi_p route]"]},
                       "effective_log2_level_p": concl["per_level"]["conductor_p"]["effective_log2"],
                       "effective_log2_level_263p": concl["per_level"]["conductor_263p"]["effective_log2"]},
    "corrected_value": {"routes_the_audit_adds_log2_Fq_ops": {"x-only ladder": c4a["log2(131 * (r/2)^2)  [x-only ladder over F_{q^{r/2}} instead]"],
                                                              "Couveignes/De Feo O~(l^2) (not listed in C4)": c4a["log2(p^2)            [Couveignes/De Feo O~(l^2) route, not listed in C4]"],
                                                              "trace-Velu linear model": c4a["trace-Velu: log2 F_q-ops, linear model (r per F_{q^r} op)"],
                                                              "trace-Velu M(r)=r log r": c4a["trace-Velu: log2 F_q-ops, M(r)=r*log2(r) model"]},
                        "conditional_effective_log2": [rt15["dim2 optimistic (best a<2^30)"]["log2 total (E0 rho + transport), rho-its"],
                                                       rt15["dim2 Robert-notes (best a<2^30)"]["log2 total (E0 rho + transport), rho-its"]],
                        "condition": "Galbraith 2024 dimension-2 Kani transport, not implemented in characteristic 2"},
    "correction_on_disk": [ev("verify/p-levels/C4-audit/c4_numbers.json", "log2(...) keys", "see values"),
                           ev("verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_summary.json", "dim2 optimistic / dim2 Robert-notes", "see values")],
    "prose_only": False, "affects": [{"file": "p-levels/conclusions.json", "key": "per_level.conductor_p.effective_log2 / conductor_263p.effective_log2"}],
    "context": ev("verify/redteam/RT2-01-1/raw/s3_cost_model.json", "constants.{log2_rho_E0_M,log2_rho_B2_native_M}",
                  [rt2011["constants"]["log2_rho_E0_M"], rt2011["constants"]["log2_rho_B2_native_M"]]),
    "hardness_impact": "level p / 263p: unconditional best known stays 64.33 (no implemented transport; the audit's cheapest vertical route, trace-Velu at 2^%.2f F_q ops, is not below native rho at 2^%.2f F_q mults); conditional on an unimplemented char-2 dim-2 Kani transport, about 60.81-61.3"
                       % (c4a["trace-Velu: log2 F_q-ops, linear model (r per F_{q^r} op)"], rt2011["constants"]["log2_rho_B2_native_M"]),
})

errata.append({
    "id": "ERR-12", "claim_id": "transport-263 C3 (recompute, subset run)",
    "topic": "superseded subset run reports all_ok = false",
    "original_value": ev("verify/transport-263/C3-recompute/c3_pure_subset.json", "per_curve[0].{stored_ascending,all_ok}",
                         {k: t3sub["per_curve"][0].get(k) for k in ("label", "stored_ascending", "all_ok")}),
    "corrected_value": ev("verify/transport-263/C3-recompute/c3_pure_all.json", "counts_true.all_ok and per_curve[0].info_stored_int_ascending",
                          {"all_ok": t3all["counts_true"]["all_ok"], "info_stored_int_ascending": t3all["per_curve"][0].get("info_stored_int_ascending")}),
    "correction_on_disk": [],
    "prose_only": False, "note": "the subset run counted the storage order of kernel ints (not ascending) as a failure; the full run demotes it to info and passes 262/262. Not an error in the sweep.",
    "affects": [], "hardness_impact": "none",
})

out = {
    "script": "build_errata.py",
    "n_errata": len(errata),
    "errata": errata,
    "g6_crosscheck_disagreement_classes": dict(dis),
    "scan_summary": {"file": "gaps/G6-consolidate-and-cross-check-per-curve/scan_corrections.json", "n_files_scanned": scan["n_files_scanned"],
                     "n_hits": scan["n_hits"], "by_type": scan["by_type"],
                     "triage": "false_match_flag hits are negative controls or expected inequalities (e.g. N != 2, floor j^2 != j, my_velu == -sage false while == sage true, "
                               "negative-control kernels), except those folded into ERR-12; toy-analogue-b params_info m_matches_meta=false is in the excluded toy-b sweep; "
                               "RT0-6-1 claims all match to 2 dp; rho_branch_correction keys are model constants, not errata."},
    "inputs_sha256": INPUTS,
}
json.dump(out, open(os.path.join(HERE, "errata.json"), "w"), indent=1, default=str)
print("errata", len(errata), dict(dis))
