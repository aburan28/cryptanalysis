# Compare Codex per-curve relation-coverage data with our recomputation (c10):
#  run-01 comparison.csv (profiles polynomial k=4, polynomial k=5) and run-03 all-k6-*.jsonl (k=6 census),
#  and the aggregate claims in run-01 REPORT / run-03 REPORT / EXPLOITABILITY.md.
import json, csv, glob
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
CI = W / "codex_inputs/curve-comparison"
def load_jsonl(pattern):
    d = {}
    for f in sorted(glob.glob(str(W / "raw" / pattern))):
        for line in open(f):
            if line.strip():
                r = json.loads(line); d[r.pop("label")] = r
    return d
ours45 = load_jsonl("c10c_k4_5_shard*of6.jsonl")
assert len(ours45) == 263, len(ours45)
ours6 = load_jsonl("c10c_k6_shard*of8.jsonl")
res_k6_rows_available = len(ours6)
ours6_partial = ours6
ours6 = ours6 if len(ours6) >= 1 else None
FIELDS = ["factor_base_x_count", "factor_base_signed_point_count", "prime_subgroup_distinct_targets",
          "eligible_signed_triples", "all_signed_triples", "infinity_triples"]
rows = list(csv.DictReader(open(CI / "run-01/comparison.csv")))
oursr = load_jsonl("c10d_random_k4_shard*of3.jsonl")
res_random_available = len(oursr)
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
gtc = {c["label"]: c for c in GT["curves"]}
summ = json.loads((CI / "run-01/summary.json").read_text())
jb_ok = sum(1 for r in summ if r["j"] == gtc[r["curve_id"]]["j_int"] and r["b"] == gtc[r["curve_id"]]["b_int"])
res = {"run01_rows": len(rows), "per_curve": {}, "mismatches": [],
       "run01_summary_rows": len(summ), "run01_summary_rows_j_b_equal_gt": jb_ok,
       "run01_summary_curves": len(set(r["curve_id"] for r in summ))}
for r in summ:
    res["per_curve"].setdefault(r["curve_id"], {})["run01_summary_j_b_equal_gt"] = res["per_curve"].get(r["curve_id"], {}).get("run01_summary_j_b_equal_gt", True) and (r["j"] == gtc[r["curve_id"]]["j_int"] and r["b"] == gtc[r["curve_id"]]["b_int"])
for r in rows:
    lab, k = r["curve_id"], r["k"]
    if r["profile"] == "random":
        if lab not in oursr: continue
        o = oursr[lab]["4r"]; k = "4random"
    else:
        o = ours45[lab][k]
    ok = all(int(r[f]) == o[f] for f in FIELDS)
    res["per_curve"].setdefault(lab, {})[f"run01_{'random_k4' if k == '4random' else 'poly_k' + k}"] = ok
    if not ok:
        res["mismatches"].append({"curve": lab, "k": k, "codex": {f: r[f] for f in FIELDS}, "ours": {f: o[f] for f in FIELDS}})
# aggregate claims
def agg(k):
    E0 = ours45["E0"][k]
    fl = {l: v[k] for l, v in ours45.items() if l != "E0"}
    t = [v[k]["prime_subgroup_distinct_targets"] for v in ours45.values()]
    same = [v["prime_subgroup_distinct_targets"] for v in fl.values() if v["factor_base_x_count"] == E0["factor_base_x_count"]]
    return {"E0_targets": E0["prime_subgroup_distinct_targets"], "all_curves_target_range": [min(t), max(t)],
            "descendants_with_higher_coverage_than_E0": sum(1 for v in fl.values() if v["prime_subgroup_distinct_targets"] > E0["prime_subgroup_distinct_targets"]),
            "size_matched_descendants": len(same), "size_matched_target_range": [min(same), max(same)] if same else None,
            "best_size_matched": max(((v["prime_subgroup_distinct_targets"], l) for l, v in fl.items() if v["factor_base_x_count"] == E0["factor_base_x_count"]), default=None)}
res["aggregate_k4"] = agg("4"); res["aggregate_k5"] = agg("5")
if len(oursr) == 263:
    save = ours45
    ours45 = {l: {"4r": v["4r"]} for l, v in oursr.items()}
    res["aggregate_k4_random"] = agg("4r")
    ours45 = save
res["random_k4_curves_recomputed"] = len(oursr)
res["codex_claims"] = {"k4": {"E0": 80, "range": [0, 584], "higher": "155/262", "size_matched_range": [56, 80], "best_same_size": "A010 80"},
                       "k5": {"E0": 660, "range": [168, 3632], "higher": "215/262", "size_matched_range": [680, 832], "best_same_size": "B067 832"},
                       "k4_random": {"E0": 184, "range": [0, 440], "higher": "39/262", "size_matched_range": [152, 192], "best_same_size": "B023 192"}}
# EXPLOITABILITY k=5 specifics
k5 = {l: ours45[l]["5"] for l in ["E0", "B067", "A090", "B021", "B081"]}
res["exploitability_k5"] = {l: {"x": v["factor_base_x_count"], "targets": v["prime_subgroup_distinct_targets"],
                                "eligible": v["eligible_signed_triples"], "tags": v["tag_split_n0_n2_nodd"],
                                "ratio_vs_E0": v["prime_subgroup_distinct_targets"] / 660} for l, v in k5.items()}
res["exploitability_k4"] = {l: {"x": ours45[l]["4"]["factor_base_x_count"], "targets": ours45[l]["4"]["prime_subgroup_distinct_targets"],
                                "ratio_vs_E0": ours45[l]["4"]["prime_subgroup_distinct_targets"] / 80} for l in ["E0", "A010", "B021", "A090", "B081"]}
if ours6:
    recs = []
    for f in sorted(glob.glob(str(CI / "run-03-scaling/all-k6-*.jsonl"))):
        for line in open(f):
            line = line.strip()
            if line: recs.append(json.loads(line))
    res["run03_k6_rows"] = len(recs)
    res["run03_k6_keys"] = sorted(recs[0].keys()) if recs else []
    mm = 0; cmp = 0
    for r in recs:
        lab = r.get("curve_id") or r.get("curve")
        if lab not in ours6: continue
        o = ours6[lab]["6"]
        pairs = [(a, b) for a, b in [("factor_base_x_count", "factor_base_x_count"),
                                     ("distinct_reachable_targets", "prime_subgroup_distinct_targets"),
                                     ("eligible_signed_triples", "eligible_signed_triples"),
                                     ("infinity_triples", "infinity_triples")] if a in r]
        ok = all(int(r[a]) == o[b] for a, b in pairs) and [r["tag_zero_x_count"], r["tag_two_x_count"], r["tag_odd_x_count"]] == o["tag_split_n0_n2_nodd"] and int(r["collision_excess"]) == o["eligible_signed_triples"] - o["infinity_triples"] - o["prime_subgroup_distinct_targets"]
        cmp += 1; mm += (not ok)
        res["per_curve"].setdefault(lab, {})["run03_k6"] = ok
        if not ok: res["mismatches"].append({"curve": lab, "k": 6, "codex": {a: r[a] for a, _ in pairs}, "ours": {b: o[b] for _, b in pairs}})
    res["run03_k6_compared"] = cmp; res["run03_k6_mismatch"] = mm; res["k6_curves_recomputed"] = len(ours6)
    fl6 = {l: v["6"] for l, v in ours6.items()}
    E06 = fl6["E0"]
    res["aggregate_k6"] = {"x_range": [min(v["factor_base_x_count"] for v in fl6.values()), max(v["factor_base_x_count"] for v in fl6.values())],
                           "target_range": [min(v["prime_subgroup_distinct_targets"] for v in fl6.values()), max(v["prime_subgroup_distinct_targets"] for v in fl6.values())],
                           "infinity_triples_total": sum(v["infinity_triples"] for v in fl6.values()),
                           "collision_rows": sorted(l for l, v in fl6.items() if v["eligible_signed_triples"] - v["infinity_triples"] != v["prime_subgroup_distinct_targets"]),
                           "E0": E06,
                           "best_size_matched": max(((v["prime_subgroup_distinct_targets"], l) for l, v in fl6.items() if l != "E0" and v["factor_base_x_count"] == E06["factor_base_x_count"]), default=None)}
    res["codex_claims"]["k6"] = {"x_range": [22, 42], "target_range": [2992, 23008], "E0": "eligible 10868 distinct 10840 excess 28", "only_collision_row": "E0", "best_same_size": "A092 11080"}
from math import comb
def formula(n0, n2, no): return 8*(comb(n0, 3) + n0*comb(n2, 2)) + 4*(n0 + n2)*comb(no, 2)
fbad = 0; fn = 0
for src in [ours45, oursr] + ([ours6] if ours6 else []):
    for lab, d in src.items():
        for k, o in d.items():
            fn += 1; fbad += (formula(*o["tag_split_n0_n2_nodd"]) != o["eligible_signed_triples"])
res["run02_eligible_formula_rows_checked"] = fn; res["run02_eligible_formula_failures"] = fbad
print(json.dumps({k: v for k, v in res.items() if k != "per_curve"}, indent=1, default=str))
(W / "raw" / "c13_compare_run01_run03.json").write_text(json.dumps(res, indent=1, default=str))
