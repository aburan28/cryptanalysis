"""Tail-exceedance check: number of (curve, subspace, k) cells with |z_matched| > 3 at
k in {8,10,12,14,16}, observed for floor / null1 / null2, against a Monte-Carlo of the exact
nested-binomial model (same cell structure: nested V_8 < ... < V_16, canonical cells have one
fewer coin).  Also the chi-square dispersion of the pooled z per k.  Pure numpy.
Run: sage -python exceed_mc.py   (reads per_curve.json, null_per_curve.json, stats.json)"""
import json, math
import numpy as np
from scipy import stats
OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
per = json.load(open(OUT + "per_curve.json"))
nul = json.load(open(OUT + "null_per_curve.json"))
KS = [8, 10, 12, 14, 16]
SUBS = ["canon", "rand1", "rand2", "rand3"]
groups = {"floor": {l: v["zscores"] for l, v in per.items() if l != "E0"},
          "null1": {l: v["zscores"] for l, v in nul.items() if l.startswith("R")},
          "null2": {l: v["zscores"] for l, v in nul.items() if l.startswith("S")}}
res = {}
for g, d in groups.items():
    cells = [(l, s, k) for l in d for s in SUBS for k in KS if abs(d[l][s]["k%d" % k]) > 3]
    res[g] = {"n_exceed": len(cells), "cells": cells,
              "n_curve_subspace_pairs_with_exceedance": len({(l, s) for l, s, k in cells}),
              "n_curves_with_exceedance": len({l for l, s, k in cells})}
rng = np.random.default_rng(99)
REPS = 4000
ncs = 262 * 4
sims, sims_pairs = [], []
for r in range(REPS):
    # coins: canonical cells (1 of 4 subspaces) have coins 2^k - 2 and nested increments; random ones 2^k - 1
    tot = np.zeros(ncs)
    cnt = 0
    pair_hit = np.zeros(ncs, dtype=bool)
    prev_coins = np.zeros(ncs)
    is_canon = np.zeros(ncs, dtype=bool)
    is_canon[::4] = True
    X = np.zeros(ncs)
    for k in range(1, 17):
        coins = np.where(is_canon, (1 << k) - 2, (1 << k) - 1).astype(float)
        inc = (coins - prev_coins).astype(np.int64)
        X = X + rng.binomial(inc, 0.5)
        prev_coins = coins
        if k in KS:
            z = (X - coins / 2) / np.sqrt(coins / 4)
            hit = np.abs(z) > 3
            cnt += int(hit.sum())
            pair_hit |= hit
    sims.append(cnt)
    sims_pairs.append(int(pair_hit.sum()))
sims = np.array(sims)
sims_pairs = np.array(sims_pairs)
for g in res:
    res[g]["mc_mean"] = float(sims.mean())
    res[g]["mc_p_ge_obs"] = float((1 + (sims >= res[g]["n_exceed"]).sum()) / (1 + REPS))
    res[g]["mc_pairs_mean"] = float(sims_pairs.mean())
    res[g]["mc_pairs_p_ge_obs"] = float((1 + (sims_pairs >= res[g]["n_curve_subspace_pairs_with_exceedance"]).sum()) / (1 + REPS))
st = json.load(open(OUT + "stats.json"))
res["pooled_dispersion_chi2_p"] = {g: {k: st["per_k"][str(k)]["pooled"][g]["chi2_sumz2_p_two_sided"] for k in KS}
                                   for g in ("floor", "null1", "null2")}
res["pooled_sd_z"] = {g: {k: st["per_k"][str(k)]["pooled"][g]["sd_z"] for k in KS} for g in ("floor", "null1", "null2")}
json.dump(res, open(OUT + "exceedance_mc.json", "w"), indent=1)
for g in ("floor", "null1", "null2"):
    x = res[g]
    print(g, "exceed", x["n_exceed"], "pairs", x["n_curve_subspace_pairs_with_exceedance"], "curves", x["n_curves_with_exceedance"],
          "| MC mean %.1f p(>=obs) %.4f | pairs MC mean %.1f p %.4f" % (x["mc_mean"], x["mc_p_ge_obs"], x["mc_pairs_mean"], x["mc_pairs_p_ge_obs"]))
print("floor cells:", res["floor"]["cells"])
print("dispersion chi2 p:", res["pooled_dispersion_chi2_p"])
print("sd:", res["pooled_sd_z"])
