#!/usr/bin/env python3
"""Stage 0 (zero compute) for IDEA-20261015-7a3c9e and IDEA-20261015-b41f68.

Reads receipts already committed in crypto and cryptanalysis and computes:

A. per experiment row: measured probes per target against r/(A*#states)
   (prediction 1), and the price product c_probe*c_state/(2.1*c_step^2)
   against the IC/BL online ratio (prediction 2), each row from ONE
   experiment's own receipts; the slope of ln(IC/BL) on ln r (prediction 3).
B1. per probe panel: CV, median/mean, max/mean, and a Lilliefors-type KS test
   of the exponential (geometric) model with a parametric bootstrap p-value.
B2. IC ns/probe against root-table bytes.

Pure Python (no numpy). Deterministic (fixed seeds).

    python3 -I stage0.py --crypto /path/crypto --cryptanalysis-main DIR \
        --bl-arm DIR --out analysis.json
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import math
import os
import random
import statistics as st

C_BL = 2.1          # the idea's BL constant, 1.77*1.2
BOOT = 10_000
KS_BOOT = 2_000


def mean(x):
    return sum(x) / len(x)


def boot_mean_ci(x, seed, f=mean):
    rng = random.Random(seed)
    n = len(x)
    vals = sorted(f([x[rng.randrange(n)] for _ in range(n)]) for _ in range(BOOT))
    return [vals[int(0.025 * BOOT)], vals[int(0.975 * BOOT) - 1]]


def boot_ratio_ci(num, den, seed):
    """mean(num)/mean(den), paired resampling over targets."""
    rng = random.Random(seed)
    n = len(num)
    vals = []
    for _ in range(BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(mean([num[i] for i in idx]) / mean([den[i] for i in idx]))
    vals.sort()
    return [vals[int(0.025 * BOOT)], vals[int(0.975 * BOOT) - 1]]


def cv(x):
    return st.pstdev(x) / mean(x) if len(x) > 1 else None


def ks_exp(x):
    """KS distance of the sample to Exp(mean = sample mean)."""
    m = mean(x)
    s = sorted(x)
    n = len(s)
    d = 0.0
    for i, v in enumerate(s):
        F = 1.0 - math.exp(-v / m)
        d = max(d, abs(F - i / n), abs((i + 1) / n - F))
    return d


def lilliefors_exp(x, seed):
    """Parametric-bootstrap p-value for H0: exponential with unknown mean."""
    d0 = ks_exp(x)
    rng = random.Random(seed)
    n = len(x)
    ge = 0
    for _ in range(KS_BOOT):
        y = [rng.expovariate(1.0) for _ in range(n)]
        if ks_exp(y) >= d0:
            ge += 1
    return d0, (ge + 1) / (KS_BOOT + 1)


def cv_null_interval(n, seed):
    """2.5-97.5% of the sample CV of n exponential draws (the model's own spread)."""
    rng = random.Random(seed)
    vals = sorted(cv([rng.expovariate(1.0) for _ in range(n)]) for _ in range(KS_BOOT))
    return [vals[int(0.025 * KS_BOOT)], vals[int(0.975 * KS_BOOT) - 1]]


def distribution(name, source, probes, seed, states=None, r=None, A=None):
    p = [float(v) for v in probes]
    d0, pval = lilliefors_exp(p, seed)
    out = {
        "panel": name, "source": source, "N": len(p),
        "mean": mean(p), "median": st.median(p), "max": max(p),
        "cv": cv(p), "cv_ci95_bootstrap": boot_mean_ci(p, seed + 1, cv),
        "cv_exponential_null_95": cv_null_interval(len(p), seed + 2),
        "median_over_mean": st.median(p) / mean(p),
        "max_over_mean": max(p) / mean(p), "ln_N_plus_1": math.log(len(p)) + 1,
        "ks_D_vs_exponential": d0, "ks_p_parametric_bootstrap": pval,
        "cv_in_falsification_band_0.6_1.5": 0.6 <= cv(p) <= 1.5,
        "cv_in_prediction_band_0.9_1.1": 0.9 <= cv(p) <= 1.1,
        "median_over_mean_in_0.6_0.8": 0.6 <= st.median(p) / mean(p) <= 0.8,
    }
    if states:
        out["predicted_mean"] = r / (A * states)
    return out


# ---------------------------------------------------------------- loaders

def s23(crypto):
    """Ledger section 23 receipts: research/ic_single_target_20260930/runs."""
    base = os.path.join(crypto, "research/ic_single_target_20260930/runs")
    sizes = []
    for d in sorted(glob.glob(os.path.join(base, "k*n*"))):
        tag = os.path.basename(d)
        rows = []
        for t in range(1, 65):
            f = os.path.join(d, f"T{t:02d}-R1.price.json")
            rep = json.load(open(f))
            at = rep["median"]["ic_online_repetition"]
            R = rep["repetitions"][at]
            rows.append({
                "probes": rep["counts"]["pass"]["descent"]["trials_per_target"][0],
                "ic_ns": rep["median"]["ic_online_wall_ns"],
                "pdp_ns": rep["median"]["ic_online_phases_ns"]["target_pdp"],
                "query_ns": rep["median"]["ic_online_phases_ns"]["target_query"],
                "setup_ns": st.median(x["setup_ns"] for x in rep["repetitions"]),
                "rho_ns": rep["median"]["rho_online_phases_ns"]["rho_solve"],
                "rho_steps": rep["rho_counts"]["steps"],
                "states": rep["counts"]["pass"]["build"]["stored_pairs"],
                "points": rep["counts"]["pass"]["select"]["points"],
                "m": rep["recipe"]["descent_summands"],
                "r": rep["r"], "n": rep["n"], "a": rep["a"], "curve": rep["curve"],
            })
        assert len({x["states"] for x in rows}) == 1
        sizes.append((tag, rows))
    analysis = json.load(open(os.path.join(crypto, "research/ic_single_target_20260930/analysis.json")))
    model_col = {(s["a"], s["n"]): s["precomputation_boundary_model"]["ic_online_over_bl"]
                 for s in analysis["sizes"]}
    return sizes, model_col


def n61_hosted(crypto):
    d = os.path.join(crypto, "research/sat_factor_base_review_20260908/autolab/evidence/"
                     "20261003-koblitz-n61-hosted-isolated/autolab_runs/gha-37156392134-1/logs")
    rows = []
    for w in range(256):
        ic = json.loads(open(os.path.join(d, f"ic_w{w:03d}.jsonl")).readline())
        sm = json.load(open(os.path.join(d, f"ic_w{w:03d}.summary.json")))
        rho = json.loads(open(os.path.join(d, f"rho_w{w:03d}.jsonl")).readline())
        assert ic["published_q"] == rho["published_q"]
        rows.append({"probes": ic["probes"], "ic_ns": ic["online_ms"] * 1e6,
                     "pdp_ns": ic.get("target_pdp_ms", ic["online_ms"]) * 1e6,
                     "setup_ns": sm["setup_complete_ns"],
                     "rho_ns": rho["walk_and_collision_ms"] * 1e6, "rho_steps": rho["walk_steps"],
                     "states": sm["root_table_entries"], "regular_states": sm["regular_states"],
                     "rss": sm["peak_rss_bytes"], "n": 61, "a": 0})
    return rows


def dense_root(crypto):
    base = os.path.join(crypto, "research/n83_dense_root_20261013")
    panel = json.load(open(os.path.join(base, "analysis_panel.json")))
    out = {}
    for arm in panel["arms"]:
        if arm.get("status") != "PASS_INDEPENDENT_REPLAY":
            continue
        rows = [json.loads(l) for l in open(os.path.join(base, "runs/panel", arm["arm"], "targets_result.jsonl"))]
        out[arm["arm"]] = {"arm": arm, "rows": rows}
    rho = json.load(open(os.path.join(base, "runs/rho_primary/receipt.json")))
    return out, rho


def k600_bl(bl_dir):
    rows = [json.loads(l) for l in open(os.path.join(bl_dir, "panel/runs.jsonl"))]
    ic = [r for r in rows if r["arm"] == "ic" and r["panel"] == "F"]
    bl = [r for r in rows if r["arm"] == "bl" and r["panel"] == "F"]
    rho = [r for r in rows if r["arm"] == "rho" and r["panel"] == "F"]
    key = lambda r: r["fields"]["target_sha256"]
    bl_by = {key(r): r for r in bl}
    rho_by = {key(r): r for r in rho}
    # IC table geometry from the first IC producer record.
    raw = open(os.path.join(bl_dir, "panel/runs", os.path.basename(ic[0]["stdout_file"]))).read()
    rec = json.loads(base64.b64decode(raw.split("raw_b64=", 1)[1].split()[0]))
    summ = [x for x in rec["records"] if x["kind"] == "compact_orbit_dlp_summary"][0]
    pre = json.load(open(os.path.join(bl_dir, "ic_precompute/precompute_receipt.json")))
    blp = json.load(open(os.path.join(bl_dir, "bl/precompute_receipt.json")))
    res = json.load(open(os.path.join(bl_dir, "result.json")))
    out = []
    for r in ic:
        k = key(r)
        out.append({"probes": int(r["fields"]["ops"]), "ic_ns": float(r["fields"]["online_ms"]) * 1e6,
                    "bl_ns": float(bl_by[k]["fields"]["online_ms"]) * 1e6,
                    "bl_steps": int(bl_by[k]["fields"]["ops"]),
                    "rho_ns": float(rho_by[k]["fields"]["online_ms"]) * 1e6,
                    "rho_steps": int(rho_by[k]["fields"]["ops"])})
    return out, summ, pre, blp, res


def k600_tier1(t1_dir):
    rows = []
    for f in sorted(glob.glob(os.path.join(t1_dir, "claims/B/B_B-w*_r0.claim.json"))):
        c = json.load(open(f))
        rows.append({"probes": c["counts"]["ic_probes"], "ic_ns": c["ic_online_ms"] * 1e6,
                     "rho_ns": c["rho_online_ms"] * 1e6, "rho_steps": c["counts"]["rho_walk_steps"],
                     "rank_ms": c["cold"]["ic_rank_stage_ms_once"],
                     "setup_ms": c["cold"]["ic_setup_ms_per_process"]})
    pre = json.load(open(os.path.join(t1_dir, "precompute/precompute_receipt.json")))
    return rows, pre


def k600_reconcile(rc_dir):
    rows = [json.loads(l) for l in open(os.path.join(rc_dir, "panel/runs.jsonl"))]
    ic = [r for r in rows if r["arm"] == "iB770c" and r["fields"]["panel"] != "q0"]
    rT = [r for r in rows if r["arm"] == "rT770" and r["fields"]["panel"] != "q0"]
    fresh_rank = [r for r in rows if r["arm"] == "iB770f"]
    return ic, rT, fresh_rank


# ---------------------------------------------------------------- rows

def price_row(name, source, r, A, states, probes, ic_ns, setup_ns, rho_ns, rho_steps,
              seed, c_step_what, P_what, bl_ns=None, bl_steps=None, extra=None):
    pred = r / (A * states)
    mprobe = mean(probes)
    c_probe = mean(ic_ns) / mprobe
    P = setup_ns
    c_state = P / states
    c_step = mean(rho_ns) / mean(rho_steps)
    formula = c_probe * c_state / (C_BL * c_step ** 2)
    bl_model_ns = C_BL * (r / A) * c_step ** 2 / P
    row = {
        "row": name, "source": source, "log2_r": math.log2(r), "A": A, "states": states,
        "targets": len(probes),
        "probes_mean": mprobe, "probes_mean_ci95": boot_mean_ci(probes, seed),
        "probes_predicted": pred, "probe_ratio": mprobe / pred,
        "probe_ratio_ci95": [v / pred for v in boot_mean_ci(probes, seed)],
        "probe_ratio_in_0.85_1.15": 0.85 <= mprobe / pred <= 1.15,
        "probe_ratio_in_0.7_1.3": 0.7 <= mprobe / pred <= 1.3,
        "c_probe_ns": c_probe, "c_probe_status": "measured: mean IC online ns / mean probes, same rows",
        "c_state_ns": c_state, "c_state_status": f"measured P / #states by definition; P = {P_what}",
        "P_ms": P / 1e6,
        "c_step_ns": c_step, "c_step_status": f"measured: mean walk ns / mean steps, {c_step_what}",
        "formula_ratio": formula,
        "ic_online_mean_ms": mean(ic_ns) / 1e6,
        "bl_model_online_ms_c2.1": bl_model_ns / 1e6,
        "ic_over_bl_model_c2.1": mean(ic_ns) / bl_model_ns,
    }
    if bl_ns is not None:
        row["bl_online_mean_ms_measured"] = mean(bl_ns) / 1e6
        row["ic_over_bl_measured"] = mean(ic_ns) / mean(bl_ns)
        row["ic_over_bl_measured_ci95"] = boot_ratio_ci(ic_ns, bl_ns, seed + 7)
        row["formula_over_measured"] = formula / row["ic_over_bl_measured"]
        row["within_factor_3"] = 1 / 3 <= row["formula_over_measured"] <= 3
        row["within_factor_10"] = 0.1 <= row["formula_over_measured"] <= 10
        row["bl_steps_mean"] = mean(bl_steps)
        row["bl_steps_model_c2.1"] = C_BL * (r / A) / (P / c_step)
        row["bl_measured_over_model_c2.1"] = mean(bl_ns) / bl_model_ns
    else:
        row["ic_over_bl_measured"] = None
        row["formula_over_measured"] = None
        row["prediction2_status"] = ("not testable: no BL arm ran in this experiment; "
                                     "formula / (IC over BL model) = predicted / measured probes by algebra")
    if extra:
        row.update(extra)
    return row


def slope(xs, ys):
    k = len(xs)
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    res = [y - (my + b * (x - mx)) for x, y in zip(xs, ys)]
    se = math.sqrt(sum(e * e for e in res) / (k - 2) / sxx) if k > 2 else float("nan")
    t = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447}.get(k - 2, 1.96)
    return {"slope": b, "ci95": [b - t * se, b + t * se], "points": k}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crypto", required=True)
    ap.add_argument("--n83-tier1", required=True)
    ap.add_argument("--reconcile", required=True)
    ap.add_argument("--bl-arm", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    price_rows, dists = [], []
    seed = 20261015

    # section 23
    sizes, model_col = s23(a.crypto)
    s23_slope_pts = []
    for tag, rows in sizes:
        r, n, m = rows[0]["r"], rows[0]["n"], rows[0]["m"]
        A = 2 * n
        row = price_row(
            f"s23 {tag} (m={m})", "crypto research/ic_single_target_20260930/runs/" + tag,
            r, A, rows[0]["states"], [x["probes"] for x in rows], [x["ic_ns"] for x in rows],
            st.median(x["setup_ns"] for x in rows), [x["rho_ns"] for x in rows],
            [x["rho_steps"] for x in rows], seed, "ParallelRho, 64 lanes, same process",
            "median setup_ns over 64 rows (whole reusable setup)",
            extra={"design": "pair_table, descent_summands=%d" % m,
                   "in_scope_of_claim": m == 2,
                   "s23_model_column": model_col[(rows[0]["a"], n)],
                   "c_probe_lookup_only_ns": mean([x["pdp_ns"] for x in rows]) / mean([x["probes"] for x in rows]),
                   "lookup_share": mean([x["pdp_ns"] for x in rows]) / mean([x["ic_ns"] for x in rows]),
                   "table_bytes": None})
        price_rows.append(row)
        s23_slope_pts.append((math.log(r), row))
        dists.append(distribution(f"s23 {tag} (m={m})", row["source"], [x["probes"] for x in rows],
                                  seed + n, rows[0]["states"], r, A))
        seed += 101

    # n=61 hosted isolated, W=256, K500
    n61 = n61_hosted(a.crypto)
    r61 = sizes[[t for t, _ in sizes].index("k0n61")][1][0]["r"]
    row = price_row("n61 a=0 K500 root index, GHA 37156392134 (W=256)",
                    "crypto research/sat_factor_base_review_20260908/autolab/evidence/20261003-koblitz-n61-hosted-isolated/autolab_runs/gha-37156392134-1",
                    r61, 122, n61[0]["states"], [x["probes"] for x in n61], [x["ic_ns"] for x in n61],
                    st.median(x["setup_ns"] for x in n61), [x["rho_ns"] for x in n61],
                    [x["rho_steps"] for x in n61], seed, "rho_ks_batch signed-Frobenius walk, same job",
                    "median setup_complete_ns per process (base+index+rank+LA)",
                    extra={"design": "PDP4 S3 root index (four summands)", "in_scope_of_claim": "m=4 root index",
                           "table_bytes": None, "peak_rss_bytes": st.median(x["rss"] for x in n61)})
    price_rows.append(row)
    dists.append(distribution("n61 K500 root index (W=256, GHA 37156392134)", row["source"],
                              [x["probes"] for x in n61], seed, n61[0]["states"], r61, 122))
    seed += 101

    # n=83 dense root panel (one experiment, four arms, Apple M4 Pro shared host)
    dr, drho = dense_root(a.crypto)
    r83 = 8569786107849059
    for arm, d in dr.items():
        ar, rows = d["arm"], d["rows"]
        P = (ar["setup_ms"] + ar["rank_ms"] + ar["linear_algebra_ms"]) * 1e6
        rho_ns = [drho["target_ms"] * 1e6]
        rho_steps = [drho["outcome"]["walk_steps"]]
        row = price_row(f"n83 {arm} (dense-root panel)", "crypto research/n83_dense_root_20261013",
                        r83, 166, ar["root_table_entries"], [x["probes"] for x in rows],
                        [x["target_ms"] * 1e6 for x in rows], P, rho_ns, rho_steps, seed,
                        "fold-L64-DP6 rho on ONE primary point (runs/rho_primary), same host and study",
                        "setup_ms + rank_ms + linear_algebra_ms of the panel arm (12 rank threads)",
                        extra={"design": "PDP4 packed root index", "in_scope_of_claim": "m=4 root index",
                               "table_bytes": ar["root_table_allocated_bytes"],
                               "host": "shared Apple M4 Pro, unisolated (exploratory timings)"})
        price_rows.append(row)
        dists.append(distribution(f"n83 {arm} (64 pts)", row["source"], [x["probes"] for x in rows],
                                  seed, ar["root_table_entries"], r83, 166))
        seed += 101

    # n=83 K600: three GitHub runs, one row each
    bl_rows, summ, pre, blp, res = k600_bl(a.bl_arm)
    states600 = summ["root_table_entries"]
    P_bl = pre["P_IC_ms"] * 1e6
    row = price_row("n83 K600, BL arm run 38689817618", "cryptanalysis experiments/koblitz-n83-bl-arm-20261014/run_github_38689817618",
                    r83, 166, states600, [x["probes"] for x in bl_rows], [x["ic_ns"] for x in bl_rows],
                    P_bl, [x["rho_ns"] for x in bl_rows], [x["rho_steps"] for x in bl_rows], seed,
                    "rT770 tuned rho (Fold/64/DP6), same job, same 16 points",
                    "P_IC = rank stage + setup on the execution CPU (the BL budget)",
                    bl_ns=[x["bl_ns"] for x in bl_rows], bl_steps=[x["bl_steps"] for x in bl_rows],
                    extra={"design": "PDP4 S3 root index (wide path)", "in_scope_of_claim": "m=4 root index",
                           "table_bytes": None, "peak_rss_bytes": summ["peak_rss_bytes"],
                           "c_step_bl_precompute_ns": blp["producer"]["ns_per_step"],
                           "formula_with_bl_precompute_step": None,
                           "result_json_ic_over_bl": res.get("primary", res).get("value") if isinstance(res.get("primary"), dict) else None})
    c_bl_step = blp["producer"]["ns_per_step"]
    row["formula_with_bl_precompute_step"] = row["c_probe_ns"] * row["c_state_ns"] / (C_BL * c_bl_step ** 2)
    price_rows.append(row)
    dists.append(distribution("n83 K600 (16 fresh pts; work-identical in runs 38523707244, 38617911080, 38689817618)",
                              row["source"], [x["probes"] for x in bl_rows], seed, states600, r83, 166))
    seed += 101
    # BL online steps distribution (rho-side null, for B1 context)
    dists.append(distribution("n83 BL online steps (16 fresh pts, run 38689817618)", row["source"],
                              [x["bl_steps"] for x in bl_rows], seed))
    seed += 101

    t1, t1pre = k600_tier1(a.n83_tier1)
    P_t1 = (t1[0]["rank_ms"] + st.median(x["setup_ms"] for x in t1)) * 1e6
    row = price_row("n83 K600, Tier 1 run 38523707244 (panel B)",
                    "cryptanalysis experiments/koblitz-single-target-n83-tier1-20261014/tier1_github_38523707244",
                    r83, 166, states600, [x["probes"] for x in t1], [x["ic_ns"] for x in t1], P_t1,
                    [x["rho_ns"] for x in t1], [x["rho_steps"] for x in t1], seed,
                    "rung-3 rho (32 lanes, DP4): NOT the tuned walk", "rank stage once + median per-process setup",
                    extra={"design": "PDP4 S3 root index (wide path)", "in_scope_of_claim": "m=4 root index",
                           "states_source": "root_table_entries of the K600 producer (same base hash; read from run 38689817618)",
                           "rank_stage_probe_mean_600_relations": t1pre["rank_probes_mean"],
                           "rank_stage_probe_ratio": t1pre["rank_probes_mean"] / (r83 / (166 * states600))})
    price_rows.append(row)
    seed += 101

    ic, rT, fr = k600_reconcile(a.reconcile)
    by = {r["fields"]["panel"]: r for r in ic}
    rT_mean = {}
    for r in rT:
        rT_mean.setdefault(r["fields"]["panel"], []).append(r)
    pts = sorted(by)
    P_rc = st.median(float(r["fields"]["setup_ms"]) for r in fr) * 1e6
    row = price_row("n83 K600, reconcile run 38617911080",
                    "cryptanalysis experiments/koblitz-n83-reconcile-20261014/run_github_38617911080",
                    r83, 166, states600, [int(by[p]["fields"]["ops"]) for p in pts],
                    [float(by[p]["fields"]["online_ms"]) * 1e6 for p in pts], P_rc,
                    [mean([float(x["fields"]["online_ms"]) for x in rT_mean[p]]) * 1e6 for p in pts],
                    [mean([int(x["fields"]["ops"]) for x in rT_mean[p]]) for p in pts], seed,
                    "rT770 tuned rho, per point mean of its 2 rows, same job",
                    "median setup_ms of iB770f (B's producer, fresh in-process rank on Q0, same job)",
                    extra={"design": "PDP4 S3 root index (wide path)", "in_scope_of_claim": "m=4 root index",
                           "states_source": "root_table_entries of the K600 producer (same base hash; read from run 38689817618)"})
    price_rows.append(row)

    # prediction 3: slopes
    def fit(pts_, key):
        return slope([x for x, _ in pts_], [math.log(rw[key]) for _, rw in pts_])
    m2 = [(x, rw) for x, rw in s23_slope_pts if rw["in_scope_of_claim"] is True]
    bl83 = [rw for rw in price_rows if rw["row"].startswith("n83 K600, BL arm")][0]
    slopes = {
        "s23_six_sizes_model_column_1.93x1.21_canonical_step": fit(s23_slope_pts, "s23_model_column"),
        "s23_five_m2_sizes_model_column": fit(m2, "s23_model_column"),
        "s23_six_sizes_ic_over_bl_model_c2.1_tuned_step": fit(s23_slope_pts, "ic_over_bl_model_c2.1"),
        "s23_five_m2_sizes_ic_over_bl_model_c2.1_tuned_step": fit(m2, "ic_over_bl_model_c2.1"),
        "s23_six_sizes_formula_ratio": fit(s23_slope_pts, "formula_ratio"),
        "seven_points_s23_model_plus_n83_measured_MIXED": slope(
            [x for x, _ in s23_slope_pts] + [math.log(r83)],
            [math.log(rw["ic_over_bl_model_c2.1"]) for _, rw in s23_slope_pts] + [math.log(bl83["ic_over_bl_measured"])]),
    }

    # B2: ns/probe against table bytes
    b2 = []
    for rw in price_rows:
        b2.append({"row": rw["row"], "c_probe_ns": rw["c_probe_ns"],
                   "c_probe_lookup_only_ns": rw.get("c_probe_lookup_only_ns"),
                   "states": rw["states"], "table_bytes": rw.get("table_bytes"),
                   "peak_rss_bytes": rw.get("peak_rss_bytes"), "host": rw.get("host", "see source")})

    out = {"what": __doc__, "C_BL": C_BL, "price_rows": price_rows, "slopes_ln_ratio_on_ln_r": slopes,
           "probe_distributions": dists, "ns_per_probe_vs_table": b2}
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
