#!/usr/bin/env python3
"""Audit a receipt of the n=83 stacked run and apply the frozen decision rule.

1. loads `runs.jsonl` against `schedule.json` and decodes every raw record;
2. checks the gates of `protocol.json` (per-process layout, fold and index
   digests are checked by `arm.py`; here: one scalar per point across every
   IC arm and the tuned rho with an oracle replay, one relation per point
   across every IC process, the probe identities, Q0 against the archived
   Feistel identity, and the rank arms' factor-log tables, relation digests
   and per-attempt probes);
3. checks the controls (A/A, planted) and computes the primary and every
   secondary statistic with bootstrap intervals;
4. writes `result.json` and `result_table.md` into the receipt directory.

The end-to-end cold cost of an arm pair (rank arm k, cold arm c) is
E2E = mean rank stage of k over its rank processes + mean cold(c) over the
cold points (cold = setup + one-target online with the verified cached
table). Its bootstrap resamples the points (paired across arms) and, for
each rank process independently, its attempts (the stage's non-attempt time
is kept), 10,000 draws.

`--correctness-only` (local smoke) runs steps 1-2 on whatever rows exist and
writes `correctness.json` with no timing values in it.

Adapted from `koblitz-n83-state-fold-20261015`'s `verify_receipt.py`.
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
UNFOLDED_COLD = ("cP", "cSmF")
FOLDED_COLD = ("cS", "cSaa", "cSX", "cSmS", "cSF", "cSI")
IC_COLD = UNFOLDED_COLD + FOLDED_COLD
LIFT_RANK = ("kS", "kSaa", "kSmF", "kSmS")
FOLDED_RANK = ("kS", "kSaa", "kSmS")
PAIRS = {"cP": "kP", "cS": "kS", "cSaa": "kSaa", "cSmF": "kSmF", "cSmS": "kSmS"}
DRAWS = 10000
SEED = 20261016


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


def by_unit(runs, kinds, panels=("C", "K", "O")):
    out = {}
    for r in runs:
        if r["status"] == "valid" and r["kind"] in kinds and r["panel"] in panels:
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
        relations = {json.dumps(r["f"]["relation"]) for r in arms.values() if r["kind"] != "rho_tuned"}
        rel_ok[unit] = len(relations) <= 1
        p = {a: r["f"].get("ops") for a, r in arms.items() if r["kind"] != "rho_tuned"}
        unfolded = [p[a] for a in UNFOLDED_COLD + ("kP", "kSmF") if a in p]
        folded = [p[a] for a in FOLDED_COLD + FOLDED_RANK if a in p]
        good = len(set(unfolded)) <= 1 and len(set(folded)) <= 1
        if unfolded and folded:
            good = good and folded[0] <= unfolded[0]
        if "cSX" in p and unfolded:
            good = good and p["cSX"] + int(arms["cSX"]["f"].get("audit_probes") or 0) == unfolded[0]
        probe_ok[unit] = good
    checks["one_scalar_per_point_ic_and_rho"] = all(scalar_ok.values()) if scalar_ok else None
    checks["oracle_replay"] = all(replay_ok.values()) if replay_ok else None
    checks["one_relation_per_point_every_ic_process"] = all(rel_ok.values()) if rel_ok else None
    checks["probe_identities"] = all(probe_ok.values()) if probe_ok else None
    q0 = units.get("q0", {})
    want = protocol["online"]["q0_identity"]
    if q0:
        checks["q0_matches_archived_feistel_identity"] = all(
            r["f"].get("relation") == want["relation"] and str(r["f"].get("recovered_scalar")) == want["scalar"] and
            r["f"].get("ops") == want["probes_unfolded" if not protocol["arms"][a]["fold"] else "probes_folded"]
            for a, r in q0.items())
    else:
        checks["q0_matches_archived_feistel_identity"] = None
    rank_rows = [r for r in executed if r["kind"] == "ic_rank"]
    checks["rank_tables_equal_archived"] = (all(r["status"] == "valid" and r["f"].get("logs_equal_archived") is True
                                                for r in rank_rows) if rank_rows else None)
    rank_ok = {}
    for unit, arms in by_unit(runs, ("ic_rank",)).items():
        digests = {arms[a]["f"].get("rank_relations_blake3") for a in LIFT_RANK if a in arms}
        probes = {json.dumps(arms[a]["rank_attempt_probes"]) for a in FOLDED_RANK if a in arms}
        good = len(digests) <= 1 and None not in digests and len(probes) <= 1
        if "kSmF" in arms and "kS" in arms:
            a, b = arms["kSmF"]["rank_attempt_probes"], arms["kS"]["rank_attempt_probes"]
            good = good and len(a) == len(b) and all(x is not None and y is not None and x >= y for x, y in zip(a, b))
        rank_ok[unit] = good
    checks["rank_relations_and_probes_identical_across_layouts"] = all(rank_ok.values()) if rank_ok else None
    detail.update({"units_seen": len(units),
                   "scalar_failures": sorted(u for u, v in scalar_ok.items() if not v),
                   "relation_failures": sorted(u for u, v in rel_ok.items() if not v),
                   "probe_failures": sorted(u for u, v in probe_ok.items() if not v),
                   "rank_failures": sorted(u for u, v in rank_ok.items() if not v)})
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


def rank_processes(runs, arm):
    """(non-attempt ms, [attempt ms]) for each valid rank process of `arm`."""
    out = []
    for r in runs:
        if r["kind"] == "ic_rank" and r["arm"] == arm and r["status"] == "valid":
            attempts = [v / 1e6 for v in r["rank_attempt_ns"]]
            out.append((r["f"]["rank_stage_ms"] - sum(attempts), attempts))
    return out


def e2e(points, cold_arm, procs, draw=None, rng=None):
    if draw is None:
        cold = statistics.mean(points[u][cold_arm]["f"]["cold_ms"] for u in points)
        rank = statistics.mean(rest + sum(att) for rest, att in procs)
        return rank + cold
    cold = statistics.mean(points[u][cold_arm]["f"]["cold_ms"] for u in draw)
    rank = statistics.mean(rest + sum(rng.choices(att, k=len(att))) for rest, att in procs)
    return rank + cold


def e2e_ratio(runs, complete, a, b, seed, denominator_rho=False):
    """E2E(a) / E2E(b) for cold arms a, b (paired rank arms PAIRS[...]), or E2E(a) / mean rho cold."""
    pa = rank_processes(runs, PAIRS[a])
    pb = None if denominator_rho else rank_processes(runs, PAIRS[b])
    if not complete or not pa or (pb is not None and not pb):
        return None
    units = sorted(complete)

    def value(draw, rng):
        num = e2e(complete, a, pa, draw, rng)
        if denominator_rho:
            pool = draw if draw is not None else units
            return num / statistics.mean(complete[u]["rT"]["f"]["rho_cold_ms"] for u in pool)
        return num / e2e(complete, b, pb, draw, rng)

    point = value(None, None)
    rng = random.Random(seed)
    draws = sorted(value([units[rng.randrange(len(units))] for _ in units], rng) for _ in range(DRAWS))
    return {"estimate": point, "ci95": [draws[int(0.025 * DRAWS)], draws[int(0.975 * DRAWS) - 1]],
            "n_points": len(units), "rank_processes": [len(pa)] + ([] if pb is None else [len(pb)]),
            "bootstrap": "points resampled (paired); attempts resampled within each rank process; %d draws" % DRAWS}


def attempt_ratio(runs, a, b, seed):
    x = [v for _, att in rank_processes(runs, a) for v in att]
    y = [v for _, att in rank_processes(runs, b) for v in att]
    if not x or not y:
        return None
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choices(x, k=len(x))) / statistics.mean(rng.choices(y, k=len(y)))
                   for _ in range(2000))
    return {"estimate": statistics.mean(x) / statistics.mean(y), "ci95": [draws[50], draws[1949]],
            "attempts": [len(x), len(y)], "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}


def statistics_block(runs, protocol):
    units = by_unit(runs, ("ic_cold", "rho_tuned"), panels=("C",))
    complete = {u: a for u, a in units.items() if all(x in a for x in protocol["design"]["cold_arms"])}
    out = {"complete_points": len(complete)}
    out["primary_e2e_cP_over_cS"] = e2e_ratio(runs, complete, "cP", "cS", SEED)
    out["aa_e2e_cS_over_cSaa"] = e2e_ratio(runs, complete, "cS", "cSaa", SEED + 1)
    out["aa_cold_cS_over_cSaa"] = estimate(paired(complete, "cS", "cSaa", "cold_ms"), SEED + 2)
    out["planted_cold_cSX_over_cS"] = estimate(paired(complete, "cSX", "cS", "cold_ms"), SEED + 3)
    out["online_cP_over_cS"] = estimate(paired(complete, "cP", "cS", "online_ms"), SEED + 4)
    out["online_cP_over_cS_geometric"] = estimate(paired(complete, "cP", "cS", "online_ms"), SEED + 5, geo_ratio)
    for key, name in (("cold_ms", "cold_without_rank"), ("setup_ms", "setup"), ("index_ms", "index_build"),
                      ("peak_rss_bytes", "peak_rss")):
        out[name + "_cP_over_cS"] = estimate(paired(complete, "cP", "cS", key), SEED + 10)
    # Ablations: the stack without one component, over the stack.
    out["e2e_cSmF_over_cS"] = e2e_ratio(runs, complete, "cSmF", "cS", SEED + 20)
    out["e2e_cSmS_over_cS"] = e2e_ratio(runs, complete, "cSmS", "cS", SEED + 21)
    for other, seed in (("cSmF", 22), ("cSmS", 26)):
        out["online_%s_over_cS" % other] = estimate(paired(complete, other, "cS", "online_ms"), SEED + seed)
        out["online_%s_over_cS_geometric" % other] = estimate(paired(complete, other, "cS", "online_ms"),
                                                               SEED + seed + 1, geo_ratio)
        out["cold_without_rank_%s_over_cS" % other] = estimate(paired(complete, other, "cS", "cold_ms"), SEED + seed + 2)
        out["setup_%s_over_cS" % other] = estimate(paired(complete, other, "cS", "setup_ms"), SEED + seed + 3)
    # Optional components on top of the stack (no rank arm; cold without the rank stage).
    for other, seed in (("cSF", 30), ("cSI", 33)):
        out["cold_without_rank_cS_over_%s" % other] = estimate(paired(complete, "cS", other, "cold_ms"), SEED + seed)
        out["online_cS_over_%s" % other] = estimate(paired(complete, "cS", other, "online_ms"), SEED + seed + 1)
        out["setup_cS_over_%s" % other] = estimate(paired(complete, "cS", other, "setup_ms"), SEED + seed + 2)
    for key in ("cold_ms", "setup_ms", "online_ms", "index_ms", "peak_rss_bytes"):
        out["mean_" + key] = ({arm: statistics.mean(a[arm]["f"][key] for a in complete.values()) for arm in IC_COLD}
                              if complete else {})
    rank_out = {}
    for arm in ("kP",) + LIFT_RANK:
        rows = [r for r in runs if r["kind"] == "ic_rank" and r["arm"] == arm and r["status"] == "valid"]
        if rows:
            rank_out[arm] = {"rank_stage_ms": [r["f"]["rank_stage_ms"] for r in rows],
                             "single_process_e2e_cold_ms": [r["f"]["cold_ms"] for r in rows],
                             "setup_incl_rank_ms": [r["f"]["setup_ms"] for r in rows],
                             "attempts": [len(r["rank_attempt_ns"] or []) for r in rows],
                             "mean_attempt_ms": statistics.mean(v / 1e6 for r in rows for v in r["rank_attempt_ns"]),
                             "mean_attempt_probes": statistics.mean(v for r in rows for v in r["rank_attempt_probes"]
                                                                    if v is not None)}
    for a, b, seed in (("kP", "kS", 40), ("kSmF", "kS", 41), ("kSmS", "kS", 42), ("kS", "kSaa", 43)):
        if a in rank_out and b in rank_out:
            rank_out["per_attempt_cost_%s_over_%s" % (a, b)] = attempt_ratio(runs, a, b, SEED + seed)
            rank_out["rank_stage_%s_over_%s" % (a, b)] = (statistics.mean(rank_out[a]["rank_stage_ms"]) /
                                                          statistics.mean(rank_out[b]["rank_stage_ms"]))
            rank_out["single_process_e2e_%s_over_%s" % (a, b)] = (
                statistics.mean(rank_out[a]["single_process_e2e_cold_ms"]) /
                statistics.mean(rank_out[b]["single_process_e2e_cold_ms"]))
    out["rank_stage"] = rank_out
    rho = [a["rT"]["f"] for a in complete.values()]
    if rho:
        steps = sum(float(r["ops"]) for r in rho)
        ms_per_step = sum(r["online_ms"] for r in rho) / steps
        sqrt_r = protocol["online"]["sqrt_r"]
        out["rho_ms_per_step"] = ms_per_step
        out["rho_mean_online_ms"] = statistics.mean(r["online_ms"] for r in rho)
        out["rho_mean_cold_ms"] = statistics.mean(r["rho_cold_ms"] for r in rho)
        out["S_rho_cold"] = out["rho_mean_cold_ms"] / ms_per_step / sqrt_r
        out["S_rho_online"] = out["rho_mean_online_ms"] / ms_per_step / sqrt_r
        s_e2e, s_cold, s_online = {}, {}, {}
        for arm in ("cP", "cS", "cSaa", "cSmF", "cSmS"):
            if PAIRS[arm] in rank_out:
                s_e2e[arm] = e2e(complete, arm, rank_processes(runs, PAIRS[arm])) / ms_per_step / sqrt_r
        for arm in IC_COLD:
            s_cold[arm] = out["mean_cold_ms"][arm] / ms_per_step / sqrt_r
            s_online[arm] = out["mean_online_ms"][arm] / ms_per_step / sqrt_r
        out["S_e2e_cold"] = s_e2e
        out["S_cold_without_rank"] = s_cold
        out["S_online"] = s_online
        if "cP" in s_e2e and "cS" in s_e2e:
            out["delta_S_e2e_cold_cP_to_cS"] = s_e2e["cS"] - s_e2e["cP"]
        out["delta_S_online_cP_to_cS"] = s_online["cS"] - s_online["cP"]
        for arm, seed in (("cP", 50), ("cS", 51)):
            out["e2e_cold_gap_%s_over_rT" % arm] = e2e_ratio(runs, complete, arm, None, SEED + seed, denominator_rho=True)
            out["online_gap_rT_over_%s" % arm] = estimate(
                [(a["rT"]["f"]["online_ms"], a[arm]["f"]["online_ms"]) for a in complete.values()], SEED + seed + 10)
            out["online_gap_%s_over_rT" % arm] = estimate(
                [(a[arm]["f"]["online_ms"], a["rT"]["f"]["online_ms"]) for a in complete.values()], SEED + seed + 20)
    return out


def decide(checks, stats):
    gates_ok = all(v is not False for v in checks.values())
    aa_e2e, aa_cold = stats.get("aa_e2e_cS_over_cSaa"), stats.get("aa_cold_cS_over_cSaa")
    planted, primary = stats.get("planted_cold_cSX_over_cS"), stats.get("primary_e2e_cP_over_cS")
    controls = {"aa_e2e_inside_0.97_1.03": aa_e2e is not None and 0.97 <= aa_e2e["estimate"] <= 1.03,
                "aa_cold_inside_0.97_1.03": aa_cold is not None and 0.97 <= aa_cold["estimate"] <= 1.03,
                "planted_lower_bound_above_1": planted is not None and planted["ci95"][0] > 1.0}
    if not gates_ok or not all(controls.values()) or primary is None:
        return "invalid", controls
    lo, hi = primary["ci95"]
    return ("improvement" if lo > 1 else "regression" if hi < 1 else "not_separated"), controls


def fmt(e):
    if not e:
        return "n/a"
    n = e.get("n", e.get("n_points"))
    return "%.4f [%.4f, %.4f] (n=%s)" % (e["estimate"], e["ci95"][0], e["ci95"][1], n)


def table(result):
    s = result["statistics"]
    lines = ["# n=83 stacked producer: frozen result", "", "Verdict: **%s**" % result["decision"], "",
             "| statistic | estimate [95%] |", "| --- | --- |"]
    for key in ("primary_e2e_cP_over_cS", "aa_e2e_cS_over_cSaa", "aa_cold_cS_over_cSaa", "planted_cold_cSX_over_cS",
                "online_cP_over_cS", "online_cP_over_cS_geometric", "cold_without_rank_cP_over_cS",
                "setup_cP_over_cS", "index_build_cP_over_cS", "peak_rss_cP_over_cS",
                "e2e_cSmF_over_cS", "e2e_cSmS_over_cS", "online_cSmF_over_cS", "online_cSmS_over_cS",
                "cold_without_rank_cSmF_over_cS", "cold_without_rank_cSmS_over_cS",
                "cold_without_rank_cS_over_cSF", "online_cS_over_cSF", "cold_without_rank_cS_over_cSI",
                "e2e_cold_gap_cP_over_rT", "e2e_cold_gap_cS_over_rT", "online_gap_rT_over_cP",
                "online_gap_rT_over_cS"):
        lines.append("| %s | %s |" % (key, fmt(s.get(key))))
    rank = {k: v for k, v in s.get("rank_stage", {}).items() if not k.startswith("k")}
    lines += ["", "Mean cold without rank (ms): " + json.dumps({k: round(v, 1) for k, v in s.get("mean_cold_ms", {}).items()}),
              "", "S end-to-end cold: " + json.dumps(s.get("S_e2e_cold")),
              "", "S online: " + json.dumps(s.get("S_online")),
              "", "Rank stage: " + json.dumps(rank),
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
    print(json.dumps({"decision": decision, "primary": stats.get("primary_e2e_cP_over_cS"),
                      "controls": controls, "checks": checks}, sort_keys=True))


if __name__ == "__main__":
    main()
