"""Assemble results.json (answers to Q1-Q5 with the numbers computed in this directory) and
runs_all.csv (grid + k = 7 + m = 4 + Codex-reproduction runs).  Run after analyze.py.
Plain python3."""
import csv
import glob
import hashlib
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = json.loads((ROOT / "summary_tables.json").read_text())
CTRL = json.loads((ROOT / "controls.json").read_text())
flats = list(csv.DictReader(open(ROOT / "runs.csv")))


def num(x):
    if x in ("", None):
        return None
    try:
        return int(x)
    except ValueError:
        try:
            return float(x)
        except ValueError:
            return x


for r in flats:
    for k in ("k", "m", "formal_d_reg", "desc_rank", "msolve_max_degree", "sub_idx", "bf_solutions",
              "formal_top_quotient_dim"):
        r[k] = num(r[k])
    for k in ("msolve_cpu_reported", "msolve_process_cpu"):
        r[k] = num(r[k])


def pick(**kw):
    return [r for r in flats if r["status"] == "ok" and all(r[k] == v for k, v in kw.items())]


def hist(rs, key):
    c = Counter(r[key] for r in rs if r[key] is not None)
    return {str(k): c[k] for k in sorted(c, key=lambda z: (z is None, z))}


def med(rs, key):
    v = [r[key] for r in rs if r[key] is not None]
    return st.median(v) if v else None


def r2(x):
    return None if x is None else round(x, 2)


def summary(rs, key):
    v = [r[key] for r in rs if r[key] is not None]
    if not v:
        return None
    return {"n": len(v), "min": min(v), "median": st.median(v), "max": max(v), "hist": hist(rs, key)}


sparse = [c["label"] for c in CTRL["curves"] if c["kind"] == "sparse"]
dense = [c["label"] for c in CTRL["curves"] if c["kind"] == "dense"]


def pooled(labels, **kw):
    out = []
    for lab in labels:
        out += pick(label=lab, sub="poly", **kw)
    return out


R = {}
R["task"] = "G5-per-curve-summation-polynomial-n131"
R["tools"] = {"sage": "10.9", "msolve": "0.9.5 (F4, grevlex, 1 thread, -g 2)", "singular": "4.4.1 (libsingular std via Sage)",
              "python": "numpy brute force (Moebius transform) for exact solution sets"}
R["field"] = "F_2[z]/(z^131+z^13+z^2+z+1) (ground_truth/ecc2k.py); field elements = bitmask integers"
R["definitions"] = {
    "plain": "131 Boolean equations of S_{m+1}(x_1..x_m, x(R)) with x_i = sum_j v_ij w_j, (w_j) a basis of V_k, plus v^2+v",
    "codex": "plain + Codex run-01 membership indicators (ANF of 'x not a rational nonzero x-coordinate', one per block) "
             "+ pairwise distinctness prod_i(1+v_ai+v_ci) (m = 3); Codex's exact make_equations",
    "formal_d_reg": "Codex's measure: full F_2 row reduction of the generator list with degree-compatible pivots, J = ideal "
                    "of the highest-degree components, d_reg = 1 + max degree of a standard monomial of R/J (0 = unit "
                    "ideal after row reduction, i.e. inconsistent by linear algebra)",
    "msolve_max_degree": "largest 'deg' of any F4 round printed by msolve -v 2 (the maximal degree the solver reached)",
    "desc_rank": "F_2-dimension of the span of the 131-bit coefficients of the descended S_{m+1} = number of linearly "
                 "independent Boolean equations",
    "graded_profile": "row-reduce the 131 descended equations with a degree-compatible order; count rows by top degree "
                      "(rows below the input degree are degree falls available by linear algebra alone; degree 0 = "
                      "inconsistent). Invariant under the choice of degree-compatible order and of the F_2-basis of F_q",
    "subspaces": {"poly": "V_k = span{1, z, .., z^(k-1)}", "rand<s>": "first k of 6 random vectors (seed 20260924)",
                  "scaled<s>": "c * V_k, c dense (seed 20260926)", "powerw<s>": "span{1, w, .., w^(k-1)}, w dense random",
                  "powerb": "span{1, b, .., b^(k-1)} (curve's own b)", "shiftb": "span{1, w, .., w^(k-1)}, w = b + 1 (so b = 1 + w)"},
}
R["design"] = {
    "main": "E0, A000, B000, A010 on V_k, k = 4, 5, 6: m = 2 and 3 plain (10 random N-subgroup targets + 5 planted), "
            "m = 3 codex (10 image targets from Codex's exact image + the same 10 random targets)",
    "controls": "5 random + 3 planted (plain), 5 image + 5 random (codex) per job: 10 dense-b and 10 sparse-b random curves "
                "with Tr(b) = 1 (+ b = z, Tr 0), E0/A000 on 5 random subspaces, E0/A000 on 3 scaled subspaces, E0 on 3 "
                "power bases span{w^j}, A000/B000/A010 on span{b^j}, A000/B000/A010/RD00 on span{(b+1)^j}; random-subspace "
                "jobs at k = 6 only 1+1 (plain) and 1 (codex) m = 3 targets with 300 s caps",
    "caps": "msolve 600 s wall (timeout), formal d_reg 600 s wall (cysignals alarm); machine load average 28-48 from other jobs (uptime)",
    "extensions": "k = 7 m = 3 plain msolve (5 targets per curve/subspace), Codex's two k = 7 cells, m = 4 (S5) k = 3 msolve "
                  "(10 random + 1 planted per curve), degree-graded profiles m = 3 up to k = 12 and m = 4 up to k = 5",
}
R["inputs_sha256"] = dict(reversed(l.split(None, 1)) for l in (ROOT / "inputs_sha256.txt").read_text().splitlines())
R["inputs_note"] = ("inputs_codex_run03/ are copies of Codex run-03 raw rows and source (read-only originals under "
                    "~/Documents/Codex/.../run-03-scaling); selected_scaling.py hashes to Codex protocol.json's source_sha256 "
                    + str(json.loads((ROOT / "inputs_codex_run03" / "protocol.json").read_text())["source_sha256"] ==
                          [v for k, v in R["inputs_sha256"].items() if k.endswith("selected_scaling.py")][0]))
R["sanity"] = S["sanity"]
R["n_grid_runs"] = S["n_runs"]
R["selftests"] = json.loads((ROOT / "selftest.json").read_text())
_ih = json.loads((ROOT / "indep_hilbert.json").read_text())
R["independent_hilbert_check"] = {"n_systems": _ih["n"], "all_match_singular": _ih["all_match"],
                                  "method": "Macaulay-matrix ranks in F_2[v]/(v_i^2), no Singular (scripts/indep_hilbert.py)",
                                  "scope": "all main-group k = 4 m = 3 non-unit rows + k = 5 codex image rows of E0 and A010"}

# ---------------- Q1
repro = S["Q1"]["codex_k6_cells_reproduced"]
k7codex = [r for r in S["k7_runs"] if r["target_kind"] == "codex_run03_target"]
q1 = {"codex_k6_cells": repro,
      "all_six_reproduced_exactly": all(r["reproduced"] for r in repro),
      "k6_codex_image_formal_d_reg_over_10_targets": {lab: summary(pick(group="main", label=lab, k=6, m=3, mode="codex",
                                                                         target_kind="image"), "formal_d_reg")
                                                      for lab in ("E0", "A000", "B000", "A010")},
      "k6_msolve_on_codex_systems_image_targets": {lab: {"max_degree": summary(pick(group="main", label=lab, k=6, m=3, mode="codex", target_kind="image"), "msolve_max_degree"),
                                                           "f4_cpu_median_s": med(pick(group="main", label=lab, k=6, m=3, mode="codex", target_kind="image"), "msolve_cpu_reported")}
                                                     for lab in ("E0", "A000", "B000", "A010")},
      "k7_codex_cells": k7codex}
e0 = next(r for r in repro if r["label"] == "E0")
a10 = next(r for r in repro if r["label"] == "A010")
q1["answer"] = (
    f"Yes, exactly. With Codex's own target rule (sorted image, sha256('<id>:6:run03')) and Codex's equations, all six run-03 "
    f"k = 6 cells reproduce: E0 d_reg {e0['d_reg']} / top quotient dim {e0['top_quotient_dim']} "
    f"({e0['raw_equations']} raw -> {e0['reduced_equations']} row-reduced generators), A010 {a10['d_reg']} / "
    f"{a10['top_quotient_dim']} ({a10['raw_equations']} -> {a10['reduced_equations']}); "
    + ", ".join(f"{r['label']} {r['d_reg']}/{r['top_quotient_dim']}" for r in repro if r["label"] not in ("E0", "A010"))
    + f". Over 10 image targets each, E0 gives "
    f"{q1['k6_codex_image_formal_d_reg_over_10_targets']['E0']['hist']} and A010 "
    f"{q1['k6_codex_image_formal_d_reg_over_10_targets']['A010']['hist']}, so the gap is not a single-target accident. "
    f"But the formal d_reg is not what the solver meets: msolve's F4 reaches maximal degree 6 (the input degree) on every "
    f"one of these systems, for E0 and for the descendants. At k = 7, Codex's two cells (E0, A010) time out at 600 s in the "
    f"formal-d_reg computation too (Codex's were censored at 30 s); msolve solves both, reaching degree "
    f"{sorted({r['msolve_max_degree'] for r in k7codex})} (the degree of the k = 7 distinctness generators) in "
    f"{[r['msolve_cpu_reported'] for r in k7codex]} s F4 CPU for {[r['label'] for r in k7codex]}.")

R["Q1"] = q1

# ---------------- Q2 / Q4 (polynomial basis)
def cmp_block(k, m, mode, tk, key):
    return {"E0": summary(pick(group="main", label="E0", k=k, m=m, mode=mode, target_kind=tk), key),
            "A000": summary(pick(group="main", label="A000", k=k, m=m, mode=mode, target_kind=tk), key),
            "B000": summary(pick(group="main", label="B000", k=k, m=m, mode=mode, target_kind=tk), key),
            "A010": summary(pick(group="main", label="A010", k=k, m=m, mode=mode, target_kind=tk), key),
            "sparse_b_pooled": summary(pooled(sparse, k=k, m=m, mode=mode, target_kind=tk), key),
            "sparse_b_per_curve_median": {lab: med(pick(label=lab, sub="poly", k=k, m=m, mode=mode, target_kind=tk), key) for lab in sparse},
            "dense_b_pooled": summary(pooled(dense, k=k, m=m, mode=mode, target_kind=tk), key),
            "dense_b_per_curve_median": {lab: med(pick(label=lab, sub="poly", k=k, m=m, mode=mode, target_kind=tk), key) for lab in dense},
            "b_eq_z_TrB0": summary(pick(label="RZz", sub="poly", k=k, m=m, mode=mode, target_kind=tk), key)}


q2 = {}
for k in (4, 5, 6):
    for (m, mode, tk) in ((3, "codex", "image"), (3, "plain", "planted"), (3, "plain", "random"), (2, "plain", "planted"), (2, "plain", "random")):
        for key in ("formal_d_reg", "desc_rank", "msolve_cpu_reported", "msolve_max_degree"):
            q2[f"k{k}_m{m}_{mode}_{tk}_{key}"] = cmp_block(k, m, mode, tk, key)
R["curve_comparison_polynomial_basis"] = q2
c6 = q2["k6_m3_codex_image_formal_d_reg"]
p6 = q2["k6_m3_plain_planted_formal_d_reg"]
r6 = q2["k6_m3_plain_random_formal_d_reg"]
def rng_(rs, key="desc_rank"):
    v = [r[key] for r in rs if r[key] is not None]
    return f"{min(v)}-{max(v)}" if v and min(v) != max(v) else (str(v[0]) if v else "n/a")


rank_ranges = {}
for k in (4, 5, 6):
    rank_ranges[k] = {"E0": rng_(pick(group="main", label="E0", k=k, m=3, mode="plain", target_kind="random")),
                      "sparse": rng_(pooled(sparse, k=k, m=3, mode="plain", target_kind="random")),
                      "dense": rng_(pooled(dense, k=k, m=3, mode="plain", target_kind="random")),
                      "class_desc": rng_([r for lab in ("A000", "B000", "A010") for r in
                                          pick(group="main", label=lab, k=k, m=3, mode="plain", target_kind="random")])}
pw = summary([r for r in flats if r["status"] == "ok" and r["label"] == "E0" and r["sub"] == "powerw" and r["k"] == 6
              and r["m"] == 3 and r["mode"] == "codex" and r["target_kind"] == "image"], "formal_d_reg")
ad = summary([r for r in flats if r["status"] == "ok" and r["sub"] in ("shiftb", "powerb") and r["k"] == 6
              and r["m"] == 3 and r["mode"] == "codex" and r["target_kind"] == "image"], "formal_d_reg")
R["Q2"] = {"answer": (
    f"Partly. The mechanism is the one the review named, but E0 is not inside the sparse-b spread: it sits between the "
    f"sparse-b and dense-b groups. k = 6, codex system, image targets, formal d_reg: E0 {c6['E0']['hist']}; 10 sparse-b "
    f"curves (b = 1+z^j or z^129(+z^j), Tr(b) = 1) {c6['sparse_b_pooled']['hist']}; b = z (Tr 0, the review's example) "
    f"{c6['b_eq_z_TrB0']['hist']}; 10 dense-b curves {c6['dense_b_pooled']['hist']}. Plain system, planted targets: "
    f"E0 {p6['E0']['hist']}, sparse {p6['sparse_b_pooled']['hist']}, dense {p6['dense_b_pooled']['hist']}. "
    f"The number of independent descended equations (random targets, m = 3) orders the same way: k = 4/5/6 E0 "
    f"{rank_ranges[4]['E0']}/{rank_ranges[5]['E0']}/{rank_ranges[6]['E0']}, sparse {rank_ranges[4]['sparse']}/"
    f"{rank_ranges[5]['sparse']}/{rank_ranges[6]['sparse']}, dense {rank_ranges[4]['dense']}/{rank_ranges[5]['dense']}/"
    f"{rank_ranges[6]['dense']}, A000/B000/A010 {rank_ranges[4]['class_desc']}/{rank_ranges[5]['class_desc']}/"
    f"{rank_ranges[6]['class_desc']} (the review's 65/90/116 vs 76/107/131 reproduced). It is a representation artifact in "
    f"the sense that it follows the subspace, not the curve: E0 on span{{w^j}} for 3 random dense w gives "
    f"{pw['hist'] if pw else None} (b = 1 = w^0 in every power basis), and the class and dense curves on span{{b^j}} or "
    f"span{{(b+1)^j}} give {ad['hist'] if ad else None}, i.e. the sparse-b value (Q3)."),
    "k6_codex_image": c6, "k6_plain_planted": p6, "k6_plain_random": r6, "rank_ranges_random_targets": rank_ranges}

# ---------------- Q3
def subrows(lab, sub, k, m, mode, tk, sub_idx=None):
    kw = dict(label=lab, sub=sub, k=k, m=m, mode=mode, target_kind=tk)
    if sub_idx is not None:
        kw["sub_idx"] = sub_idx
    return pick(**kw)


q3 = {}
for lab in ("E0", "A000", "B000", "A010", "RD00", "RD01"):
    for k in (4, 5, 6):
        for (m, mode, tk) in ((3, "codex", "image"), (3, "plain", "planted"), (3, "plain", "random")):
            for key in ("formal_d_reg", "desc_rank", "msolve_cpu_reported", "msolve_max_degree"):
                d = {}
                for sub in ("poly", "rand", "scaled", "powerw", "powerb", "shiftb"):
                    rs = subrows(lab, sub, k, m, mode, tk)
                    if rs:
                        d[sub] = summary(rs, key) or {"n": len(rs), "values": "none (all timed out)"}
                        d[sub]["timeouts"] = sum(1 for r in rs if (r["formal_status"] == "timeout" if key == "formal_d_reg" else r["msolve_status"] == "timeout"))
                if d:
                    q3[f"{lab}_k{k}_m{m}_{mode}_{tk}_{key}"] = d
R["subspace_controls"] = q3
k7 = S["k7_runs"]


def k7sum(lab, sub, tk):
    rs = [r for r in k7 if r["label"] == lab and r.get("sub", "poly0") == sub and r["target_kind"] == tk and r["mode"] == "plain"]
    v = [r["msolve_cpu_reported"] for r in rs if r["msolve_cpu_reported"] is not None]
    return {"n": len(rs), "f4_cpu_s": v, "max_degree": sorted({r["msolve_max_degree"] for r in rs if r["msolve_max_degree"]}),
            "desc_rank": sorted({r["desc_rank"] for r in rs}), "agrees_bruteforce": all(r["msolve_agrees"] for r in rs)} if rs else None


k7tab = {}
for lab, sub in (("E0", "poly0"), ("A000", "poly0"), ("B000", "poly0"), ("A010", "poly0"), ("RD00", "poly0"), ("RD01", "poly0"),
                 ("RS00", "poly0"), ("RS02", "poly0"), ("RS05", "poly0"), ("RS06", "poly0"), ("E0", "scaled0"), ("E0", "scaled1"),
                 ("E0", "powerw0"), ("A000", "shiftb0"), ("B000", "shiftb0"), ("A010", "shiftb0"), ("RD00", "shiftb0"),
                 ("A000", "powerb0"), ("RD00", "powerb0")):
    k7tab[f"{lab}_{sub}"] = {"random": k7sum(lab, sub, "random"), "planted": k7sum(lab, sub, "planted")}
R["k7_m3_plain_msolve"] = k7tab


def medk7(key):
    v = k7tab[key]["random"]["f4_cpu_s"] if k7tab[key]["random"] else []
    return st.median(v) if v else None


e0s = {s: q3.get(f"E0_k6_m3_codex_image_formal_d_reg", {}).get(s) for s in ("poly", "rand", "scaled", "powerw")}


def rs_stats(lab, k, m, mode, tk):
    rs = subrows(lab, "rand", k, m, mode, tk)
    if not rs:
        return None
    return {"n": len(rs), "formal_d_reg": hist(rs, "formal_d_reg"),
            "formal_timeouts": sum(1 for r in rs if r["formal_status"] == "timeout"),
            "desc_rank": hist(rs, "desc_rank"), "msolve_max_degree": hist(rs, "msolve_max_degree"),
            "msolve_f4_cpu_median": med(rs, "msolve_cpu_reported"),
            "msolve_timeouts": sum(1 for r in rs if r["msolve_status"] == "timeout"),
            "msolve_process_cpu_at_timeout_median": med([r for r in rs if r["msolve_status"] == "timeout"], "msolve_process_cpu")}


randsub = {f"{lab}_k{k}_{mode}_{tk}": rs_stats(lab, k, 3, mode, tk)
           for lab in ("E0", "A000", "RD00", "RD01") for k in (4, 5, 6)
           for (mode, tk) in (("codex", "image"), ("plain", "planted"), ("plain", "random"))}
R["random_subspace_m3"] = randsub


def rtxt(lab, k, mode, tk):
    d = randsub.get(f"{lab}_k{k}_{mode}_{tk}")
    if not d:
        return "n/a"
    if d["formal_timeouts"] == d["n"] and d["msolve_timeouts"] == d["n"]:
        return (f"all {d['n']} cells hit both 300 s wall caps (formal d_reg and msolve; msolve process CPU at the kill, "
                f"median {r2(d['msolve_process_cpu_at_timeout_median'])} s)")
    return (f"d_reg {d['formal_d_reg']} (timeouts {d['formal_timeouts']}), F4 max deg {d['msolve_max_degree']}, "
            f"F4 median {r2(d['msolve_f4_cpu_median'])} s (timeouts {d['msolve_timeouts']}), n = {d['n']}")


R["Q3"] = {"answer": (
    f"Yes. On c*V_k (3 dense c) E0 behaves like a dense-b curve: k = 6 codex image d_reg "
    f"{e0s['scaled']['hist'] if e0s['scaled'] else None} (on V_6: {e0s['poly']['hist'] if e0s['poly'] else None}), 131 "
    f"independent equations, and at k = 7 msolve needs median {medk7('E0_scaled0')} and {medk7('E0_scaled1')} s on two "
    f"scaled subspaces (E0 on V_7: {medk7('E0_poly0')} s; A000 {medk7('A000_poly0')}, B000 {medk7('B000_poly0')}, A010 "
    f"{medk7('A010_poly0')}, dense RD00 {medk7('RD00_poly0')} s). On random subspaces there is no structure for any curve "
    f"and E0 coincides with A000 and the dense-b curves (same 5 subspaces for E0 and A000, 2 for RD00/RD01; plain system, "
    f"random targets): k = 4 E0 {rtxt('E0', 4, 'plain', 'random')}; A000 {rtxt('A000', 4, 'plain', 'random')}; RD00 "
    f"{rtxt('RD00', 4, 'plain', 'random')}. k = 5 E0 {rtxt('E0', 5, 'plain', 'random')}; A000 {rtxt('A000', 5, 'plain', 'random')}; "
    f"RD00 {rtxt('RD00', 5, 'plain', 'random')}; RD01 {rtxt('RD01', 5, 'plain', 'random')}. k = 6 (1 target per subspace, "
    f"300 s caps): E0 {rtxt('E0', 6, 'plain', 'random')}; A000 {rtxt('A000', 6, 'plain', 'random')}. (With Codex's membership "
    f"generators the k = 4 values split 7/9 by subspace and curve, the membership-parity effect Codex already reported: "
    f"E0 {randsub['E0_k4_codex_image']['formal_d_reg'] if randsub.get('E0_k4_codex_image') else None}, A000 "
    f"{randsub['A000_k4_codex_image']['formal_d_reg'] if randsub.get('A000_k4_codex_image') else None}.) "
    f"The E0 effect survives only on power-basis subspaces span{{w^j}} (b = 1 = w^0 for every w), and any curve gets the "
    f"same effect on span{{(b+1)^j}}: A000/B000/A010/RD00 there have codex d_reg 7 at k = 6 and msolve medians "
    f"{medk7('A000_shiftb0')}/{medk7('B000_shiftb0')}/{medk7('A010_shiftb0')}/{medk7('RD00_shiftb0')} s at k = 7."),
    "E0_k6_codex_image_formal_d_reg_by_subspace": e0s}

# ---------------- Q4
a4 = {}
for k in (4, 5, 6):
    for (m, mode, tk) in ((3, "codex", "image"), (3, "plain", "planted"), (3, "plain", "random"), (2, "plain", "planted")):
        for key in ("formal_d_reg", "desc_rank", "msolve_cpu_reported", "msolve_max_degree"):
            b = q2[f"k{k}_m{m}_{mode}_{tk}_{key}"]
            a4[f"k{k}_m{m}_{mode}_{tk}_{key}"] = {x: b[x] for x in ("A000", "B000", "A010", "dense_b_pooled")}
R["Q4"] = {"answer": (
    f"No. A000, B000 and A010 are indistinguishable from the 10 dense-b random curves in every measured quantity: "
    f"k = 6 codex image d_reg A000 {c6['A000']['hist']}, B000 {c6['B000']['hist']}, A010 {c6['A010']['hist']} vs dense "
    f"{c6['dense_b_pooled']['hist']}; independent equations 131 (dense 130-131); msolve F4 max degree 6 everywhere; F4 time "
    f"medians at k = 6 (codex image) A000 {q2['k6_m3_codex_image_msolve_cpu_reported']['A000']['median']}, B000 "
    f"{q2['k6_m3_codex_image_msolve_cpu_reported']['B000']['median']}, A010 {q2['k6_m3_codex_image_msolve_cpu_reported']['A010']['median']} s "
    f"vs dense pooled {q2['k6_m3_codex_image_msolve_cpu_reported']['dense_b_pooled']['median']} s; k = 7 plain msolve "
    f"medians {medk7('A000_poly0')}/{medk7('B000_poly0')}/{medk7('A010_poly0')} s vs dense {medk7('RD00_poly0')}/{medk7('RD01_poly0')} s. "
    f"The degree-graded profiles of A000, B000, A010 equal those of the dense curves at every k computed (m = 3, k = 2..12)."),
    "tables": a4}

# ---------------- Q5
gp = S["graded_profiles"]


def gprof(m, k, lab, sub="poly"):
    for r in gp:
        if r["m"] == m and r["k"] == k and r["label"] == lab and r["sub"] == sub:
            return r["graded"][0]
    return None


gtab = {}
for m, ks in ((3, range(2, 13)), (4, range(2, 6))):
    for k in ks:
        row = {lab: gprof(m, k, lab) for lab in ("E0", "A000", "B000", "A010", "RD00", "RD01", "RS00", "RS05")}
        row["A000_shiftb"] = gprof(m, k, "A000", "shiftb")
        row["E0_scaled0"] = gprof(m, k, "E0", "scaled0")
        gtab[f"m{m}_k{k}"] = {x: y for x, y in row.items() if y is not None}
R["graded_profiles_table"] = gtab
first_equal = {}
for m, ks in ((3, range(2, 13)), (4, range(2, 6))):
    fe = None
    for k in ks:
        a, b = gprof(m, k, "E0"), gprof(m, k, "RD00")
        if a is not None and b is not None and a == b and fe is None:
            fe = k
        if a is not None and b is not None and a != b:
            fe = None
    first_equal[f"m{m}"] = fe
m4 = S["m4_runs"]
m4tab = {}
for lab in ("E0", "A000", "B000", "A010", "RD00", "RD01", "RS00"):
    rs = [r for r in m4 if r["label"] == lab and r["k"] == 3]
    if rs:
        v = [r["msolve_cpu_reported"] for r in rs if r["target_kind"] == "random" and r["msolve_cpu_reported"] is not None]
        m4tab[lab] = {"n_random": len(v), "f4_cpu_random_s": v, "median": st.median(v) if v else None,
                      "max_degree": sorted({r["msolve_max_degree"] for r in rs if r["msolve_max_degree"]}),
                      "planted_f4_cpu_s": [r["msolve_cpu_reported"] for r in rs if r["target_kind"] == "planted"],
                      "agree": all(r["msolve_agrees"] for r in rs if r["msolve_status"] == "ok"),
                      "timeouts": sum(1 for r in rs if r["msolve_status"] == "timeout")}
R["m4_k3_msolve"] = m4tab
rank_rows = S["rank_scaling"]


def rk(m, k, lab, sub="poly"):
    for r in rank_rows:
        if r["m"] == m and r["k"] == k and r["label"] == lab and r["sub"] == sub:
            return r["rank_full"][0], r["monomials"]
    return None


R["rank_and_monomials"] = {f"m{m}_k{k}": {lab: rk(m, k, lab) for lab in ("E0", "A000", "RD00", "RS00") if rk(m, k, lab)}
                           for m, ks in ((2, (4, 6, 10, 20, 40)), (3, range(2, 10)), (4, (2, 3, 4))) for k in ks}
bdep = json.loads((ROOT / "b_dependence.json").read_text())["rows"]
R["b_dependence_by_boolean_degree"] = bdep


def bfree_degrees(m):
    rows = [r for r in bdep if r["m"] == m]
    ok = None
    for r in rows:
        free = sorted(int(d) for d, v in r["by_degree"].items() if v["b_dependent"] == 0)
        ok = free if ok is None else sorted(set(ok) & set(free))
    return ok


def first_bfree(m, ks):
    free = set(bfree_degrees(m) or [])
    fk = None
    for k in ks:
        g = gprof(m, k, "E0")
        if g is None:
            continue
        if all(int(d) in free for d in g):
            fk = k if fk is None else fk
        else:
            fk = None
    return fk


fb = {"m3": first_bfree(3, range(2, 13)), "m4": first_bfree(4, range(2, 6))}
R["first_k_all_rows_in_b_free_slices"] = fb

# maximal F4 degree: E0 vs every other curve, per (subspace kind, k, m, mode, target kind) cell
cells = {}
for r in flats:
    if r["status"] != "ok" or r["msolve_max_degree"] is None:
        continue
    key = (r["sub"], r["k"], r["m"], r["mode"], r["target_kind"])
    cells.setdefault(key, {}).setdefault("E0" if r["label"] == "E0" else "other", set()).add(r["msolve_max_degree"])
maxdeg_cells = []
for key, d in sorted(cells.items(), key=lambda t: tuple(str(u) for u in t[0])):
    if "E0" in d and "other" in d:
        maxdeg_cells.append({"cell": "/".join(str(u) for u in key), "E0": sorted(d["E0"]), "others": sorted(d["other"]),
                             "same": d["E0"] == d["other"] or d["E0"] <= d["other"]})
R["msolve_max_degree_E0_vs_others"] = maxdeg_cells
n_same = sum(1 for c in maxdeg_cells if c["same"])
deg_poly = sorted({d for c in maxdeg_cells if c["cell"].startswith("poly/") and "/3/" in c["cell"] for d in c["E0"] + c["others"]})


def r2(x):
    return None if x is None else round(x, 2)


import math  # noqa: E402

_desc7 = [medk7(f"{x}_poly0") for x in ("A000", "B000", "A010")]
bits_k7 = (round(math.log2(min(_desc7) / medk7("E0_poly0")), 2), round(math.log2(max(_desc7) / medk7("E0_poly0")), 2))
_sh7 = [medk7(f"{x}_shiftb0") for x in ("A000", "B000", "A010")]
R["k7_speed_ratio_bits_desc_over_E0"] = bits_k7

R["Q5"] = {"answer": (
    f"No. (i) The degree the solver actually reaches does not separate the curves: in {n_same} of {len(maxdeg_cells)} "
    f"(subspace, k, m, system, target) cells the maximal F4 degree of E0's runs is within the set reached by the other "
    f"curves' runs (m = 3 on V_k: always {deg_poly}, the input degree), over {R['sanity']['msolve_ok_runs']} completed "
    f"msolve runs. "
    f"(ii) The one measured E0-vs-descendant difference is a set of extra low-degree equations obtainable by linear "
    f"algebra from the polynomial-basis presentation (b = 1 lies in every power basis). It shows up as lower formal d_reg "
    f"(k = 6) and as faster F4 at k = 7 (E0 median {medk7('E0_poly0')} s vs {min(_desc7)}-{max(_desc7)} s for A000/B000/A010, "
    f"{bits_k7[0]}-{bits_k7[1]} bits), but every class curve obtains the same speed on span{{(b+1)^j}} "
    f"({min(_sh7)}-{max(_sh7)} s), so min over presentations, which is what an attacker pays, is the "
    f"same for E0 and the descendants. (iii) The effect dies with k: E0's degree-graded row profile equals that of dense-b "
    f"curves from k = {first_equal['m3']} for m = 3 (checked to k = 12) and from k = {first_equal['m4']} for m = 4 (checked "
    f"to k = 5), and stays equal at every larger k computed. Beyond that point every curve has 131 independent equations and "
    f"the same linear-algebra degree falls (in the polynomial basis all curves keep some: m = 3, k = 12: {gprof(3, 12, 'E0')}; "
    f"m = 4, k = 5: {gprof(4, 5, 'E0')}). Reason (b_dependence.json): only the Boolean-degree slices "
    f"{bfree_degrees(3)} (m = 3) and {bfree_degrees(4)} (m = 4) of the descended polynomial are independent of b; all lower "
    f"slices depend on b. Once the b-free slices alone have rank 131 (m = 3 from k = {fb['m3']}, m = 4 from k = {fb['m4']} "
    f"in the graded profiles) every row has its top degree there, and because V_k is contained in V_(k+1) that rank cannot drop again, so "
    f"the linear-algebra profile is the same for every curve at all larger k. Realistic l (m = 4..6, l = 24..29 in experiments/pdp-scaling) lies far beyond the crossover; that "
    f"the profiles stay equal there is this argument plus the measured trend, not a measurement at l = 29. "
    f"E0's only persistent structural difference is a "
    f"slightly smaller monomial support (m = 3 k = 9: 91288 vs 91396, -0.12%; m = 4 k = 4: 41889 vs 42529, -1.5%), "
    f"worth < 0.03 bit even if cost were proportional to the support. At m = 4, k = 3 (where the profiles still differ "
    f"slightly) msolve medians over 10 random targets are E0 {r2(m4tab.get('E0', {}).get('median'))} s vs "
    f"A000 {r2(m4tab.get('A000', {}).get('median'))}, B000 {r2(m4tab.get('B000', {}).get('median'))}, "
    f"A010 {r2(m4tab.get('A010', {}).get('median'))}, RD00 {r2(m4tab.get('RD00', {}).get('median'))}, "
    f"RD01 {r2(m4tab.get('RD01', {}).get('median'))}, RS00 {r2(m4tab.get('RS00', {}).get('median'))} s (target-to-target spread dominates). Bound: no measured difference "
    f"changes the index-calculus cost by more than 1 bit at realistic l; per-curve summation-polynomial hardness is "
    f"class-invariant up to the choice of presentation."),
    "first_k_where_E0_profile_equals_dense": first_equal}

R["anomalies"] = [
    "Output went to gaps/G5-per-curve-summation-polynomial-n131/ (the task's deliverable path); the task's rule line also "
    "named verify/index-calculus/sumpoly-real-n131/, where nothing was written.",
    "Codex's 'd_reg' is a formal, presentation-dependent Hilbert regularity of the top-form ideal after row reduction; "
    "msolve's F4 never exceeded the input degree (6) on any polynomial-basis m = 3 system while that formal value was 0 (unit after row reduction) or 7-13.",
    "E0 is not inside the sparse-b spread: k = 6 codex image d_reg 7 for all 50 sparse-b targets and 5 b = z targets, 8 for "
    "8/10 E0 targets, 10-11 for dense-b.  Same mechanism (subspace alignment), different degree of alignment (b in F_2).",
    "Polynomial-basis (and any power-basis) subspaces make the PDP systems far easier for every curve than random subspaces: "
    "k = 5 plain random targets F4 median 0.01 s on V_5 vs 11.6-13.2 s on random subspaces (max degree 7 there); k = 6 "
    "random-subspace cells all exceed 300 s.  This class-wide presentation effect is much larger than any curve effect.",
    "For k <= 5 (all curves) and k = 6 (E0, sparse-b, adapted subspaces) random-target systems are inconsistent by linear "
    "algebra alone (constant term outside the span of the other coefficients), so their 'd_reg' is 0 and says nothing about "
    "solving hardness.",
    "Wall-clock caps were used while the machine had load average 28-48 from other jobs; reported F4 times are msolve's own CPU "
    "times.  m = 4, k = 4 msolve hit the 600 s cap on E0's first random target and was not pursued; Codex's k = 7 formal "
    "d_reg cells time out at 600 s here (30 s in Codex).",
    "Control target counts: main curves 10 random + 5 planted (plain) and 10 image + 10 random (codex); control jobs 5+3 and "
    "5+5; random-subspace k = 6 jobs 1+1 and 1 with 300 s caps.",
    "b = z (Tr 0, the review's example) has a 2-part of order 4096, so its image/planted targets are not restricted to the odd "
    "subgroup.",
    "E0's within-curve spread at k = 6 (codex image): one target has 104 independent equations and formal d_reg 11, like a "
    "descendant; the E0 distribution is not a single value.",
    "msolve here is 0.9.5; experiments/pdp-scaling used 0.10.1.",
]

# -------- per-curve file for the class curves measured individually
per_curve = {}
for lab in ("E0", "A000", "B000", "A010", "A112", "A127", "B095"):
    rec = {"orbit": "crater" if lab == "E0" else lab[0], "measured_in": []}
    for k in (4, 5, 6):
        for (m, mode, tk) in ((3, "codex", "image"), (3, "codex", "random"), (3, "plain", "planted"), (3, "plain", "random"),
                              (2, "plain", "planted"), (2, "plain", "random")):
            rs = pick(group="main", label=lab, k=k, m=m, mode=mode, target_kind=tk)
            if rs:
                rec[f"k{k}_m{m}_{mode}_{tk}"] = {"n": len(rs), "formal_d_reg": hist(rs, "formal_d_reg"),
                                                 "desc_rank": hist(rs, "desc_rank"),
                                                 "msolve_max_degree": hist(rs, "msolve_max_degree"),
                                                 "msolve_f4_cpu_median_s": med(rs, "msolve_cpu_reported"),
                                                 "bf_solutions": hist(rs, "bf_solutions")}
                if "grid_main" not in rec["measured_in"]:
                    rec["measured_in"].append("grid_main")
    cr = [r for r in S["Q1"]["codex_k6_cells_reproduced"] if r["label"] == lab]
    if cr:
        rec["codex_run03_k6_cell"] = cr[0]
        rec["measured_in"].append("codex_repro")
    for sub in ("poly0", "shiftb0", "powerb0"):
        t = k7tab.get(f"{lab}_{sub}")
        if t and t["random"]:
            rec[f"k7_m3_plain_{sub}"] = t
            rec["measured_in"].append(f"k7_{sub}")
    if lab in m4tab:
        rec["m4_k3_msolve"] = m4tab[lab]
        rec["measured_in"].append("m4_k3")
    for sub in ("rand", "scaled", "powerw", "powerb", "shiftb"):
        for k in (4, 5, 6):
            rs = [r for r in flats if r["status"] == "ok" and r["label"] == lab and r["sub"] == sub and r["k"] == k
                  and r["m"] == 3 and r["mode"] == "codex" and r["target_kind"] == "image"]
            if rs:
                rec[f"k{k}_m3_codex_image_{sub}"] = {"n": len(rs), "formal_d_reg": hist(rs, "formal_d_reg"),
                                                     "desc_rank": hist(rs, "desc_rank"),
                                                     "msolve_max_degree": hist(rs, "msolve_max_degree"),
                                                     "msolve_f4_cpu_median_s": med(rs, "msolve_cpu_reported")}
    per_curve[lab] = rec
(ROOT / "per_curve.json").write_text(json.dumps(per_curve, indent=1, default=str))
R["per_curve_file"] = str(ROOT / "per_curve.json")

R["files"] = {
    "results.json": "this file (answers Q1-Q5, all comparison tables, anomalies)",
    "runs.csv": "every grid run (one row per system: curve, subspace, k, m, system, target, formal d_reg, msolve data)",
    "runs_all.csv": "runs.csv + the k = 7, m = 4 and Codex-reproduction runs (column 'source')",
    "per_curve.json": "per class curve (E0, A000, B000, A010, A112, A127, B095) summaries",
    "summary_tables.json": "analyze.py output (per-cell distributions)",
    "raw/grid/*.jsonl": "full grid records incl. msolve per-round tables, Hilbert functions, solution classes",
    "raw/codex_repro_*.json": "Codex run-03 k = 6 cell reproductions", "raw/k7/*.json": "k = 7 runs",
    "raw/m4/*.json": "m = 4 (S5) runs", "rank_scaling.json": "independent-equation counts vs k",
    "graded_profile.json, graded_extra.json": "degree-graded RREF profiles vs k",
    "b_dependence.json": "which Boolean-degree slices depend on b", "indep_hilbert.json": "Singular-free Hilbert check",
    "controls.json": "control curves (point-counted), subspaces, constants", "selftest.json": "library self-tests",
    "inputs_codex_run03/, inputs_sha256.txt": "Codex inputs used and hashes", "scripts/": "all code (see docstrings)",
    "logs/": "run logs", "scratch/": "probe scripts (random-subspace cost probe, trace table, Tr(b)=0 torsion test)",
}
(ROOT / "results.json").write_text(json.dumps(R, indent=1, default=str))

# -------- runs_all.csv: grid rows + k7 + m4 + Codex reproduction
extra = []
for r in S["k7_runs"]:
    extra.append({"source": "k7", "label": r["label"], "sub": r.get("sub"), "k": 7, "m": 3, "mode": r["mode"],
                  "target_kind": r["target_kind"], "target_idx": r["target_idx"], "desc_rank": r["desc_rank"],
                  "bf_solutions": r["bf_solutions"], "formal_status": r["formal_status"], "formal_d_reg": r["formal_d_reg"],
                  "formal_top_quotient_dim": r["formal_top_quotient_dim"], "msolve_status": r["msolve_status"],
                  "msolve_max_degree": r["msolve_max_degree"], "msolve_cpu_reported": r["msolve_cpu_reported"],
                  "msolve_max_matrix_rows": (r["msolve_max_matrix"] or [None])[0], "msolve_agrees_bruteforce": r["msolve_agrees"]})
for r in S["m4_runs"]:
    extra.append({"source": "m4", "label": r["label"], "sub": "poly0", "k": r["k"], "m": 4, "mode": "plain",
                  "target_kind": r["target_kind"], "target_idx": r["target_idx"], "desc_rank": r["desc_rank"],
                  "bf_solutions": r["bf_solutions"], "msolve_status": r["msolve_status"],
                  "msolve_max_degree": r["msolve_max_degree"], "msolve_cpu_reported": r["msolve_cpu_reported"],
                  "msolve_max_matrix_rows": (r["msolve_max_matrix"] or [None])[0], "msolve_agrees_bruteforce": r["msolve_agrees"]})
for r in S["Q1"]["codex_k6_cells_reproduced"]:
    extra.append({"source": "codex_repro", "label": r["label"], "sub": "poly0", "k": 6, "m": 3, "mode": "codex",
                  "target_kind": "codex_run03_target", "target_idx": 0, "desc_rank": r["descended_rank"],
                  "formal_status": "verified", "formal_d_reg": r["d_reg"], "formal_top_quotient_dim": r["top_quotient_dim"],
                  "msolve_status": "ok", "msolve_max_degree": r["msolve_max_degree"], "msolve_cpu_reported": r["msolve_cpu_reported"]})
fields = ["source"] + list(flats[0].keys())
with open(ROOT / "runs_all.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for r in flats:
        w.writerow({"source": "grid", **r})
    for r in extra:
        w.writerow({x: r.get(x) for x in fields})
print(json.dumps({q: R[q]["answer"] for q in ("Q1", "Q2", "Q3", "Q4", "Q5")}, indent=1))
