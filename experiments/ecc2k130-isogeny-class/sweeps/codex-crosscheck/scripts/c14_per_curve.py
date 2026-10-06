# Assemble per_curve.json keyed by ground-truth label: {label: {codex_label_match, codex_values_match, checks...}}
import json
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
Rw = W / "raw"
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
labels = [c["label"] for c in GT["curves"]]
gt = {c["label"]: c for c in GT["curves"]}
c02 = json.loads((Rw / "c02_curves_orders_torsion.json").read_text())
c07 = json.loads((Rw / "c07_explicit_maps.json").read_text())
c08 = json.loads((Rw / "c08_cm_scalar_algebra.json").read_text())
c04 = json.loads((Rw / "c04_compare_horizontal.json").read_text())
c03 = json.loads((Rw / "c03_horizontal_graph.json").read_text())
c13 = json.loads((Rw / "c13_compare_run01_run03.json").read_text())
import glob
c11 = {}
for f in sorted(glob.glob(str(Rw / "c11d_shard*of6.jsonl"))):
    for line in open(f):
        if line.strip():
            r = json.loads(line); c11[r["key"]] = r
CI = W / "codex_inputs/curve-comparison"
vl = json.loads((CI / "run-04-isogeny/velu-line-enumeration.json").read_text())
vl_j = {r["curve_id"]: r["j_integer"] for r in vl["codomain_inventory"] if r["j_integer"] != "1"}
cx_graph = json.loads((CI / "run-10-horizontal-isogenies/horizontal-graph.json").read_text())
cx_nb = {}
for r in cx_graph["results"]:
    for a, b in r["edges"]:
        cx_nb.setdefault((str(r["prime"]), a), set()).add(b); cx_nb.setdefault((str(r["prime"]), b), set()).add(a)
cm = json.loads((CI / "run-11-horizontal-core-fringe/cm-alignment.json").read_text())
N = 680564733841876926932320129493409985129
beta = int(cm["orbits"][0]["beta_plus_scalar_mod_N"]); gamma = int(cm["orbits"][0]["gamma_minus_scalar_mod_N"])
chart_ok = {}
for o in cm["orbits"]:
    for c in o["charts"]:
        k = int(c["curve_id"][1:]); s = c["path_steps"]; d = c["path_direction"]
        chart_ok[c["curve_id"]] = ((k + 16*d*s) % 131 == 0 and str(pow(beta if d == 1 else gamma, s, N)) == c["alignment_scalar_mod_N"])
inv = json.loads((W / "codex_inputs/public-cm-inventory/inventory.json").read_text())
emb = json.loads((CI / "run-05-embedding/embedding-result.json").read_text())
emb_c = {c["curve_id"]: c for c in emb["curves"]}
out = {}
for lab in labels:
    r = {}
    cc = c02["curves"][lab]
    # label checks
    lm = {"inventory_rule_j_equals_gt": cc["label_match_gt"]}
    if lab != "E0":
        lm["run04_velu_codomain_j_equals_gt"] = (vl_j.get(lab) == gt[lab]["j_int"])
    if lab in ("A000", "B000"):
        m = inv["models"][0 if lab == "A000" else 1]
        lm["inventory_json_j_b_equal_gt"] = (m["j_integer_encoding"] == gt[lab]["j_int"] and m["b_integer_encoding"] == gt[lab]["b_int"])
    r["label_checks"] = lm
    r["codex_label_match"] = all(lm.values())
    # value checks
    v = {}
    v["order_4N_point_proof"] = cc["order_4N_by_point_proof"]
    if lab in ("A000", "B000"):
        v["inventory_cardinality_equals_4N"] = inv["models"][0 if lab == "A000" else 1]["cardinality"] == GT["meta"]["card"]
    # 263-torsion claim: Codex general statement (E0: (Z/263)^2 / 264 lines; floor: Z/263^2 / 1 line)
    exp_struct = "(Z/263)^2" if lab == "E0" else "Z/263^2"
    v["local_263_structure_matches_codex_claim"] = (cc["twist_263_structure"] == exp_struct)
    if lab in emb_c:
        e = emb_c[lab]
        v["run05_structure_equal"] = (e["E_Fq2_263_primary_structure"] == cc["twist_263_structure"])
        v["run05_stable_lines_equal"] = (e["Fq_rational_263_isogeny_kernel_lines"] == cc["stable_263_lines"])
        if lab != "E0":
            v["run05_full_E263_degree_equal"] = (e["full_E263_field_degree"] == 526)
    # horizontal graph neighbours
    if lab != "E0":
        hg = True
        for l, d in c03["ells"].items():
            ours = set(n for n, m in d["neighbours"][lab])
            hg &= (ours == cx_nb.get((l, lab), set()))
        v["run10_horizontal_neighbours_all_6_degrees_equal"] = hg
        v["run11_chart_alignment_scalar_algebra"] = chart_ok.get(lab, False)
    pc = c13["per_curve"].get(lab, {})
    for k2, val in pc.items():
        if k2 == "run01_summary_j_b_equal_gt":
            lm[k2] = val
        else:
            v[k2 + "_coverage_values_equal"] = val
    for panel in ["common_conjugate", "chart_specific"]:
        key = f"{panel}:{lab}"
        if key in c11:
            x = c11[key]
            valid = bool(x.get("all_x_lift_on_ref"))
            v[f"run13_{panel}_x_on_A090_B021_and_unfiltered_image_equal"] = bool(valid and x.get("targets_unfiltered_ref") == x["codex_targets"] and x["codex_x_count"] == x["n_pulled_x"])
            r.setdefault("notes", {})[f"run13_{panel}_codex_targets_vs_subgroup_filtered"] = [x["codex_targets"], x.get("targets_subgroup_ref")]
    if lab in c07["B_degree263"]:
        b = c07["B_degree263"][lab]
        v["run04_explicit_263_map_verified"] = bool(b["kernel_poly_matches_independent_line"] and b["codomain_j_equals_gt"]
                                                    and b["transport"]["P"]["point_matches_some_iso"] and b["transport"]["Q"]["point_matches_some_iso"])
    if lab in ("A000", "B000"):
        O = lab[0]; cr = c07["C_degree11"][O]
        v["run10_l11_maps_and_run11_beta_gamma_geometric"] = all(
            m["codex_kernel_equals_a_division_poly_factor"] and m["P_point_matches_some_iso"] and m["Q_point_matches_some_iso"]
            and m["scalar_on_codex_normalised_P"] in (["beta"], ["gamma"]) for m in cr["maps"].values())
    r["label_checks"] = lm
    r["codex_label_match"] = all(lm.values())
    r["value_checks"] = v
    r["codex_values_match"] = all(v.values())
    out[lab] = r
(W / "per_curve.json").write_text(json.dumps(out, indent=1))
nl = sum(r["codex_label_match"] for r in out.values()); nv = sum(r["codex_values_match"] for r in out.values())
from collections import Counter
cnt = Counter()
for r in out.values():
    for k, val in r["value_checks"].items():
        cnt[(k, val)] += 1
print("label match", nl, "/", len(out), "; values match", nv, "/", len(out))
for (k, val), n in sorted(cnt.items()):
    print(f"  {k}: {val} x{n}")
bad = [l for l, r in out.items() if not (r["codex_label_match"] and r["codex_values_match"])]
print("curves with any mismatch:", bad)
