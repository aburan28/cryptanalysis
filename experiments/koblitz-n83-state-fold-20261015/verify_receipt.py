#!/usr/bin/env python3
"""Audit a receipt of the n=83 state-fold run and apply the frozen decision rule.

1. loads `runs.jsonl` against `schedule.json` and decodes every raw record;
2. checks the gates of `protocol.json` (validity, index digests are checked
   per process by `arm.py`; here: one scalar per point across every IC arm
   and the tuned rho with an oracle replay, one relation per order group,
   the probe identities, and the rank arms' factor-log tables);
3. checks the controls (A/A, planted) and computes the primary and every
   secondary statistic with bootstrap intervals;
4. writes `result.json` and `result_table.md` into the receipt directory.

`--correctness-only` (local smoke) runs steps 1-2 on whatever rows exist and
writes `correctness.json` with no timing values in it.
"""

import argparse
import base64
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
FEISTEL_GROUP = ("cB", "cF", "cFaa", "cX", "cBF", "cFF", "cFI")
LEFT_GROUP = ("cBL", "cFL")
FOLDED_FEISTEL = ("cF", "cFaa", "cX", "cFF", "cFI")
IC_COLD = FEISTEL_GROUP + LEFT_GROUP
DRAWS = 10000
SEED = 20261015


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def raw_record(receipt, row):
    for line in (receipt / row["stdout_file"]).read_text().splitlines():
        if line.startswith("raw_b64="):
            return json.loads(base64.b64decode(line[len("raw_b64="):]))
    return None


def oracle():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402
    beats = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                       .read_text())["beats"]
    return panel.cached_curve(dict(beats["koblitz.compact_orbit.n83_single_target"]["curve_fixture"]))


def load(receipt, schedule, protocol, partial):
    rows = jsonl(receipt / "runs.jsonl")
    by_serial, problems = {}, []
    for row in rows:
        if row["serial"] in by_serial:
            problems.append("serial %d has two rows" % row["serial"])
        by_serial[row["serial"]] = row
    scheduled = {run["serial"]: (segment, run) for segment in schedule["segments"] for run in segment["runs"]}
    missing = sorted(set(scheduled) - set(by_serial))
    if missing and not partial:
        problems.append("%d scheduled runs have no row" % len(missing))
    runs = []
    for serial, row in sorted(by_serial.items()):
        segment, run = scheduled[serial]
        if row["arm"] != run["arm"] or row["point_id"] != run["point_id"] or row["seed"] != run["seed"]:
            problems.append("row %d does not match the schedule" % serial)
        item = {"serial": serial, "segment": segment["id"], "panel": segment["panel"], "arm": run["arm"],
                "kind": protocol["arms"][run["arm"]]["kind"], "unit": run["point_id"], "point": run["point"],
                "status": row["status"], "issues": list(row.get("issues", [])),
                "contention": row.get("contention_flags", [])}
        if row["status"] != "skipped_time_guard":
            raw = raw_record(receipt, row)
            if raw is None:
                item["issues"].append("no raw producer record")
                item["status"] = "invalid"
            else:
                if raw.get("issues"):
                    item["issues"] += ["arm: " + issue for issue in raw["issues"]]
                    item["status"] = "invalid"
                item["f"] = raw.get("fields") or {}
                if item["kind"] == "rho_tuned":
                    item["f"]["rho_cold_ms"] = (item["f"].get("setup_ms") or 0.0) + (item["f"].get("online_ms") or 0.0)
                else:
                    summary = next((rec for rec in raw["records"]
                                    if rec.get("kind") == "compact_orbit_dlp_summary"), {})
                    item["rank_attempt_ns"] = summary.get("rank_attempt_ns")
                    item["rank_attempt_probes"] = summary.get("rank_attempt_probes")
        runs.append(item)
    return runs, problems, missing


def by_unit(runs, kinds):
    out = {}
    for r in runs:
        if r["status"] == "valid" and r["kind"] in kinds:
            out.setdefault(r["unit"], {})[r["arm"]] = r
    return out


def correctness(runs, protocol):
    checks, detail = {}, {}
    executed = [r for r in runs if r["status"] != "skipped_time_guard"]
    checks["all_executed_rows_valid"] = all(r["status"] == "valid" for r in executed)
    detail["invalid_rows"] = [{"serial": r["serial"], "arm": r["arm"], "issues": r["issues"]}
                              for r in executed if r["status"] != "valid"]
    curve = oracle()

    def replay(point, scalar):
        return curve.mul(curve.g, int(scalar)) == curve.decode([int(v) for v in point])

    units = by_unit(runs, ("ic_cold", "rho_tuned", "ic_rank"))
    scalar_ok, replay_ok, rel_ok, probe_ok = {}, {}, {}, {}
    for unit, arms in sorted(units.items()):
        scalars = {str(r["f"].get("recovered_scalar")) for r in arms.values()}
        scalar_ok[unit] = len(scalars) == 1 and "None" not in scalars
        point = next(iter(arms.values()))["point"]
        replay_ok[unit] = scalar_ok[unit] and replay(point, next(iter(scalars)))
        ok = True
        for group in (FEISTEL_GROUP, LEFT_GROUP):
            relations = {json.dumps(arms[a]["f"]["relation"]) for a in group if a in arms}
            ok = ok and len(relations) <= 1
        for rank_arm in ("kB", "kN"):  # same Feistel online path after the rank stage
            if rank_arm in arms and "cB" in arms:
                ok = ok and arms[rank_arm]["f"]["relation"] == arms["cB"]["f"]["relation"]
        rel_ok[unit] = ok
        p = {a: arms[a]["f"].get("ops") for a in arms if a in IC_COLD}
        good = True
        if "cB" in p and "cBF" in p:
            good = good and p["cB"] == p["cBF"]
        folded = [p[a] for a in FOLDED_FEISTEL if a in p]
        good = good and len(set(folded)) <= 1
        if folded and "cB" in p:
            good = good and folded[0] <= p["cB"]
        if "cX" in p and "cB" in p:
            good = good and p["cX"] + int(arms["cX"]["f"].get("audit_probes") or 0) == p["cB"]
        if "cFL" in p and "cBL" in p:
            good = good and p["cFL"] <= p["cBL"]
        probe_ok[unit] = good
    checks["one_scalar_per_point_ic_and_rho"] = all(scalar_ok.values()) if scalar_ok else None
    checks["oracle_replay"] = all(replay_ok.values()) if replay_ok else None
    checks["one_relation_per_order_group"] = all(rel_ok.values()) if rel_ok else None
    checks["probe_identities"] = all(probe_ok.values()) if probe_ok else None
    rank_rows = [r for r in executed if r["kind"] == "ic_rank"]
    checks["rank_tables_equal_archived"] = (all(r["status"] == "valid" and r["f"].get("logs_equal_archived") is True
                                                for r in rank_rows) if rank_rows else None)
    detail.update({"units_seen": len(units),
                   "scalar_failures": sorted(u for u, v in scalar_ok.items() if not v),
                   "relation_failures": sorted(u for u, v in rel_ok.items() if not v),
                   "probe_failures": sorted(u for u, v in probe_ok.items() if not v)})
    return checks, detail


def ratio_of_means(pairs):
    return sum(a for a, _ in pairs) / sum(b for _, b in pairs)


def geo_ratio(pairs):
    return math.exp(statistics.mean(math.log(a) - math.log(b) for a, b in pairs))


def boot(pairs, statistic, seed):
    rng = random.Random(seed)
    n = len(pairs)
    values = sorted(statistic([pairs[rng.randrange(n)] for _ in range(n)]) for _ in range(DRAWS))
    return [values[int(0.025 * DRAWS)], values[int(0.975 * DRAWS) - 1]]


def paired(units, a, b, key):
    return [(arms[a]["f"][key], arms[b]["f"][key]) for _, arms in sorted(units.items())
            if a in arms and b in arms and arms[a]["f"].get(key) is not None and arms[b]["f"].get(key) is not None]


def estimate(pairs, seed, statistic=ratio_of_means):
    if not pairs:
        return None
    return {"estimate": statistic(pairs), "ci95": boot(pairs, statistic, seed), "n": len(pairs)}


def statistics_block(runs, protocol):
    units = by_unit(runs, ("ic_cold", "rho_tuned"))
    complete = {u: a for u, a in units.items() if all(x in a for x in protocol["design"]["cold_arms"])}
    out = {"complete_points": len(complete)}
    out["primary_cold_cB_over_cF"] = estimate(paired(complete, "cB", "cF", "cold_ms"), SEED)
    out["aa_cold_cF_over_cFaa"] = estimate(paired(complete, "cF", "cFaa", "cold_ms"), SEED + 1)
    out["planted_cold_cX_over_cF"] = estimate(paired(complete, "cX", "cF", "cold_ms"), SEED + 2)
    out["planted_cold_cB_over_cX"] = estimate(paired(complete, "cB", "cX", "cold_ms"), SEED + 3)
    for key, name in (("setup_ms", "setup"), ("online_ms", "online"), ("index_ms", "index_build"),
                      ("peak_rss_bytes", "peak_rss")):
        out[name + "_cB_over_cF"] = estimate(paired(complete, "cB", "cF", key), SEED + 10)
    out["online_cB_over_cF_geometric"] = estimate(paired(complete, "cB", "cF", "online_ms"), SEED + 11, geo_ratio)
    out["cold_cBL_over_cFL"] = estimate(paired(complete, "cBL", "cFL", "cold_ms"), SEED + 20)
    out["cold_cBF_over_cFF"] = estimate(paired(complete, "cBF", "cFF", "cold_ms"), SEED + 21)
    out["cold_cF_over_cFI"] = estimate(paired(complete, "cF", "cFI", "cold_ms"), SEED + 22)
    out["online_cB_over_cBL"] = estimate(paired(complete, "cBL", "cB", "online_ms"), SEED + 23)
    out["online_cBF_over_cB"] = estimate(paired(complete, "cBF", "cB", "online_ms"), SEED + 24)
    means = {arm: statistics.mean(a[arm]["f"]["cold_ms"] for a in complete.values())
             for arm in IC_COLD} if complete else {}
    out["mean_cold_ms"] = means
    for key in ("setup_ms", "online_ms", "index_ms", "peak_rss_bytes"):
        out["mean_" + key] = ({arm: statistics.mean(a[arm]["f"][key] for a in complete.values()) for arm in IC_COLD}
                              if complete else {})
    if means:
        single = min(("cBL", "cBF"), key=lambda a: means[a])
        out["better_unfolded_single_arm"] = single
        out["cold_better_single_over_cF"] = estimate(paired(complete, single, "cF", "cold_ms"), SEED + 25)
    rho = [a["rT"]["f"] for a in complete.values()]
    if rho:
        steps = sum(float(r["ops"]) for r in rho)
        ms_per_step = sum(r["online_ms"] for r in rho) / steps
        sqrt_r = protocol["online"]["sqrt_r"]
        out["rho_ms_per_step"] = ms_per_step
        out["rho_mean_online_ms"] = statistics.mean(r["online_ms"] for r in rho)
        out["rho_mean_cold_ms"] = statistics.mean(r["rho_cold_ms"] for r in rho)
        for arm in ("cB", "cF"):
            out["cold_gap_%s_over_rT" % arm] = estimate(
                [(a[arm]["f"]["cold_ms"], a["rT"]["f"]["rho_cold_ms"]) for a in complete.values()], SEED + 30)
            out["online_gap_rT_over_%s" % arm] = estimate(
                [(a["rT"]["f"]["online_ms"], a[arm]["f"]["online_ms"]) for a in complete.values()], SEED + 31)
        s = {arm: means[arm] / ms_per_step / sqrt_r for arm in ("cB", "cF", "cFI")}
        out["S_cold_setup_plus_online"] = s
        out["delta_S_cold_setup_plus_online_cB_to_cF"] = s["cF"] - s["cB"]
    rank = [r for r in runs if r["kind"] == "ic_rank" and r["status"] == "valid"]
    rank_out = {}
    for arm in ("kB", "kN"):
        rows = [r for r in rank if r["arm"] == arm]
        if rows:
            rank_out[arm] = {"rank_stage_ms": [r["f"]["rank_stage_ms"] for r in rows],
                             "cold_incl_rank_ms": [r["f"]["cold_ms"] for r in rows],
                             "setup_incl_rank_ms": [r["f"]["setup_ms"] for r in rows],
                             "attempts": [len(r["rank_attempt_ns"] or []) for r in rows],
                             "mean_attempt_ms": statistics.mean(v / 1e6 for r in rows for v in r["rank_attempt_ns"]),
                             "mean_attempt_probes": statistics.mean(v for r in rows for v in r["rank_attempt_probes"] if v is not None)}
    if "kB" in rank_out and "kN" in rank_out:
        b = [v / 1e6 for r in rank if r["arm"] == "kB" for v in r["rank_attempt_ns"]]
        n = [v / 1e6 for r in rank if r["arm"] == "kN" for v in r["rank_attempt_ns"]]
        rng = random.Random(SEED + 40)
        draws = sorted(statistics.mean(rng.choice(b) for _ in b) / statistics.mean(rng.choice(n) for _ in n)
                       for _ in range(2000))
        rank_out["per_attempt_cost_kB_over_kN"] = {"estimate": statistics.mean(b) / statistics.mean(n),
                                                   "ci95": [draws[50], draws[1949]], "attempts": [len(b), len(n)],
                                                   "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}
        rank_out["rank_stage_kB_over_kN"] = (statistics.mean(rank_out["kB"]["rank_stage_ms"]) /
                                             statistics.mean(rank_out["kN"]["rank_stage_ms"]))
        if means and rho:
            rb, rn = statistics.mean(rank_out["kB"]["rank_stage_ms"]), statistics.mean(rank_out["kN"]["rank_stage_ms"])
            ledger = {"old_rank_kB_plus_cB": (rb + means["cB"]) / ms_per_step / sqrt_r,
                      "fold_only_rank_kB_plus_cF": (rb + means["cF"]) / ms_per_step / sqrt_r,
                      "fold_and_rank_kN_plus_cF": (rn + means["cF"]) / ms_per_step / sqrt_r}
            rank_out["S_cold_ledger_rank_plus_setup_plus_online"] = ledger
            rank_out["cold_gap_incl_rank_over_rT"] = {k: (v * ms_per_step * sqrt_r) / out["rho_mean_cold_ms"]
                                                      for k, v in ledger.items()}
    out["rank_stage"] = rank_out
    return out


def decide(checks, stats):
    gates_ok = all(v is not False for v in checks.values())
    aa, planted, primary = (stats.get("aa_cold_cF_over_cFaa"), stats.get("planted_cold_cX_over_cF"),
                            stats.get("primary_cold_cB_over_cF"))
    controls = {"aa_inside_0.97_1.03": aa is not None and 0.97 <= aa["estimate"] <= 1.03,
                "planted_lower_bound_above_1": planted is not None and planted["ci95"][0] > 1.0}
    if not gates_ok or not all(controls.values()) or primary is None:
        return "invalid", controls
    lo, hi = primary["ci95"]
    return ("improvement" if lo > 1 else "regression" if hi < 1 else "not_separated"), controls


def fmt(e):
    if not e:
        return "n/a"
    return "%.4f [%.4f, %.4f] (n=%d)" % (e["estimate"], e["ci95"][0], e["ci95"][1], e["n"])


def table(result):
    s = result["statistics"]
    lines = ["# n=83 state fold: frozen result", "", "Verdict: **%s**" % result["decision"], "",
             "| statistic | estimate [95%] |", "| --- | --- |"]
    for key in ("primary_cold_cB_over_cF", "aa_cold_cF_over_cFaa", "planted_cold_cX_over_cF",
                "planted_cold_cB_over_cX", "setup_cB_over_cF", "online_cB_over_cF", "online_cB_over_cF_geometric",
                "index_build_cB_over_cF", "peak_rss_cB_over_cF", "cold_cBL_over_cFL", "cold_cBF_over_cFF",
                "cold_better_single_over_cF", "cold_cF_over_cFI", "cold_gap_cB_over_rT", "cold_gap_cF_over_rT",
                "online_gap_rT_over_cB", "online_gap_rT_over_cF"):
        lines.append("| %s | %s |" % (key, fmt(s.get(key))))
    lines += ["", "Means (ms): " + json.dumps({k: round(v, 1) for k, v in s.get("mean_cold_ms", {}).items()}),
              "", "Cold S (setup + online): " + json.dumps(s.get("S_cold_setup_plus_online")),
              "", "Rank stage: " + json.dumps({k: v for k, v in s.get("rank_stage", {}).items()
                                               if k not in ("kB", "kN")}),
              "", "Checks: " + json.dumps(result["checks"]), "", "Controls: " + json.dumps(result["controls"])]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--correctness-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    schedule = json.loads((HERE / "schedule.json").read_text())
    runs, problems, missing = load(args.receipt, schedule, protocol, args.correctness_only)
    checks, detail = correctness(runs, protocol)
    checks["receipt_matches_schedule"] = not problems
    if args.correctness_only:
        out = {"checks": checks, "detail": detail, "problems": problems, "rows": len(runs)}
        (args.receipt / "correctness.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(json.dumps(out, sort_keys=True))
        return
    stats = statistics_block(runs, protocol)
    checks["every_scheduled_row_present"] = not missing
    checks["all_points_complete"] = stats["complete_points"] == protocol["design"]["cold_points"]
    decision, controls = decide(checks, stats)
    result = {"kind": protocol["kind"], "decision": decision, "checks": checks, "controls": controls,
              "detail": detail, "problems": problems,
              "skipped_time_guard": sum(1 for r in runs if r["status"] == "skipped_time_guard"),
              "contention_flags": [{"serial": r["serial"], "arm": r["arm"], "flags": r["contention"]}
                                   for r in runs if r.get("contention")],
              "statistics": stats}
    (args.receipt / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (args.receipt / "result_table.md").write_text(table(result))
    print(json.dumps({"decision": decision, "primary": stats.get("primary_cold_cB_over_cF"),
                      "controls": controls, "checks": checks}, sort_keys=True))


if __name__ == "__main__":
    main()
