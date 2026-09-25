# Re-derive run-13's horizontal-edge equality rates from Codex's own per-chart hashes (floor-solver-results.json),
# but using OUR independently computed edge lists (c03), and compare with the run-13 REPORT / analysis-summary claims.
import json, itertools
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
d = json.loads((W / "codex_inputs/curve-comparison/run-13-full-floor-solver/floor-solver-results.json").read_text())
our = json.loads((W / "raw/c03_horizontal_graph.json").read_text())
cs = {r["curve_id"]: r for r in d["panels"]["chart_specific"]}
labs = sorted(cs)
f4 = {}
sr = d["panel_summaries"]["chart_specific"]["solver_results"]
for l, r in cs.items():
    f4[l] = sr.get(r["reduced_system_hash"], {}).get("max_f4_degree")
res = {"edges": {}, "n_edges_total": 0}
for l, v in our["ells"].items():
    E = set()
    for a, nb in v["neighbours"].items():
        if a == "E0": continue
        for b, _ in nb: E.add(tuple(sorted((a, b))))
    n = len(E); res["n_edges_total"] += n
    eq = lambda key: sum(cs[a][key] == cs[b][key] for a, b in E)
    res["edges"][l] = {"edges": n, "equal_reduced": eq("reduced_system_hash"), "equal_membership": eq("membership_mask_hash"),
                       "equal_top_rate": eq("top_system_hash") / n, "equal_f4_rate_incl_None": sum(f4[a] == f4[b] for a, b in E) / n,
                       "comparable_f4_edges": sum(f4[a] is not None and f4[b] is not None for a, b in E),
                       "equal_f4_comparable_rate": sum(f4[a] == f4[b] for a, b in E if f4[a] is not None and f4[b] is not None) / max(1, sum(f4[a] is not None and f4[b] is not None for a, b in E))}
pairs = list(itertools.combinations(labs, 2))
res["global_equal_top_rate"] = sum(cs[a]["top_system_hash"] == cs[b]["top_system_hash"] for a, b in pairs) / len(pairs)
res["global_equal_f4_rate_incl_None"] = sum(f4[a] == f4[b] for a, b in pairs) / len(pairs)
cp = [(a, b) for a, b in pairs if f4[a] is not None and f4[b] is not None]
res["global_equal_f4_comparable_rate"] = sum(f4[a] == f4[b] for a, b in cp) / len(cp)
from collections import Counter
res["f4_distribution"] = {str(k): v for k, v in Counter(f4.values()).items()}
res["unique_reduced"] = len(set(r["reduced_system_hash"] for r in cs.values()))
res["unique_top"] = len(set(r["top_system_hash"] for r in cs.values()))
res["unique_membership"] = len(set(r["membership_mask_hash"] for r in cs.values()))
res["codex_claims"] = {"edges": 1572, "equal_top_rate_range": "3.82%..6.87%", "global_top": "5.50%", "global_f4": "94.46%",
                       "unique_reduced": 262, "unique_top": 160, "unique_membership": 261}
print(json.dumps(res, indent=1))
(W / "raw" / "c16_run13_edge_rates.json").write_text(json.dumps(res, indent=1))
