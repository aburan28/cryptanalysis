"""Render the numeric tables of report.md from stats.json / exceedance_mc.json / replicate.json /
costmodel.json / structure_checks.json / toy/relprob_toy.json (no numbers typed by hand).
Run: python3 make_tables.py > tables.md"""
import json
OUT = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
st = json.load(open(OUT + "stats.json"))
ex = json.load(open(OUT + "exceedance_mc.json"))
rep = json.load(open(OUT + "replicate.json"))
cm = json.load(open(OUT + "costmodel.json"))
sc = json.load(open(OUT + "structure_checks.json"))
per = json.load(open(OUT + "per_curve.json"))
KS = [8, 10, 12, 14, 16]

print("### T1. Pooled z (4 subspaces per curve), exact per-curve model\n")
print("| k | floor mean z / sd (n=1048) | KS vs binomial p | null1 mean / sd | null2 mean / sd | KS2 floor-null1 p | KS2 floor-null2 p | KS2 A-B p |")
print("|--:|--|--:|--|--|--:|--:|--:|")
for k in KS:
    x = st["per_k"][str(k)]["pooled"]
    print("| %d | %+.3f / %.3f | %.3f | %+.3f / %.3f | %+.3f / %.3f | %.3f | %.3f | %.3f |" % (
        k, x["floor"]["mean_z"], x["floor"]["sd_z"], x["floor"]["ks_vs_binomial_p_mc"],
        x["null1"]["mean_z"], x["null1"]["sd_z"], x["null2"]["mean_z"], x["null2"]["sd_z"],
        x["ks2_floor_vs_null1"]["p_perm"], x["ks2_floor_vs_null2"]["p_perm"], x["ks2_orbitA_vs_orbitB"]["p_perm"]))
print()
print("Per-subspace floor KS-vs-binomial p-values (Monte-Carlo, 2000 draws):\n")
print("| k | canon | rand1 | rand2 | rand3 |")
print("|--:|--:|--:|--:|--:|")
for k in KS:
    x = st["per_k"][str(k)]
    print("| %d | %s |" % (k, " | ".join("%.3f" % x[s]["floor"]["ks_vs_binomial_p_mc"] for s in ("canon", "rand1", "rand2", "rand3"))))
print()
gm = st["grand_mean"]
print("Grand mean z over 5 k x 4 subspaces (SE from the exact nested covariance): " + "; ".join(
    "%s %+.4f (SE %.4f, %.2f sigma, p=%.2f)" % (g, gm[g]["grand_mean_z"], gm[g]["se"], gm[g]["z_of_mean"], gm[g]["p_two_sided"])
    for g in ("floor", "null1", "null2")) + ".\n")
print("### T2. Extreme values over the 262 x 4 floor cells\n")
print("| k | max z (cell) | P(max >= obs) | E[max z] [5%,50%,95%] | min z (cell) | P(min <= obs) | null1 max/min | null2 max/min |")
print("|--:|--|--:|--|--|--:|--|--|")
for k in KS:
    x = st["per_k"][str(k)]["pooled"]
    fe = x["floor_extremes"]
    print("| %d | %+.2f (%s, %s) | %.3f | %.2f [%.2f, %.2f, %.2f] | %+.2f (%s, %s) | %.3f | %+.2f / %+.2f | %+.2f / %+.2f |" % (
        k, fe["max_z"], fe["max_cell"][0], fe["max_cell"][1], fe["p_max_ge_obs"], fe["expected_max_z"], *fe["max_z_5_50_95"],
        fe["min_z"], fe["min_cell"][0], fe["min_cell"][1], fe["p_min_le_obs"],
        x["null1_extremes"]["max_z"], x["null1_extremes"]["min_z"], x["null2_extremes"]["max_z"], x["null2_extremes"]["min_z"]))
print()
print("Tail count |z| > 3 (5 k x 4 subspaces): floor %d, null1 %d, null2 %d; nested-binomial MC mean %.1f; MC p(>= floor) = %.4f."
      % (ex["floor"]["n_exceed"], ex["null1"]["n_exceed"], ex["null2"]["n_exceed"], ex["floor"]["mc_mean"], ex["floor"]["mc_p_ge_obs"]))
print("Replication on 12 new random subspaces (seeds 9101-9112): floor %d, null1 %d, null2 %d; MC mean %.1f; MC p(>= floor) = %.3f.\n"
      % (rep["floor"]["n_exceed"], rep["null1"]["n_exceed"], rep["null2"]["n_exceed"], rep["floor"]["mc_mean_for_262_curves"], rep["floor"]["mc_p_ge_obs"]))
print("### T3. E0 z-scores (exact model) and densities\n")
print("| k | canon | rand1 | rand2 | rand3 | canonical density d_k |")
print("|--:|--:|--:|--:|--:|--:|")
for k in KS:
    z = per["E0"]["zscores"]
    print("| %d | %s | %.6f |" % (k, " | ".join("%+.2f" % z[s]["k%d" % k] for s in ("canon", "rand1", "rand2", "rand3")), per["E0"]["density_k%d" % k]))
print()
print("### T4. Codex Run-08 'best descendant' ratios vs the same protocol simulated under the pure null (1000 replicas)\n")
print("| k | Codex best | null best: mean [5%, 50%, 95%] | fraction of null replicas with best <= Codex | Codex median | null median [5%, 95%] |")
print("|--:|--:|--|--:|--:|--|")
for k in range(8, 17):
    c = st["codex_run08_null_replica"]["per_k"][str(k)]
    med = ("%.4f" % c["codex_median"]) if "codex_median" in c else "-"
    print("| %d | %.4f | %.4f [%.4f, %.4f, %.4f] | %.3f | %s | [%.4f, %.4f] |" % (
        k, c["codex_best"], c["sim_best_mean"], *c["sim_best_5_50_95"], c["frac_sim_best_le_codex"], med,
        c["sim_median_5_50_95"][0], c["sim_median_5_50_95"][2]))
print()
print("Our own data, same attempt model (targets = ceil(1.1 b)/(4 C(b,4))), best descendant vs E0:\n")
print("| k | canonical V only: best (curve) | median | best-of-4-subspaces: best (curve) | median |")
print("|--:|--|--:|--|--:|")
for k in range(8, 17):
    r = st["attempt_ratio_m4_codex_model"][str(k)]
    print("| %d | %.4f (%s) | %.4f | %.4f (%s) | %.4f |" % (k, r["canon_best"], r["canon_best_curve"], r["canon_median"],
                                                           r["bestof4_best"], r["bestof4_best_curve"], r["bestof4_median"]))
print()
print("### T5. Index calculus vs rho, cost model (log2 group operations; min over l)\n")
print("rho: " + "; ".join("%s 2^%.2f" % (k, v) for k, v in cm["rho_log2"].items()) + "\n")
print("| m | free PDP (oracle) | free PDP + GGMP-hyp (E0) | table/MITM-amortised | + GGMP-hyp | per-target MITM | + GGMP-hyp |")
print("|--:|--|--|--|--|--|--|")
for m in range(2, 8):
    t = cm["table"]
    f = lambda key: "2^%.1f (l=%d)" % (t[key]["log2_total"], t[key]["best_l"])
    print("| %d | %s | %s | %s | %s | %s | %s |" % (m, f("free|plain|m%d" % m), f("free|GGMP-hyp(E0)|m%d" % m),
                                                 f("table|plain|m%d" % m), f("table|GGMP-hyp(E0)|m%d" % m),
                                                 f("mitm|plain|m%d" % m), f("mitm|GGMP-hyp(E0)|m%d" % m)))
print()
print("Density effect at attack sizes (best z bought by screening S subspaces/curves, z ~ sqrt(2 ln S)):\n")
print("| l | S | z_best | log2 gain in relation probability, m=4 | m=6 |")
print("|--:|--:|--:|--:|--:|")
for key, v in cm["density_effect"].items():
    l, S = key.split("_")
    print("| %s | %s | %.2f | %.4f | %.4f |" % (l[1:], S[1:], v["z_best"], v["log2_relprob_gain_m4"], v["log2_relprob_gain_m6"]))
print()
try:
    toy = json.load(open(OUT + "toy/relprob_toy.json"))
    print("### T6. Toy (n = 19, conductor 457): exact decomposition probability / random-symmetric-set baseline\n")
    print("| l, m | E0 | floor (100) mean +- sd | null (100) mean +- sd | null Tr(b)=1 (100) mean +- sd | KS2 floor-null p | KS2 floor-matched p |")
    print("|--|--:|--|--|--|--:|--:|")
    for key, e in toy["summary"].items():
        print("| %s | %.4f | %.4f +- %.4f | %.4f +- %.4f | %.4f +- %.4f | %.3f | %.3f |" % (
            key, e["E0"]["mean_ratio_to_randset"], e["floor"]["mean_ratio_to_randset"], e["floor"]["sd_ratio"],
            e["null"]["mean_ratio_to_randset"], e["null"]["sd_ratio"], e["null_matched"]["mean_ratio_to_randset"],
            e["null_matched"]["sd_ratio"], e["ks2_floor_vs_null_ratio"]["p"], e["ks2_floor_vs_null_matched_ratio"]["p"]))
    print()
    print("Mean decomposition probability y_m (floor) vs heuristic |F|^m/(m! #E): " + "; ".join(
        "%s %.4g" % (k, e["floor"]["mean_y"]) for k, e in toy["summary"].items()))
    print()
    print("tau-union demo: " + json.dumps(toy["tau_union_demo"]))
except FileNotFoundError:
    print("(toy results not available)")
