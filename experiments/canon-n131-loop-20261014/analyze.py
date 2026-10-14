#!/usr/bin/env python3
"""Apply protocol.json's frozen decision rule to a loop_bench rows file.

usage: python3 analyze.py <rows.jsonl> <out.json> [isolated_ir.json]

For each workload and arm, rho_r = t(arm, r) / t(lift_scan, r), paired by
round.  Reports the geometric mean, a percentile bootstrap over rounds
(20000 resamples, random.Random(20261014)) at the Bonferroni level
1 - 0.05/16 and at 95%, and the verdict the protocol's rule assigns.
Controls (protocol v2): lift_scan_aa (A/A, negative) and lift_scan_2pass
(positive: two lift_scan passes in one interval, a known 2x effect that must be
resolved with adjusted lower bound > 1.5).  null is the descriptive loop floor.  A smoke run
(meta.smoke true) is analysed the same way and labelled SMOKE: its numbers
test this script, nothing else.
"""
import json
import math
import random
import sys

PRIMARY = ["exhaustive", "gap_scan", "refine_bf", "exhaustive_bf"]
REF = "lift_scan"
M = 16
ALPHA = 0.05
B = 20000


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def boot(logs, level, rng):
    n = len(logs)
    means = []
    for _ in range(B):
        s = 0.0
        for _ in range(n):
            s += logs[rng.randrange(n)]
        means.append(s / n)
    a = (1 - level) / 2
    return math.exp(pct(means, a)), math.exp(pct(means, 1 - a))


def kendall(a, b):
    """Kendall tau-a between two orderings of the same items."""
    pa = {x: i for i, x in enumerate(a)}
    pb = {x: i for i, x in enumerate(b)}
    items = list(a)
    c = d = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s = (pa[items[i]] - pa[items[j]]) * (pb[items[i]] - pb[items[j]])
            c += s > 0
            d += s < 0
    return (c - d) / (len(items) * (len(items) - 1) / 2)


def main():
    rows = [json.loads(l) for l in open(sys.argv[1])]
    meta = next(r for r in rows if r["type"] == "meta")
    passes = [r for r in rows if r["type"] == "pass"]
    iso = None
    if len(sys.argv) > 3:
        iso = json.load(open(sys.argv[3]))
    adj = 1 - ALPHA / M
    rng = random.Random(20261014)
    t = {}
    bad = {}
    for p in passes:
        t[(p["workload"], p["arm"], p["round"])] = p["wall_ns"] / p["keys"]
        if not p["correct"]:
            bad.setdefault((p["workload"], p["arm"]), 0)
            bad[(p["workload"], p["arm"])] += 1
    out = {"smoke": meta["smoke"], "label": "SMOKE: script test only, no timing statement" if meta["smoke"]
           else "Tier 1 instance-scoped (see receipt)", "meta": meta, "bonferroni_m": M,
           "adjusted_level": adj, "workloads": {}}
    rounds = sorted({p["round"] for p in passes})
    for w in meta["workloads"]:
        W = {"arms": {}, "contrasts": {}}
        for arm in meta["arms"]:
            xs = [t[(w, arm, r)] for r in rounds if (w, arm, r) in t]
            cpu = [p["thread_cpu_ns"] / p["keys"] for p in passes if p["workload"] == w and p["arm"] == arm]
            tsc = [p["tsc"] / p["keys"] for p in passes if p["workload"] == w and p["arm"] == arm]
            W["arms"][arm] = {"n": len(xs), "median_ns_per_key": pct(xs, 0.5), "min": min(xs),
                              "max": max(xs), "q25": pct(xs, 0.25), "q75": pct(xs, 0.75),
                              "median_thread_cpu_ns_per_key": pct(cpu, 0.5),
                              "median_tsc_per_key": pct(tsc, 0.5),
                              "incorrect_rows": bad.get((w, arm), 0)}
        for arm in PRIMARY + ["lift_scan_aa", "lift_scan_2pass", "null"]:
            logs = [math.log(t[(w, arm, r)] / t[(w, REF, r)]) for r in rounds
                    if (w, arm, r) in t and (w, REF, r) in t]
            gm = math.exp(sum(logs) / len(logs))
            lo, hi = boot(logs, adj, rng)
            lo95, hi95 = boot(logs, 0.95, rng)
            sd = (sum((x - sum(logs) / len(logs)) ** 2 for x in logs) / max(1, len(logs) - 1)) ** 0.5
            marg = [t[(w, arm, r)] - t[(w, "null", r)] for r in rounds]
            W["contrasts"][arm] = {"ratio_vs_lift_scan_geomean": gm, "ci_adjusted": [lo, hi],
                                   "ci95": [lo95, hi95], "sd_log_ratio": sd, "pairs": len(logs),
                                   "marginal_ns_per_key_vs_null_median": pct(marg, 0.5)}
        aa = W["contrasts"]["lift_scan_aa"]
        aa_excl = not (aa["ci_adjusted"][0] <= 1 <= aa["ci_adjusted"][1])
        aa_eff = abs(math.log(aa["ratio_vs_lift_scan_geomean"]))
        pos = W["contrasts"]["lift_scan_2pass"]
        pos_ok = pos["ci_adjusted"][0] > 1.5
        W["negative_control_aa"] = {"ci_excludes_1": aa_excl, "abs_log_effect": aa_eff}
        W["positive_control_2pass"] = {"detected": pos_ok, "expected_ratio": 2.0,
                                       "ratio": pos["ratio_vs_lift_scan_geomean"], "rule": "adjusted lower bound > 1.5"}
        for arm in PRIMARY:
            c = W["contrasts"][arm]
            lo, hi = c["ci_adjusted"]
            if W["arms"][arm]["incorrect_rows"] or W["arms"][REF]["incorrect_rows"]:
                v = "invalid (incorrect rows)"
            elif not pos_ok:
                v = "inconclusive (positive control failed)"
            elif lo > 1:
                v = "lift_scan faster in the loop"
            elif hi < 1:
                v = f"{arm} faster than lift_scan in the loop"
            else:
                v = "not resolved"
            if aa_excl and v.endswith("in the loop") and abs(math.log(c["ratio_vs_lift_scan_geomean"])) <= 2 * aa_eff:
                v = "not resolved (within placement effect)"
            c["verdict"] = v
        five = PRIMARY + [REF]
        W["loop_order"] = sorted(five, key=lambda a: W["arms"][a]["median_ns_per_key"])
        if iso:
            io = sorted(five, key=lambda a: iso[a])
            W["isolated_ir_order"] = io
            W["kendall_tau_loop_vs_isolated"] = kendall(W["loop_order"], io)
            W["isolated_ir_ratio_vs_lift_scan"] = {a: iso[a] / iso[REF] for a in PRIMARY}
        out["workloads"][w] = W
    with open(sys.argv[2], "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(out["label"])
    for w, W in out["workloads"].items():
        print(f"{w}: order {W['loop_order']}  A/A excl1={W['negative_control_aa']['ci_excludes_1']}"
              f"  positive(2pass {W['positive_control_2pass']['ratio']:.3f})={W['positive_control_2pass']['detected']}")
        for a in PRIMARY:
            c = W["contrasts"][a]
            print(f"  {a:14s} {c['ratio_vs_lift_scan_geomean']:.3f} [{c['ci_adjusted'][0]:.3f}, "
                  f"{c['ci_adjusted'][1]:.3f}]  {c['verdict']}")


if __name__ == "__main__":
    main()
