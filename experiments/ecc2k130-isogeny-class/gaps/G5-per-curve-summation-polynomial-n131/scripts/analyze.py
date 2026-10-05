"""Collect every G5 run into runs.csv and summarise into results.json (answers Q1-Q5).
Plain python3 (no Sage needed).  Inputs: raw/grid/*.jsonl, raw/codex_repro_*.json,
raw/k7/*.json, rank_scaling.json, controls.json, selftest.json."""
import csv
import glob
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CTRL = json.loads((ROOT / "controls.json").read_text())
NOTE = {c["label"]: c["note"] for c in CTRL["curves"]}

rows = []
for f in sorted(glob.glob(str(ROOT / "raw" / "grid" / "*.jsonl"))):
    for line in open(f):
        rows.append(json.loads(line))


def flat(r):
    f = r.get("formal", {})
    fr = r.get("formal_raw", {})
    ms = r.get("msolve", {})
    sc = r.get("solution_classes", {})
    return {
        "id": r.get("id"), "group": r.get("group"), "label": r.get("label"), "b_note": NOTE.get(r.get("label"), ""),
        "hw_b": r.get("hw_b"), "trace_b": r.get("trace_b"), "sub": r.get("sub"), "sub_idx": r.get("sub_idx"),
        "k": r.get("k"), "m": r.get("m"), "mode": r.get("mode"), "target_kind": r.get("target_kind"),
        "target_idx": r.get("target_idx"), "target_x": r.get("target_x"), "nv": r.get("nv"),
        "x_count": r.get("x_count"), "image_size": r.get("image_size"),
        "anf_monomials": r.get("anf_monomials"), "anf_degree": r.get("anf_degree"),
        "desc_rank": r.get("desc_rank"), "n_desc_eqs_nonzero": r.get("n_desc_eqs_nonzero"),
        "n_generators": r.get("n_generators"), "bf_solutions": r.get("bf_solutions"),
        "expected_solutions": r.get("expected_solutions"),
        "sol_rational_ok": sc.get("all_rational_and_sum_ok"), "sol_nonrational": sc.get("nonrational"),
        "formal_status": f.get("status"), "formal_d_reg": f.get("d_reg"),
        "formal_top_quotient_dim": f.get("top_quotient_dim"), "formal_unit_after_rr": f.get("unit_after_rr"),
        "formal_n_reduced": f.get("n_generators"),
        "formal_top_degree_hist": json.dumps(f.get("generator_top_degree_hist")),
        "formal_hilbert_function": json.dumps(f.get("hilbert_function")),
        "formal_std_cpu": f.get("std_cpu"), "formal_raw_status": fr.get("status"),
        "formal_raw_d_reg": fr.get("d_reg"), "formal_raw_top_quotient_dim": fr.get("top_quotient_dim"),
        "msolve_status": ms.get("status"), "msolve_max_degree": ms.get("max_degree"),
        "msolve_n_rounds": ms.get("n_rounds"), "msolve_degree_sequence": json.dumps(ms.get("degree_sequence")),
        "msolve_max_matrix_rows": (ms.get("max_matrix") or [None, None])[0],
        "msolve_max_matrix_cols": (ms.get("max_matrix") or [None, None])[1],
        "msolve_cpu_reported": ms.get("msolve_cpu_reported"), "msolve_process_cpu": ms.get("cpu"),
        "msolve_solution_count": ms.get("solution_count"), "msolve_agrees_bruteforce": ms.get("agrees_with_bruteforce"),
        "status": r.get("status", "ok"),
    }


flats = [flat(r) for r in rows]
if flats:
    with open(ROOT / "runs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flats[0].keys()))
        w.writeheader()
        w.writerows(flats)


def dist(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    c = Counter(vals)
    return {"n": len(vals), "min": min(vals), "median": st.median(vals), "max": max(vals),
            "hist": {str(k): c[k] for k in sorted(c)}}


def cell(filter_fn, key):
    return dist([x[key] for x in flats if filter_fn(x)])


def med(vals):
    vals = [v for v in vals if v is not None]
    return st.median(vals) if vals else None


# ---- summary table per (label, sub, sub_idx, k, m, mode, target_kind)
summ = defaultdict(list)
for x in flats:
    if x["status"] != "ok":
        continue
    summ[(x["group"], x["label"], x["sub"], x["sub_idx"], x["k"], x["m"], x["mode"], x["target_kind"])].append(x)
table = []
for key, xs in sorted(summ.items(), key=lambda t: tuple(str(u) for u in t[0])):
    g, lab, sub, si, k, m, mode, tk = key
    table.append({
        "group": g, "label": lab, "b_note": NOTE.get(lab, ""), "sub": f"{sub}{si}", "k": k, "m": m, "mode": mode,
        "target_kind": tk, "n": len(xs),
        "desc_rank": dist([x["desc_rank"] for x in xs]),
        "formal_d_reg": dist([x["formal_d_reg"] for x in xs]),
        "formal_top_quotient_dim_median": med([x["formal_top_quotient_dim"] for x in xs]),
        "formal_timeouts": sum(1 for x in xs if x["formal_status"] == "timeout"),
        "formal_raw_d_reg": dist([x["formal_raw_d_reg"] for x in xs]),
        "msolve_max_degree": dist([x["msolve_max_degree"] for x in xs]),
        "msolve_n_rounds_median": med([x["msolve_n_rounds"] for x in xs]),
        "msolve_max_matrix_rows_median": med([x["msolve_max_matrix_rows"] for x in xs]),
        "msolve_cpu_reported_median": med([x["msolve_cpu_reported"] for x in xs]),
        "msolve_process_cpu_median": med([x["msolve_process_cpu"] for x in xs]),
        "msolve_timeouts": sum(1 for x in xs if x["msolve_status"] == "timeout"),
        "msolve_agrees_all": all(x["msolve_agrees_bruteforce"] for x in xs if x["msolve_status"] == "ok"),
        "bf_solutions": dist([x["bf_solutions"] for x in xs]),
    })


def sel(**kw):
    def f(x):
        return x["status"] == "ok" and all(x[k] == v for k, v in kw.items())
    return f


def group_vals(pred, key):
    return [x[key] for x in flats if pred(x) and x[key] is not None]


results = {"n_runs": len(flats), "table": table}

# ---- Q1
repro = []
for f in sorted(glob.glob(str(ROOT / "raw" / "codex_repro_*.json"))):
    d = json.loads(open(f).read())
    repro.append({"label": d["label"], "target_matches_codex": d["target_matches_codex"],
                  "d_reg": d["formal"]["d_reg"], "top_quotient_dim": d["formal"]["top_quotient_dim"],
                  "codex_recorded": d["codex_recorded"], "reproduced": d["reproduced"],
                  "raw_equations": d["raw_equations"], "reduced_equations": d["reduced_equations"],
                  "descended_rank": d["descended_rank"], "hilbert_function": d["formal"]["hilbert_function"],
                  "generator_top_degree_hist": d["formal"]["generator_top_degree_hist"],
                  "msolve_max_degree": d["msolve_codex_system"].get("max_degree"),
                  "msolve_cpu_reported": d["msolve_codex_system"].get("msolve_cpu_reported"),
                  "msolve_solutions": d["msolve_codex_system"].get("solution_count")})
k7 = []
for f in sorted(glob.glob(str(ROOT / "raw" / "k7" / "*.json"))):
    for d in json.loads(open(f).read()):
        k7.append({x: d.get(x) for x in ("label", "mode", "target_kind", "target_idx", "desc_rank", "bf_solutions",
                                         "target_matches_codex", "anf_monomials")}
                  | {"sub": d.get("sub", "poly0")}
                  | {"formal_status": d["formal"].get("status"), "formal_d_reg": d["formal"].get("d_reg"),
                     "formal_top_quotient_dim": d["formal"].get("top_quotient_dim"),
                     "formal_std_cpu": d["formal"].get("std_cpu"),
                     "msolve_status": d["msolve"].get("status"), "msolve_max_degree": d["msolve"].get("max_degree"),
                     "msolve_cpu_reported": d["msolve"].get("msolve_cpu_reported"),
                     "msolve_max_matrix": d["msolve"].get("max_matrix"),
                     "msolve_agrees": d["msolve"].get("agrees_with_bruteforce")})
results["k7_runs"] = k7
q1 = {"codex_k6_cells_reproduced": repro}
for lab in ("E0", "A000", "B000", "A010"):
    for k in (4, 5, 6):
        q1[f"{lab}_k{k}_codex_image_d_reg"] = cell(sel(group="main", label=lab, k=k, m=3, mode="codex",
                                                      target_kind="image"), "formal_d_reg")
        q1[f"{lab}_k{k}_codex_random_d_reg"] = cell(sel(group="main", label=lab, k=k, m=3, mode="codex",
                                                       target_kind="random"), "formal_d_reg")
results["Q1"] = q1

# ---- Q2 / Q4: E0 vs sparse-b and dense-b random curves (polynomial basis)
sparse_labels = [c["label"] for c in CTRL["curves"] if c["kind"] == "sparse"]
dense_labels = [c["label"] for c in CTRL["curves"] if c["kind"] == "dense"]


def compare(k, m, mode, tk, key):
    out = {}
    for lab in ("E0", "A000", "B000", "A010"):
        out[lab] = dist(group_vals(sel(group="main", label=lab, k=k, m=m, mode=mode, target_kind=tk), key))
    out["sparse_b_pooled"] = dist([v for lab in sparse_labels for v in
                                   group_vals(sel(label=lab, sub="poly", k=k, m=m, mode=mode, target_kind=tk), key)])
    out["sparse_b_per_curve_median"] = {lab: med(group_vals(sel(label=lab, sub="poly", k=k, m=m, mode=mode,
                                                                target_kind=tk), key)) for lab in sparse_labels}
    out["dense_b_pooled"] = dist([v for lab in dense_labels for v in
                                  group_vals(sel(label=lab, sub="poly", k=k, m=m, mode=mode, target_kind=tk), key)])
    out["dense_b_per_curve_median"] = {lab: med(group_vals(sel(label=lab, sub="poly", k=k, m=m, mode=mode,
                                                               target_kind=tk), key)) for lab in dense_labels}
    out["b_z_review_check"] = dist(group_vals(sel(label="RZz", sub="poly", k=k, m=m, mode=mode, target_kind=tk), key))
    return out


cmp = {}
for k in (4, 5, 6):
    for m, mode, tk in ((3, "codex", "image"), (3, "codex", "random"), (3, "plain", "planted"),
                        (3, "plain", "random"), (2, "plain", "planted"), (2, "plain", "random")):
        for key in ("formal_d_reg", "desc_rank", "msolve_max_degree", "msolve_cpu_reported",
                    "msolve_max_matrix_rows"):
            cmp[f"k{k}_m{m}_{mode}_{tk}_{key}"] = compare(k, m, mode, tk, key)
results["Q2_Q4_curve_comparisons"] = cmp

# ---- Q3: subspace controls for E0 and A000
q3 = {}
for lab in ("E0", "A000"):
    for k in (4, 5, 6):
        for m, mode, tk in ((3, "codex", "image"), (3, "plain", "planted"), (3, "plain", "random"),
                            (2, "plain", "planted")):
            for key in ("formal_d_reg", "desc_rank", "msolve_cpu_reported", "msolve_max_degree"):
                d = {"poly": dist(group_vals(sel(label=lab, sub="poly", group="main", k=k, m=m, mode=mode,
                                                 target_kind=tk), key))}
                for sub, n in (("rand", 5), ("scaled", 3), ("powerw", 3), ("powerb", 1)):
                    for si in range(n):
                        v = group_vals(sel(label=lab, sub=sub, sub_idx=si, k=k, m=m, mode=mode, target_kind=tk), key)
                        if v:
                            d[f"{sub}{si}"] = dist(v)
                q3[f"{lab}_k{k}_m{m}_{mode}_{tk}_{key}"] = d
for lab in ("B000", "A010"):
    for k in (4, 5, 6):
        for key in ("formal_d_reg", "desc_rank"):
            q3[f"{lab}_k{k}_m3_codex_image_{key}"] = {
                "poly": dist(group_vals(sel(label=lab, sub="poly", k=k, m=3, mode="codex", target_kind="image"), key)),
                "powerb0": dist(group_vals(sel(label=lab, sub="powerb", k=k, m=3, mode="codex", target_kind="image"), key))}
results["Q3_subspace_controls"] = q3

# ---- rank scaling
rs = json.loads((ROOT / "rank_scaling.json").read_text()) if (ROOT / "rank_scaling.json").exists() else {}
results["rank_scaling"] = [{x: r[x] for x in ("m", "k", "label", "sub", "rank_full", "rank_nonconst", "monomials")}
                           for r in rs.get("rows", [])]

# ---- degree-graded RREF profiles and m = 4 msolve checks
gp = []
for fn in ("graded_profile.json", "graded_extra.json"):
    if (ROOT / fn).exists():
        for r in json.loads((ROOT / fn).read_text())["rows"]:
            gp.append({"m": r["m"], "k": r["k"], "label": r["label"], "sub": r["sub"], "graded": r["graded"],
                       "source": fn})
results["graded_profiles"] = gp
m4 = []
for f in sorted(glob.glob(str(ROOT / "raw" / "m4" / "*.json"))):
    for d in json.loads(open(f).read()):
        ms = d["msolve"]
        m4.append({x: d.get(x) for x in ("label", "k", "target_kind", "target_idx", "desc_rank", "anf_monomials",
                                         "bf_solutions", "planted_in_solutions")}
                  | {"msolve_status": ms.get("status"), "msolve_max_degree": ms.get("max_degree"),
                     "msolve_degree_sequence": ms.get("degree_sequence"),
                     "msolve_cpu_reported": ms.get("msolve_cpu_reported"), "msolve_max_matrix": ms.get("max_matrix"),
                     "msolve_agrees": ms.get("agrees_with_bruteforce")})
results["m4_runs"] = m4

# ---- global sanity
results["sanity"] = {
    "msolve_ok_runs": sum(1 for x in flats if x["msolve_status"] == "ok"),
    "msolve_timeouts": sum(1 for x in flats if x["msolve_status"] == "timeout"),
    "msolve_errors": sum(1 for x in flats if x["msolve_status"] == "error"),
    "msolve_disagreements_with_bruteforce": sum(1 for x in flats if x["msolve_status"] == "ok"
                                                and not x["msolve_agrees_bruteforce"]),
    "formal_timeouts": sum(1 for x in flats if x["formal_status"] == "timeout"),
    "image_targets_with_expected_solution_count": sum(1 for x in flats if x["target_kind"] == "image"
                                                      and x["bf_solutions"] == x["expected_solutions"]),
    "image_targets": sum(1 for x in flats if x["target_kind"] == "image"),
    "planted_runs_with_solutions": sum(1 for x in flats if x["target_kind"] == "planted" and (x["bf_solutions"] or 0) > 0),
    "planted_runs": sum(1 for x in flats if x["target_kind"] == "planted" and x["status"] == "ok"),
    "random_target_runs_with_solutions": sum(1 for x in flats if x["target_kind"] == "random"
                                             and (x["bf_solutions"] or 0) > 0),
    "msolve_max_degree_hist_by_m": {str(m): dict(Counter(x["msolve_max_degree"] for x in flats if x["m"] == m))
                                    for m in (2, 3)},
}
(ROOT / "summary_tables.json").write_text(json.dumps(results, indent=1, default=str))
print(json.dumps(results["sanity"], indent=1))
print(len(flats), "runs")
