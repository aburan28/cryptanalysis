# Build comparisons.json: one row per compared Codex claim, with our recomputed value, method, script, verdict.
import json, glob
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck"); R = W / "raw"
L = lambda f: json.loads((R / f).read_text())
c01, c02, c04, c05, c06, c07, c08, c09, c12, c13, c15, c16, c17 = [L(f) for f in [
    "c01_ring_invariants.json", "c02_curves_orders_torsion.json", "c04_compare_horizontal.json", "c05_rho_baselines.json",
    "c06_s3_identity.json", "c07_explicit_maps.json", "c08_cm_scalar_algebra.json", "c09_phi263_and_hd.json",
    "c12_run06_bounds.json", "c13_compare_run01_run03.json", "c15_e0_frobenius_dups.json", "c16_run13_edge_rates.json",
    "c17_run11_arithmetic.json"]]
pc = json.loads((W / "per_curve.json").read_text())
rows = []
def add(topic, source, codex, ours, script, verdict, note=""):
    rows.append({"topic": topic, "codex_source": source, "codex": codex, "ours": ours, "script": script, "verdict": verdict, "note": note})
n01 = len(c01["checks"]); a01 = sum(c["agree"] for c in c01["checks"])
add("ring invariants: F_2 points, trace, tau^131 coefficients, conductor 263*p, Lucas cert of p, 4 orders (disc, class number, min non-integer norm), gcd obstructions, ord_131(2), x^131-1 factorisation, invariant subspace dims",
    "ecc2k130-ring-invariants.json, ecc2k130-ring-homomorphism-obstructions.json, ecc2k130-frobenius-subspaces.json",
    "all fields", f"{a01}/{n01} fields equal", "c01_ring_invariants.py", "AGREE" if a01 == n01 else "DISAGREE")
g = c02["global"]
add("embedding degree ord_N(q)", "run-05 embedding-result.json", "216464610000596986937760855436835237 (118 bits, (N-1)/k=3144)",
    f"{g['embedding_degree_ord_N_q']} ({g['embedding_degree_bits']} bits, log2 {g['embedding_degree_log2']:.2f}, (N-1)/k={g['(N-1)/k_emb']})",
    "c02_curves_orders_torsion.py", "AGREE" if g["embedding_degree_agree"] else "DISAGREE")
add("N-1 factorisation", "run-05 embedding-result.json", "2^3*3*11*109*131*263*32326729*21234899465981031419669", g["N_minus_1_factorization"], "c02", "AGREE")
add("q mod 263, t mod 263, charpoly of pi mod 263", "run-05", "1, 261, (X+1)^2", f"{g['q_mod_263']}, {g['t_mod_263']}, {g['charpoly_pi_mod_263']}", "c02", "AGREE")
s = c02["summary"]
add("local 263-torsion: E0 (Z/263)^2 over F_q^2, 264 stable lines; floor Z/263^2 over F_q^2, 1 stable line, full E[263] only over F_q^526",
    "run-05 (tested E0, A090, B021, B067 only)", "4 curves", f"all 263: {s['twist_structure_counts']}; direct F_q^2 check on E0,A000,A090,B000,B021,B067 agrees",
    "c02", "AGREE", "Codex tested 4 curves; we checked all 263 via the quadratic twist plus char-poly (X+1)^2 argument")
add("#E(F_q) = 4N for every curve (a2=0 models)", "inventory.json (A000,B000), run-01 models", "4N", f"{s['order_4N']}/263 by point-order proof", "c02", "AGREE")
add("labels: inventory rule X_k = X000^(2^k)", "inventory.json + run-01 executed-source.py", "labels", f"{s['label_match_gt']}/263 j,b equal to ground truth", "c02", "AGREE")
A = c07["A_codomain_inventory"]
add("run-04 Velu codomain inventory (264 kernel lines)", "run-04 velu-line-enumeration.json", "2 horizontal + 262 distinct descendants",
    f"{A['rows_with_j_1']} rows j=1, {A['floor_rows_label_and_j_match_gt']}/262 floor rows label+j equal GT", "c07_explicit_maps.py", "AGREE")
add("run-01 per-curve j,b (summary.json, 789 rows)", "run-01 summary.json", "789 rows", f"{c13['run01_summary_rows_j_b_equal_gt']}/{c13['run01_summary_rows']} rows equal GT", "c13", "AGREE" if c13['run01_summary_rows_j_b_equal_gt'] == c13['run01_summary_rows'] else "DISAGREE")
for lab, b in c07["B_degree263"].items():
    if not isinstance(b, dict): continue
    ok = b["kernel_poly_matches_independent_line"] and b["codomain_j_equals_gt"] and all(b["transport"][p]["point_matches_some_iso"] and b["transport"][p]["codex_point_killed_by_N"] for p in "PQ")
    add(f"explicit degree-263 map E0->{lab}", f"run-04 {lab}-explicit-map.json",
        f"kernel poly deg 131 (line {b['codex_line_id']}), images of challenge P,Q",
        f"kernel poly == our independent twist-enumerated line {b['kernel_poly_matches_independent_line']}; Sage isogeny degree {b['isogeny_degree']}; codomain j == GT; P,Q images equal Codex's exactly",
        "c07", "AGREE" if ok else "DISAGREE", "Codex line ids are basis-dependent; kernel SHA-256 serialisation not reproduced (coefficients compared directly)")
for O, cr in c07["C_degree11"].items():
    for tgt, m in cr["maps"].items():
        ok = m["codex_kernel_equals_a_division_poly_factor"] and m["P_point_matches_some_iso"] and m["Q_point_matches_some_iso"]
        add(f"degree-11 map {O}000->{tgt}", "run-10 l11-generator-maps.json", "degree-5 kernel poly, images of P,Q",
            f"kernel == a degree-5 factor of psi_11 (factor degrees {cr['factor_degrees']}); P,Q images equal; scalar on N-subgroup = {m['scalar_on_codex_normalised_P']} (other iso gives the negative)",
            "c07", "AGREE" if ok else "DISAGREE")
D = c07["D_l11_field"]
add("11-torsion field and v_11", "run-10 l11-generator-maps.json", "F_(2^1310), v11=2", f"F_q^{D['E11_field_degree_over_Fq']} = F_(2^{131*D['E11_field_degree_over_Fq']}), v11={D['v11_card_Fq10']}", "c07", "AGREE")
nb = sum(1 for c in c08["checks"] if c["agree"]); nt = len(c08["checks"])
add("CM scalars beta, gamma, delta, omega roots, norm-equation solutions, 262 chart alignment scalars", "run-11 cm-alignment.json",
    "beta=352131806444148496925169449605823512480, gamma=40507279511179139861778375210528148470, beta*gamma=-11",
    f"{nb}/{nt} algebraic checks equal; geometric: Frob^(131-16) o phi_11 acts as +-beta (A and B), reverse as +-gamma; mean/max shortest path {c08['A_mean_path_len_all131']:.3f}/{c08['A_max_path_len']}",
    "c08_cm_scalar_algebra.py, c07", "AGREE", "the -11 sign is a normalisation convention: the other codomain isomorphism flips beta -> -beta (c07)")
hz = all(c04[l]["identical"] for l in ["11", "23", "29", "37", "43", "53"])
add("horizontal graphs l in {11,23,29,37,43,53}", "run-10 horizontal-graph.json", "1572 edges, shifts +-16,+-50,+-61,+-24; 29,53 cross-orbit 262-cycles",
    "edge sets identical for all 6 l (from Phi_l mod 2 roots over F_q); class-group dlogs 16,50,70/61,24; [29],[53] order 262", "c03, c04", "AGREE" if hz else "DISAGREE")
add("Phi_263(1,Y) mod 2 = (Y+1)^2 H_D(Y)", "run-04 phi263-specialization.json", "exponent list", "exponents equal (from GT hex H_D and fresh PARI polmodular)", "c09", "AGREE" if all(v for k, v in c09.items() if isinstance(v, bool)) else "DISAGREE")
add("S_3 formula and F_8 control", "ecc2k130-volcano-structural-assessment.md", "56 models x 56 triples, 416 zeros, 208/208",
    f"S_3 vanishes on random collinear triples on all 263 curves: {c06['s3_all_ok']}; F_8: {c06['F8']['zeros']} zeros, {c06['F8']['with_rational_lift']}/{c06['F8']['without']}", "c06", "AGREE")
add("rho baselines", "run-06 REPORT", "2^64.826, 2^64.326, 2^60.809", f"2^{c05['floor_rho_plain_log2']:.3f}, 2^{c05['E0_rho_neg_only_log2']:.3f}, 2^{c05['E0_rho_neg_tau_log2']:.3f}", "c05", "AGREE")
e0, a9 = c12["E0"]["10"], c12["A090"]["10"]
bits = [c12[l][k]["bits_above_E0_rho"] for l in ["E0", "A090", "B021", "B067"] for k in ["8", "9", "10"]]
add("run-06 k=8,9,10 four-summand bounds", "run-06 REPORT", "x counts 126-132/249-255/491-516; coverage 2^-95.84..2^-95.56; LB 2^104.92 (E0), 2^104.71 (A090); +22.05%; 44-50 bits above rho",
    f"coverage {e0['coverage_log2']:.2f} / {a9['coverage_log2']:.2f}; LB {e0['targets_lower_bound_log2']:.2f} / {a9['targets_lower_bound_log2']:.2f}; +{c12['A090_vs_E0_eligible_k10_percent']:.2f}%; {min(bits):.2f}..{max(bits):.2f} bits above rho",
    "c12_run06_bounds.py", "AGREE", "lowest gap 43.90 (A090,k=10) rounds to Codex's '44'")
add("E0 Frobenius duplicates 2P3+P5+P17=O; k=7 E0 eligible 79848 distinct 79788", "run-02/run-03 REPORT", "as stated",
    f"relation holds: {c15['2P3+tau(P3)+tau^2(P3)==O']}; k=7: eligible {c15['E0_k7']['eligible']} distinct {c15['E0_k7']['distinct']} max multiplicity {c15['E0_k7']['max_multiplicity']}", "c15", "AGREE")
add("run-11 overlap identity 130*16*C(c,4) and modeled edge counts", "run-11 REPORT", "2080/145600/1029600/3785600; 17160..68640", "identical", "c17", "AGREE" if c17["all_agree"] else "DISAGREE")
add("run-13 horizontal-edge equality rates (from Codex's own hashes, our edge lists)", "run-13 REPORT + floor-solver-results.json",
    "equal-top 3.82%..6.87%, global 5.50%; equal F4 94.46%; 262/160/261 unique", 
    f"top {min(v['equal_top_rate'] for v in c16['edges'].values())*100:.2f}%..{max(v['equal_top_rate'] for v in c16['edges'].values())*100:.2f}%, global {c16['global_equal_top_rate']*100:.2f}%; F4 {c16['global_equal_f4_comparable_rate']*100:.2f}% (comparable pairs only; F4 degree missing for {c16['f4_distribution'].get('None')} of 262 charts)",
    "c16", "AGREE", "internal-consistency check only (hashes are Codex's)")
for key, lab in [("aggregate_k4", "k4"), ("aggregate_k5", "k5"), ("aggregate_k4_random", "k4_random")]:
    cc, oo = c13["codex_claims"][lab], c13[key]
    ok = (cc["E0"] == oo["E0_targets"] and cc["range"] == oo["all_curves_target_range"] and cc["higher"] == f"{oo['descendants_with_higher_coverage_than_E0']}/262"
          and cc["size_matched_range"] == oo["size_matched_target_range"] and int(cc["best_same_size"].split()[1]) == oo["best_size_matched"][0])
    add(f"run-01/EXPLOITABILITY {lab} aggregates (E0 coverage, range, #descendants above E0, size-matched range, best same-size)", "run-01 REPORT / EXPLOITABILITY.md", json.dumps(cc), json.dumps(oo), "c10c/c10d + c13",
        "AGREE" if ok else "DISAGREE", "k=4 polynomial: 30 size-matched descendants tie at 80 (A010 is one of them)" if lab == "k4" else "")
cc, oo = c13["codex_claims"]["k6"], c13["aggregate_k6"]
ok = cc["x_range"] == oo["x_range"] and cc["target_range"] == oo["target_range"] and oo["collision_rows"] == ["E0"] and oo["best_size_matched"] == [11080, "A092"] and oo["E0"]["eligible_signed_triples"] == 10868 and oo["E0"]["prime_subgroup_distinct_targets"] == 10840
add("run-03 k=6 census aggregates", "run-03 REPORT / EXPLOITABILITY.md", json.dumps(cc), json.dumps(oo), "c10c + c13", "AGREE" if ok else "DISAGREE")
c20 = L("c20_exploitability_sizes.json")
add("EXPLOITABILITY size-matched ratios (A090 +9.09%/+1.70%, B021 0.700/1.073/1.018, B081 +12.12%/-0.15%, only B021 size-matched at k=4,5,6; best reductions 20.67%/4.17%/2.17%)",
    "EXPLOITABILITY.md", "as stated", json.dumps({k: c20[k] for k in ["matched_k5_and_k6", "matched_k4_k5_k6", "ratios", "k5_B067_reduction_percent", "k4random_reduction_percent", "k6_best_reduction_percent"]}),
    "c20_exploitability_sizes.py", "AGREE")
import glob as _g
rows13 = [json.loads(l) for f in _g.glob(str(R / "c11d_shard*of6.jsonl")) for l in open(f) if l.strip()]
unf = sum(r.get("targets_unfiltered_ref") == r["codex_targets"] for r in rows13); sub = sum(r.get("targets_subgroup_ref") == r["codex_targets"] for r in rows13)
cs_c = sum(r["codex_targets"] for r in rows13 if r["key"].startswith("chart")); cs_s = sum(r["targets_subgroup_ref"] for r in rows13 if r["key"].startswith("chart"))
add("run-13 per-chart distinct_reachable_targets (524 chart rows)", "run-13 floor-solver-results.json",
    "e.g. 280 per 7-x chart; sum over adapted charts 177960",
    f"x-sets lift on A090/B021 in {sum(bool(r.get('all_x_lift_on_ref')) for r in rows13)}/524; Codex count == our UNFILTERED distinct 3-sum count in {unf}/524, == order-N-subgroup count in {sub}/524; adapted-panel sum {cs_c} unfiltered vs {cs_s} in the challenge subgroup",
    "c11d_run13_charts_ref_A090_B021.py", "DEFINITIONAL DISCREPANCY",
    "run-13 counts relation images in all of E(F_q) (order 4N); run-01 counts only the order-N subgroup where the public targets live; about 27% of run-13's images are subgroup-compatible. Conclusions (negative) unaffected.")
add("run-11 'minus-dual sign' (beta*gamma = -11)", "run-11 REPORT / cm-alignment.json", "normalized reverse map contains a minus-dual sign",
    "with Codex's normalised codomain points the scalars are exactly beta and gamma; each map has two codomain isomorphisms (identity and negation), and the other choice gives -beta / -gamma (c07)",
    "c07", "NOTE", "the sign is a model-normalisation convention, not an intrinsic property; Codex's calibration against public P is the right fix")
add("run-04 A090.json / B021.json / B067.json", "run-04", "status implementation_error (Sage known-codomain constructor unavailable in char 2)",
    "no numeric content; the verified maps are in *-explicit-map.json (checked above)", "-", "NOTE")
add("kernel-polynomial SHA-256 values", "run-04 *-explicit-map.json, run-10 l11-generator-maps.json", "sha256 strings",
    "serialisation not documented; JSON-list and newline-joined hashes do not reproduce them; coefficients compared directly instead", "c07", "NOT REPRODUCED (format unknown)")
add("run-10 'isogenies_prime_degree interrupted after ~90 s while factoring a division polynomial'", "run-10 REPORT", "engineering censor",
    f"factoring psi_11 of A000/B000 over F_q took {c07['C_degree11']['A']['factor_seconds']:.1f} s / {c07['C_degree11']['B']['factor_seconds']:.1f} s in Sage 10.9 here (machine load ~170)", "c07", "NOTE",
    "the censor was not caused by the factorisation itself; no mathematical consequence")
add("run-13 F4 statistics", "run-13 REPORT", "equal F4-degree rates track a 94.46% global baseline",
    f"reproduced 94.46% but only over comparable pairs: max_f4_degree is missing (None) for {c16['f4_distribution'].get('None')} of 262 adapted charts", "c16", "NOTE")
add("run-13 'zero natural rows in 8,384 public chart-target cells'", "run-13 REPORT", "0",
    "not recomputed: each chart image has <= 280 points in a group of order 4N ~ 2^131, so the expected number of hits over 8,384 cells is at most 280*8384/(N-1) = 2^-107.8; zero is the only plausible outcome and carries no information", "-", "NOTE")
nl = sum(r["codex_label_match"] for r in pc.values()); nv = sum(r["codex_values_match"] for r in pc.values())
add("per-curve summary (per_curve.json)", "all per-curve Codex data", "263 curves", f"label match {nl}/263, values match {nv}/263", "c14", "AGREE" if nl == nv == 263 else "PARTIAL")
(W / "comparisons.json").write_text(json.dumps(rows, indent=1))
print(len(rows), "rows;", sum(r["verdict"] == "AGREE" for r in rows), "AGREE")
for r in rows: print(r["verdict"], "|", r["topic"][:90])
