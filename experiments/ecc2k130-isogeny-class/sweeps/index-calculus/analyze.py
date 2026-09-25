"""Statistics on the rational-x counts: floor curves vs two nulls vs the exact binomial model,
extreme values (winner's curse), a replica of Codex Run-08 under the null, per-curve JSON.

Inputs : raw_counts.json (density.py: class + null1 R000..R262, Tr(b) uniform)
         raw_counts_null2.json (density_null2.py: null2 S000..S262, Tr(b) = 1 like the class)
Outputs: stats.json, per_curve.json, null_per_curve.json, analyze.out (console)
Run    : export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; sage -python analyze.py

Exact per-curve model.  C = #{x in V_k : x = 0 or Tr(x + b/x^2) = 0}.  x = 0 always counts.
If 1 in V_k, x = 1 counts iff Tr(1 + b) = 0 iff Tr(b) = 1 (n = 131 odd): deterministic given
Tr(b).  Every other x != 0 gives a fair coin over uniform b, and distinct x give distinct
linear forms b -> Tr(b/x^2), independent of b -> Tr(b), so the coins are pairwise independent
even conditioned on Tr(b):  X = C - det has mean coins/2 and variance coins/4 exactly, with
det = 1 + [1 in V_k] Tr(b), coins = 2^k - 1 - [1 in V_k].
  z_matched = (X - coins/2) / sqrt(coins/4)       (used for all tests)
  z_uniform = (C - 1 - (2^k-1)/2) / sqrt((2^k-1)/4)   (reference Binomial(2^k-1,1/2), ignores Tr(b))
All class curves have Tr(b) = 1 (#E = 4N, no point of order 8), so on the canonical subspace
(1 in V) z_uniform is shifted by +1/sqrt(2^k-1) for every class curve.
"""
import json, math, sys
import numpy as np
from scipy import stats

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k

OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
raw = json.load(open(OUT + "raw_counts.json"))
raw2 = json.load(open(OUT + "raw_counts_null2.json"))
C = dict(raw["counts"])
C.update(raw2["counts"])
CLASS = raw["meta"]["class_labels"]
FLOOR = [l for l in CLASS if l != "E0"]
NULL1 = raw["meta"]["null_labels"]
NULL2 = raw2["meta"]["labels"]
SUBS = raw["meta"]["subspaces"]
KS_MAIN = [8, 10, 12, 14, 16]
KALL = list(range(8, 17))
TM = int(raw["log"]["trace_mask_int"])
rng = np.random.default_rng(20260923)
NSIM = 2000


def par(v):
    return bin(v).count("1") & 1


TRB = {l: par(int(ecc2k.RECORDS[l]["b_int"]) & TM) for l in CLASS}
TRB.update({l: par(int(r["b_int"]) & TM) for l, r in raw["null_curves"].items()})
TRB.update({l: par(int(r["b_int"]) & TM) for l, r in raw2["null_curves"].items()})
assert all(TRB[l] == 1 for l in CLASS) and all(TRB[l] == 1 for l in NULL2)


def gf2_rank(vs):
    rows, rank = list(vs), 0
    for bit in range(131):
        piv = next((i for i in range(rank, len(rows)) if (rows[i] >> bit) & 1), None)
        if piv is None:
            continue
        rows[rank], rows[piv] = rows[piv], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] >> bit) & 1:
                rows[i] ^= rows[rank]
        rank += 1
    return rank


BASES = {s: [int(v) for v in raw["log"]["subspace_bases"][s]] for s in SUBS}
ONE_IN = {s: {k: gf2_rank(BASES[s][:k] + [1]) == gf2_rank(BASES[s][:k]) for k in range(1, 17)} for s in SUBS}


def model(l, s, k):
    one = ONE_IN[s][k]
    det = 1 + (TRB[l] if one else 0)
    coins = (1 << k) - 1 - (1 if one else 0)
    return det, coins


def zm(l, s, k):
    det, coins = model(l, s, k)
    return ((C[l][s][str(k)] - det) - coins / 2) / math.sqrt(coins / 4)


def zu(l, s, k):
    n = (1 << k) - 1
    return ((C[l][s][str(k)] - 1) - n / 2) / math.sqrt(n / 4)


def ks_phi(z):
    z = np.sort(np.asarray(z))
    F = stats.norm.cdf(z)
    i = np.arange(1, len(z) + 1)
    return float(max((i / len(z) - F).max(), (F - (i - 1) / len(z)).max()))


def sim_z(cells):
    coins = np.asarray(cells)
    X = rng.binomial(coins, 0.5)
    return (X - coins / 2) / np.sqrt(coins / 4)


def ks_mc(z, cells):
    """KS distance to Phi; p-value by simulating the same cells from the exact binomials."""
    d = ks_phi(z)
    ref = np.array([ks_phi(sim_z(cells)) for _ in range(NSIM)])
    return d, float((1 + (ref >= d - 1e-12).sum()) / (1 + NSIM))


def perm_ks2(a, b, nperm=2000):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d0 = stats.ks_2samp(a, b).statistic
    allv = np.concatenate([a, b])
    cnt = 0
    for _ in range(nperm):
        rng.shuffle(allv)
        if stats.ks_2samp(allv[: len(a)], allv[len(a):]).statistic >= d0 - 1e-12:
            cnt += 1
    return float(d0), float((cnt + 1) / (nperm + 1))


def p_max_ge(zobs, cells):
    logp = 0.0
    for coins in cells:
        c = math.ceil(coins / 2 + zobs * math.sqrt(coins / 4) - 1e-9)
        logp += math.log(max(1e-300, stats.binom.cdf(c - 1, coins, 0.5)))
    return 1 - math.exp(logp)


def p_min_le(zobs, cells):
    logp = 0.0
    for coins in cells:
        c = math.floor(coins / 2 + zobs * math.sqrt(coins / 4) + 1e-9)
        logp += math.log(max(1e-300, 1 - stats.binom.cdf(c, coins, 0.5)))
    return 1 - math.exp(logp)


def max_z_quantiles(cells, reps=1000):
    mx = np.array([sim_z(cells).max() for _ in range(reps)])
    return float(mx.mean()), [float(np.quantile(mx, a)) for a in (.05, .5, .95)]


GROUPS = {"floor": FLOOR, "null1": NULL1, "null2": NULL2}
report = {"model": __doc__, "one_in_subspace_k": {s: [k for k in range(1, 17) if ONE_IN[s][k]] for s in SUBS},
          "Tr_b": {"class": 1, "null1_counts": {str(v): sum(1 for l in NULL1 if TRB[l] == v) for v in (0, 1)},
                   "null2": 1},
          "per_k": {}}
for k in KS_MAIN:
    rk = {}
    for s in SUBS + ["pooled"]:
        subs = SUBS if s == "pooled" else [s]
        ent = {}
        z = {g: [zm(l, ss, k) for l in L for ss in subs] for g, L in GROUPS.items()}
        zun = {g: [zu(l, ss, k) for l in L for ss in subs] for g, L in GROUPS.items()}
        cells = {g: [model(l, ss, k)[1] for l in L for ss in subs] for g, L in GROUPS.items()}
        for g in GROUPS:
            d, p = ks_mc(z[g], cells[g])
            s2 = float(np.sum(np.square(z[g])))
            ent[g] = {"n": len(z[g]), "mean_z": float(np.mean(z[g])), "sd_z": float(np.std(z[g], ddof=1)),
                      "mean_z_uniform_ref": float(np.mean(zun[g])),
                      "ks_vs_binomial_D": d, "ks_vs_binomial_p_mc": p,
                      "chi2_sumz2_p_two_sided": float(2 * min(stats.chi2.cdf(s2, len(z[g])), stats.chi2.sf(s2, len(z[g])))),
                      "mean_z_p_two_sided": float(2 * stats.norm.sf(abs(np.mean(z[g])) * math.sqrt(len(z[g]))))}
        for g in ("null1", "null2"):
            d, p = perm_ks2(z["floor"], z[g], 1000 if s == "pooled" else 2000)
            ent["ks2_floor_vs_" + g] = {"D": d, "p_perm": p}
        d, p = perm_ks2([zm(l, ss, k) for l in FLOOR if l[0] == "A" for ss in subs],
                        [zm(l, ss, k) for l in FLOOR if l[0] == "B" for ss in subs], 1000)
        ent["ks2_orbitA_vs_orbitB"] = {"D": d, "p_perm": p}
        zf = np.array(z["floor"])
        lab = [(l, ss) for l in FLOOR for ss in subs]
        imax, imin = int(zf.argmax()), int(zf.argmin())
        emax, qmax = max_z_quantiles(cells["floor"])
        ent["floor_extremes"] = {
            "max_z": float(zf[imax]), "max_cell": lab[imax],
            "max_density": C[lab[imax][0]][lab[imax][1]][str(k)] / 2 ** k,
            "p_max_ge_obs": p_max_ge(float(zf[imax]), cells["floor"]),
            "expected_max_z": emax, "max_z_5_50_95": qmax,
            "min_z": float(zf[imin]), "min_cell": lab[imin],
            "min_density": C[lab[imin][0]][lab[imin][1]][str(k)] / 2 ** k,
            "p_min_le_obs": p_min_le(float(zf[imin]), cells["floor"])}
        for g in ("null1", "null2"):
            zz = np.array(z[g])
            ent[g + "_extremes"] = {"max_z": float(zz.max()), "p_max_ge_obs": p_max_ge(float(zz.max()), cells[g]),
                                    "min_z": float(zz.min()), "p_min_le_obs": p_min_le(float(zz.min()), cells[g])}
        e0z = [zm("E0", ss, k) for ss in subs]
        ent["E0"] = {"counts": [C["E0"][ss][str(k)] for ss in subs], "z": e0z,
                     "z_uniform_ref": [zu("E0", ss, k) for ss in subs],
                     "fraction_of_floor_cells_below": [float((zf < v).mean()) for v in e0z]}
        rk[s] = ent
    report["per_k"][str(k)] = rk

# grand mean over k in KS_MAIN x 4 subspaces; nested V_k => Cov(z_k, z_k') = sqrt(coins_k/coins_k'), k <= k'
gm = {}
for g, L in GROUPS.items():
    vals = [zm(l, s, k) for l in L for s in SUBS for k in KS_MAIN]
    var_cell = 0.0
    for s in SUBS:
        cs = [model(L[0], s, k)[1] for k in KS_MAIN]
        var_cell += sum(math.sqrt(min(a, b) / max(a, b)) for a in cs for b in cs)
    var_cell /= len(SUBS)
    se = math.sqrt(var_cell * len(L) * len(SUBS)) / len(vals)
    m = float(np.mean(vals))
    valsu = [zu(l, s, k) for l in L for s in SUBS for k in KS_MAIN]
    gm[g] = {"grand_mean_z": m, "se": se, "z_of_mean": m / se, "p_two_sided": float(2 * stats.norm.sf(abs(m / se))),
             "grand_mean_z_uniform_ref": float(np.mean(valsu)), "z_of_mean_uniform_ref": float(np.mean(valsu)) / se}
report["grand_mean"] = gm


# ---- attempt ratio (Codex Run-08 model) -----------------------------------------------------
# Codex screen_subspaces.py: b = #nonzero liftable x = C - 1;
# log2 targets = log2 ceil(1.10 b) + log2(N-1) - log2(4 choose(b,4)); N cancels in ratios.
def targets(c):
    b = c - 1
    return math.ceil(1.10 * b) / (4 * math.comb(b, 4))


ratios = {}
for k in KALL:
    e0c = C["E0"]["canon"][str(k)]
    r_canon = np.array([targets(C[l]["canon"][str(k)]) / targets(e0c) for l in FLOOR])
    e0best = max(C["E0"][s][str(k)] for s in SUBS)
    r_best = np.array([targets(max(C[l][s][str(k)] for s in SUBS)) / targets(e0best) for l in FLOOR])
    ratios[str(k)] = {
        "canon_best": float(r_canon.min()), "canon_best_curve": FLOOR[int(r_canon.argmin())],
        "canon_median": float(np.median(r_canon)),
        "canon_5_95": [float(np.quantile(r_canon, .05)), float(np.quantile(r_canon, .95))],
        "bestof4_best": float(r_best.min()), "bestof4_best_curve": FLOOR[int(r_best.argmin())],
        "bestof4_median": float(np.median(r_best)),
        "bestof4_5_95": [float(np.quantile(r_best, .05)), float(np.quantile(r_best, .95))]}
report["attempt_ratio_m4_codex_model"] = ratios

# ---- Monte-Carlo replica of the Codex Run-08 protocol under the pure null ------------------
CODEX_BEST = {8: 0.7075, 9: 0.8088, 10: 0.7429, 11: 0.7891, 12: 0.8874, 13: 0.9043, 14: 0.9447,
              15: 0.9716, 16: 0.9766}
CODEX_MEDIAN = {8: 0.9574, 10: 0.8980, 12: 0.9842, 14: 1.0050, 16: 1.0118}
CODEX_Q = {8: (0.7983, 1.1366), 10: (0.8127, 0.9941), 12: (0.9228, 1.0646), 14: (0.9677, 1.0491),
           16: (0.9896, 1.0320)}
REPS = 1000
NC, NS = 263, 64
LT = np.array([math.log(targets(c)) if c >= 6 else np.inf for c in range((1 << 16) + 2)])
sim = {key: {k: [] for k in KALL} for key in ("best", "med", "q05", "q95")}
for rep in range(REPS):
    x = 1 + rng.binomial(255, 0.5, size=(NC, NS))
    cnt = {8: x}
    for k in range(9, 17):
        x = x + rng.binomial(1 << (k - 1), 0.5, size=(NC, NS))
        cnt[k] = x
    sel = np.argmin(LT[cnt[8]] + LT[cnt[9]] + LT[cnt[10]], axis=1)
    for k in KALL:
        ck = cnt[k][np.arange(NC), sel]
        r = np.exp(LT[ck[1:]] - LT[ck[0]])
        sim["best"][k].append(r.min())
        sim["med"][k].append(np.median(r))
        sim["q05"][k].append(np.quantile(r, .05))
        sim["q95"][k].append(np.quantile(r, .95))
codex_cmp = {}
for k in KALL:
    b = np.array(sim["best"][k])
    ent = {"codex_best": CODEX_BEST[k], "sim_best_mean": float(b.mean()),
           "sim_best_5_50_95": [float(np.quantile(b, a)) for a in (.05, .5, .95)],
           "frac_sim_best_le_codex": float((b <= CODEX_BEST[k]).mean()),
           "sim_median_5_50_95": [float(np.quantile(sim["med"][k], a)) for a in (.05, .5, .95)],
           "sim_q05_mean": float(np.mean(sim["q05"][k])), "sim_q95_mean": float(np.mean(sim["q95"][k]))}
    if k in CODEX_MEDIAN:
        ent["codex_median"] = CODEX_MEDIAN[k]
        ent["codex_5_95"] = CODEX_Q[k]
        ent["frac_sim_median_le_codex"] = float((np.array(sim["med"][k]) <= CODEX_MEDIAN[k]).mean())
    codex_cmp[str(k)] = ent
report["codex_run08_null_replica"] = {
    "reps": REPS, "curves": NC, "candidates_per_curve": NS, "per_k": codex_cmp,
    "codex_numbers_source": "run-08-descendant-subspaces/REPORT.md (best per k; median and 5-95% table)",
    "model": "per curve and candidate: C_8 = 1+Bin(255,1/2), C_{k+1} = C_k + Bin(2^k,1/2) (nested); "
             "targets(C) = ceil(1.1(C-1))/(4 choose(C-1,4)) as in Codex screen_subspaces.py; each curve keeps "
             "the candidate minimising sum_{k=8,9,10} log targets (Codex's ANF tie-breaks ignored); "
             "ratio = targets(descendant)/targets(E0) with E0 optimised the same way"}

# ---- per-curve JSON --------------------------------------------------------------------------
per = {}
for l in CLASS:
    r = {"orbit": "crater" if l == "E0" else l[0], "Tr_b": TRB[l]}
    for k in KS_MAIN:
        r["density_k%d" % k] = C[l]["canon"][str(k)] / 2 ** k
    r["zscores"] = {s: {"k%d" % k: round(zm(l, s, k), 4) for k in KS_MAIN} for s in SUBS}
    r["zscores_uniform_b_reference"] = {s: {"k%d" % k: round(zu(l, s, k), 4) for k in KS_MAIN} for s in SUBS}
    r["density_random_subspaces"] = {s: {"k%d" % k: C[l][s][str(k)] / 2 ** k for k in KS_MAIN}
                                     for s in SUBS if s != "canon"}
    r["count_incl_x0"] = {s: {"k%d" % k: C[l][s][str(k)] for k in KALL} for s in SUBS}
    r["relprob_dev_bits_m4"] = {s: {"k%d" % k: round(4 * math.log2((2 * C[l][s][str(k)] - 1) / 2 ** k), 5)
                                    for k in KS_MAIN} for s in SUBS}
    r["max_abs_z"] = round(max(abs(zm(l, s, k)) for s in SUBS for k in KS_MAIN), 4)
    per[l] = r
json.dump(per, open(OUT + "per_curve.json", "w"), indent=1)
json.dump({l: {"Tr_b": TRB[l], "zscores": {s: {"k%d" % k: round(zm(l, s, k), 4) for k in KS_MAIN} for s in SUBS},
               "density": {s: {"k%d" % k: C[l][s][str(k)] / 2 ** k for k in KS_MAIN} for s in SUBS}}
           for l in NULL1 + NULL2}, open(OUT + "null_per_curve.json", "w"), indent=1)
json.dump(report, open(OUT + "stats.json", "w"), indent=1)

# ---- console ----------------------------------------------------------------------------------
print("1 in V_k:", report["one_in_subspace_k"], "Tr(b):", report["Tr_b"])
for k in KS_MAIN:
    print("k=%2d" % k)
    for s in SUBS + ["pooled"]:
        x = report["per_k"][str(k)][s]
        print("  %-6s floor %+.3f/%.3f KSp=%.3f | null1 %+.3f/%.3f KSp=%.3f | null2 %+.3f/%.3f KSp=%.3f"
              " | KS2 f-n1 %.3f f-n2 %.3f A-B %.3f | E0 z %s"
              % (s, x["floor"]["mean_z"], x["floor"]["sd_z"], x["floor"]["ks_vs_binomial_p_mc"],
                 x["null1"]["mean_z"], x["null1"]["sd_z"], x["null1"]["ks_vs_binomial_p_mc"],
                 x["null2"]["mean_z"], x["null2"]["sd_z"], x["null2"]["ks_vs_binomial_p_mc"],
                 x["ks2_floor_vs_null1"]["p_perm"], x["ks2_floor_vs_null2"]["p_perm"], x["ks2_orbitA_vs_orbitB"]["p_perm"],
                 ["%+.2f" % v for v in x["E0"]["z"]]))
    x = report["per_k"][str(k)]["pooled"]
    fe = x["floor_extremes"]
    print("  floor extremes: max z %+.2f %s (P>=%.3f; E[max]=%.2f, 5/50/95%% %s) min z %+.2f %s (P<=%.3f)"
          % (fe["max_z"], fe["max_cell"], fe["p_max_ge_obs"], fe["expected_max_z"],
             ["%.2f" % v for v in fe["max_z_5_50_95"]], fe["min_z"], fe["min_cell"], fe["p_min_le_obs"]))
    for g in ("null1", "null2"):
        e = x[g + "_extremes"]
        print("  %s extremes: max %+.2f (P>=%.3f) min %+.2f (P<=%.3f)" % (g, e["max_z"], e["p_max_ge_obs"],
                                                                         e["min_z"], e["p_min_le_obs"]))
print("grand mean z:", json.dumps(gm))
print("attempt ratios (Codex m=4 model):")
for k in KALL:
    print(" ", k, ratios[str(k)])
print("Codex Run-08 replica under the null:")
for k in KALL:
    print(" ", k, json.dumps(codex_cmp[str(k)]))
