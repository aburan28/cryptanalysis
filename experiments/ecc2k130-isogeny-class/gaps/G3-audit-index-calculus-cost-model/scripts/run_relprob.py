"""Grid driver for relprob.c (exact relation probabilities on toy Koblitz curves).
Writes raw/relprob.jsonl (one JSON line per run) and raw/relprob_summary.json.
Summary: for every run, the ratio of measured coverage to the Poisson prediction with
lambda = M/#E (M = number of multisets (plain) or ordered tuples), to the costmodel.py formula
p = 2^(ml)/(m! 2^n), and, for targets in G = 4E, to the ker-Tr prediction 1-exp(-2M/#E)."""
import json, math, subprocess, sys, os
G = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G3-audit-index-calculus-cost-model/"
EXE = G + "scripts/relprob"
grid = []
for (n, m, l) in [(23, 2, 10), (23, 2, 11), (23, 3, 6), (23, 3, 7), (23, 4, 5),
                  (29, 2, 14), (29, 3, 9), (31, 3, 10)]:
    for enum in ("plain", "ordered"):
        for basis in ("normal", "random", "kertr"):
            seeds = (1,) if basis == "normal" else (1, 2, 3)
            if n == 31 and basis != "normal":
                seeds = (1,)
            for s in seeds:
                grid.append((n, m, l, f"{enum}:{basis}", s))
out = open(G + "raw/relprob.jsonl", "w")
rows = []
for (n, m, l, mode, s) in grid:
    K = 200000
    r = subprocess.run([EXE, str(n), str(m), str(l), mode, str(s), str(K)], capture_output=True,
                       text=True, timeout=2400)
    if r.returncode != 0:
        print("FAIL", n, m, l, mode, s, r.stderr, flush=True)
        continue
    d = json.loads(r.stdout)
    M, E = d["sums"], d["cardE"]
    lam = M / E
    d["pred_cov_lambda_M_over_E"] = 1 - math.exp(-lam)
    d["ratio_meas_over_pred_M"] = d["x_cov_frac"] / (1 - math.exp(-lam))
    kertr = mode.endswith("kertr")
    # ker-Tr: all sums in 2E, so x-coverage of 2E is 1-exp(-2M/#E); overall = half of that
    d["pred_x_cov_kertr"] = 0.5 * (1 - math.exp(-2 * lam)) if kertr else None
    d["pred_hit_G"] = (1 - math.exp(-2 * lam)) if kertr else (1 - math.exp(-lam))
    d["ratio_hitG_over_pred"] = d["hit_G"] / d["pred_hit_G"]
    d["ratio_hitG_over_costmodel_p"] = d["hit_G"] / d["pred_costmodel_p"]
    out.write(json.dumps(d) + "\n"); out.flush()
    rows.append(d)
    print(n, m, l, mode, s, "F=%d" % d["F_size"], "xcov=%.5f predM=%.5f ratio=%.3f  hitG=%.5f predG=%.5f ratioG=%.3f  cm=%.5f  t=%.1fs" % (
        d["x_cov_frac"], d["pred_cov_lambda_M_over_E"], d["ratio_meas_over_pred_M"], d["hit_G"],
        d["pred_hit_G"], d["ratio_hitG_over_pred"], d["pred_costmodel_p"], d["seconds"]), flush=True)
# summary: ratios by mode
summ = {}
for key in sorted({(r["mode"]) for r in rows}):
    sub = [r for r in rows if r["mode"] == key]
    summ[key] = dict(
        runs=len(sub),
        x_cov_ratio_to_pred_M=[round(r["ratio_meas_over_pred_M"], 4) for r in sub],
        hitG_ratio_to_pred=[round(r["ratio_hitG_over_pred"], 4) for r in sub],
        hitG_ratio_to_costmodel_p_with_true_F=[round(r["hit_G"] / (1 - math.exp(-(r["F_size"] ** r["m"] / (math.factorial(r["m"]) if key.startswith("plain") else 1)) / r["cardE"])), 4) for r in sub],
    )
json.dump(summ, open(G + "raw/relprob_summary.json", "w"), indent=1)
print(json.dumps(summ, indent=1))
