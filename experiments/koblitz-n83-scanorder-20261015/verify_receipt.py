#!/usr/bin/env python3
"""Audit a receipt of the n=83 scan-order run and apply the frozen decision rule.

1. loads `runs.jsonl` against `schedule.json` (every scheduled serial has one
   row, arm/point/seed/slice match) and decodes every raw producer record;
2. checks the gates of `protocol.json`: the left-major arms reproduce B's
   archived probes and relation on every point; the planted arms hit the
   predicted probe count and B's relation; one scalar per point across every
   IC arm and the tuned rho; every scalar replays as [d]G = Q in the pinned
   oracle (all 17 points and all 384 held-out points); Q0 equals the
   validation sidecar;
3. computes every frozen statistic with its bootstrap interval;
4. applies the decision rule and writes `result.json` and `result_table.md`
   into the receipt directory.

`--correctness-only` (local smoke) runs steps 1-2 on whatever rows exist and
writes `correctness.json` with no timing values in it. Adapted from
`../koblitz-n83-liftscan-20261015/verify_receipt.py`.
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
IC_KINDS = ("ic", "ic_multi")


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def raw_record(receipt, row):
    for line in (receipt / row["stdout_file"]).read_text().splitlines():
        if line.startswith("raw_b64="):
            return json.loads(base64.b64decode(line[len("raw_b64="):]))
    return None


def boot(units, statistic, seed, draws=10000):
    rng = random.Random(seed)
    n = len(units)
    values = sorted(statistic([units[rng.randrange(n)] for _ in range(n)]) for _ in range(draws))
    return [values[250], values[9749]]


def median(values):
    return statistics.median(values)


def ratio_of_means(pairs):
    return sum(a for a, _ in pairs) / sum(b for _, b in pairs)


def geomean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


def ratio_of_geomeans(pairs):
    return math.exp(sum(math.log(a) - math.log(b) for a, b in pairs) / len(pairs))


def cv(values):
    mean = statistics.mean(values)
    return statistics.stdev(values) / mean if len(values) > 1 and mean else float("nan")


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
        if (row["arm"] != run["arm"] or row["point_id"] != run["point_id"] or row["seed"] != run["seed"]
                or row.get("slice") != run.get("slice")):
            problems.append("row %d does not match the schedule" % serial)
        kind = protocol["arms"][run["arm"]]["kind"]
        item = {"serial": serial, "segment": segment["id"], "panel": segment["panel"],
                "block": segment.get("block"), "arm": run["arm"], "kind": kind, "point_id": run["point_id"],
                "point": run["point"], "seed": run["seed"], "slice": run.get("slice"), "status": row["status"],
                "issues": list(row.get("issues", [])), "contention": row.get("contention_flags", [])}
        if row["status"] != "skipped_time_guard":
            raw = raw_record(receipt, row)
            fields = row.get("fields", {})
            item.update({
                "fields": fields,
                "online_ms": float(fields.get("online_ms", "nan")),
                "pdp_ms": float(fields["pdp_ms"]) if "pdp_ms" in fields else None,
                "ops": int(fields["ops"]) if fields.get("ops", "None") not in ("None", "") else None,
                "scalar": fields.get("recovered_scalar"),
                "relation": fields.get("relation"),
                "process_wall_ms": row.get("process_wall_ms"),
                "raw": raw,
            })
            if raw is None:
                item["issues"].append("no raw producer record")
                item["status"] = "invalid"
            elif raw.get("issues"):
                item["issues"] += ["arm: " + issue for issue in raw["issues"]]
                item["status"] = "invalid"
            if kind == "ic_multi" and raw is not None:
                lo = int(run["slice"].split(":")[0])
                item["targets"] = [{"seed": lo + i, "online_ms": float(r.get("online_ms") or "nan"),
                                    "probes": r.get("probes"), "scalar": r.get("recovered_scalar"),
                                    "relation": json.dumps(r.get("point_indices"), separators=(",", ":"))}
                                   for i, r in enumerate(raw["records"][:-1])]
        runs.append(item)
    return runs, problems, missing


def correctness(runs, protocol):
    checks, detail = {}, {}
    executed = [r for r in runs if r["status"] != "skipped_time_guard"]
    checks["all_executed_rows_valid"] = all(r["status"] == "valid" for r in executed)
    planted = json.loads((HERE / "inputs" / "planted_starts.json").read_text())["points"]
    by_point = {}
    for r in executed:
        if r["kind"] != "ic_multi":
            by_point.setdefault(r["point_id"], []).append(r)
    archived_ok, planted_ok, probes, scalars, replays = {}, {}, {}, {}, {}
    curve = oracle()
    fixture = json.loads((SNAPSHOT / "experiments/koblitz-single-target-n83-20261006/frozen/fixture.json").read_text())
    for point_id, items in sorted(by_point.items()):
        archived = planted[point_id]
        archived_relation = json.dumps(archived["relation_point_indices"], separators=(",", ":"))
        left_major = [r for r in items if protocol["arms"][r["arm"]].get("order") == "left_major"
                      and not protocol["arms"][r["arm"]].get("planted")]
        archived_ok[point_id] = bool(left_major) and all(
            r["ops"] == archived["baseline_probes"] and r["relation"] == archived_relation for r in left_major)
        plants = [r for r in items if protocol["arms"][r["arm"]].get("planted")]
        planted_ok[point_id] = all(r["ops"] == archived["expected_probes"] and r["relation"] == archived_relation
                                   for r in plants)
        probes[point_id] = {r["arm"]: r["ops"] for r in items}
        scalars[point_id] = sorted({str(r["scalar"]) for r in items if r["scalar"] not in (None, "None")})
        if len(scalars[point_id]) == 1:
            q = curve.decode([int(v) for v in items[0]["point"]])
            replays[point_id] = curve.mul(curve.g, int(scalars[point_id][0])) == q
        else:
            replays[point_id] = False
    checks["left_major_reproduces_archived_baseline"] = bool(archived_ok) and all(archived_ok.values())
    checks["planted_hits_predicted_probes_and_relation"] = all(planted_ok.values())
    checks["one_scalar_per_point_ic_and_rho"] = all(len(v) == 1 for v in scalars.values())
    checks["oracle_replay_every_point"] = bool(replays) and all(replays.values())
    checks["q0_equals_validation_sidecar"] = (scalars.get("q0") == [str(fixture["fixture_scalar_validation_only"])]
                                              if "q0" in scalars else None)
    # Held-out panel: one scalar per seed across hB and hP, and an oracle replay of each.
    heldout = json.loads((HERE / "inputs" / "heldout_targets.json").read_text())["points"]
    per_seed = {}
    for r in executed:
        if r["kind"] == "ic_multi":
            for t in r.get("targets", []):
                per_seed.setdefault(t["seed"], set()).add(str(t["scalar"]))
    held_ok = {}
    for seed, values in sorted(per_seed.items()):
        if len(values) != 1:
            held_ok[seed] = False
            continue
        q = curve.decode([int(v) for v in heldout[seed]["point"]])
        held_ok[seed] = curve.mul(curve.g, int(next(iter(values)))) == q
    checks["heldout_one_scalar_and_oracle_replay"] = all(held_ok.values()) if held_ok else None
    detail.update({"probes": probes, "scalars": scalars, "replays": replays,
                   "archived_baseline_identity": archived_ok, "planted_identity": planted_ok,
                   "heldout_seeds_replayed": sum(held_ok.values()), "heldout_seeds_seen": len(held_ok)})
    return checks, detail


def paired(runs, panel, num, den, key="online_ms", unit="block"):
    """Per-unit (num, den) pairs from complete, valid units."""
    units = {}
    for r in runs:
        if r["panel"] == panel and r["status"] == "valid" and r["arm"] in (num, den):
            units.setdefault(r[unit], {})[r["arm"]] = r[key]
    return [(v[num], v[den]) for _, v in sorted(units.items()) if num in v and den in v]


def heldout_pairs(runs, key="online_ms"):
    """Per-seed (hB, hP) pairs from valid held-out processes."""
    units = {}
    for r in runs:
        if r["panel"] == "H" and r["status"] == "valid":
            for t in r.get("targets", []):
                units.setdefault(t["seed"], {})[r["arm"]] = t[key]
    return [(v["hB"], v["hP"]) for _, v in sorted(units.items()) if "hB" in v and "hP" in v]


def ratio_stat(pairs, seed, estimator="median"):
    if not pairs:
        return None
    if estimator == "median":
        ratios = [a / b for a, b in pairs]
        return {"estimate": median(ratios), "ci95": boot(ratios, median, seed), "units": len(ratios),
                "per_unit": ratios, "estimator": "median of per-unit ratios"}
    if estimator == "geomean":
        return {"estimate": ratio_of_geomeans(pairs), "ci95": boot(pairs, ratio_of_geomeans, seed),
                "units": len(pairs), "estimator": "ratio of geometric means (paired)"}
    return {"estimate": ratio_of_means(pairs), "ci95": boot(pairs, ratio_of_means, seed), "units": len(pairs),
            "per_unit": [a / b for a, b in pairs], "estimator": "ratio of means (section 23)"}


def arm_summary(values, seed, law=None):
    """Geometric mean, mean, CV and (for probes) mean over the law, with bootstrap intervals."""
    if not values:
        return None
    out = {"n": len(values), "geomean": geomean(values), "geomean_ci95": boot(values, geomean, seed),
           "mean": statistics.mean(values), "mean_ci95": boot(values, statistics.mean, seed + 1),
           "cv": cv(values), "cv_ci95": boot(values, cv, seed + 2) if len(values) > 2 else None}
    if law:
        out["mean_over_law"] = out["mean"] / law
        out["mean_over_law_ci95"] = [v / law for v in out["mean_ci95"]]
    return out


def classify(stat):
    if stat is None:
        return "invalid"
    lo, hi = stat["ci95"]
    return "improvement" if lo > 1 else "regression" if hi < 1 else "not_separated"


def aa_pass(stat):
    return stat is not None and 0.97 <= stat["ci95"][0] and stat["ci95"][1] <= 1.03


def planted_pass(stat):
    return stat is not None and stat["ci95"][0] > 1


def values(runs, panel, arm, key):
    return [r[key] for r in runs if r["panel"] == panel and r["arm"] == arm and r["status"] == "valid"]


def analyse(runs, protocol, checks):
    d, online = protocol["design"], protocol["online"]
    law = online["law_probes"]
    s = {}
    # Primary: B's 16 fresh points, section-23 ratio of means, bootstrap over points.
    fresh = paired(runs, "F", "fB", "fP", unit="point_id")
    s["fresh_primary_B_over_P"] = ratio_stat(fresh, 2026101500, "means")
    s["fresh_geomean_B_over_P"] = ratio_stat(fresh, 2026101501, "geomean")
    s["fresh_median_B_over_P"] = ratio_stat(fresh, 2026101502)
    s["fresh_probes_B_over_P"] = ratio_stat(paired(runs, "F", "fB", "fP", "ops", "point_id"), 2026101503, "means")
    s["fresh_aa_B_over_Baa"] = ratio_stat(paired(runs, "F", "fB", "fBaa", unit="point_id"), 2026101504, "means")
    s["fresh_planted_B_over_H"] = ratio_stat(paired(runs, "F", "fB", "fH", unit="point_id"), 2026101505, "means")
    s["fresh_arms"] = {arm: {"online_ms": arm_summary(values(runs, "F", arm, "online_ms"), 2026101510 + 10 * i),
                             "probes": arm_summary([float(v) for v in values(runs, "F", arm, "ops")],
                                                   2026101515 + 10 * i, law)}
                       for i, arm in enumerate(("fB", "fP", "fBaa", "fH"))}
    # Q0 (one target: timing and repeat variation only).
    s["q0_B_over_P"] = ratio_stat(paired(runs, "Q", "qB", "qP"), 2026101550)
    s["q0_aa_B_over_Baa"] = ratio_stat(paired(runs, "Q", "qB", "qBaa"), 2026101551)
    s["q0_planted_B_over_H"] = ratio_stat(paired(runs, "Q", "qB", "qH"), 2026101552)
    s["q0_probes"] = {arm: sorted(set(values(runs, "Q", arm, "ops"))) for arm in d["q0_ic_arms"]}
    # Held-out panel H (secondary, powered): per target, one process per slice and arm.
    held = heldout_pairs(runs)
    s["heldout_B_over_P"] = ratio_stat(held, 2026101560, "means")
    s["heldout_geomean_B_over_P"] = ratio_stat(held, 2026101561, "geomean")
    s["heldout_probes_B_over_P"] = ratio_stat(heldout_pairs(runs, "probes"), 2026101562, "means")
    held_probes = heldout_pairs(runs, "probes")
    s["heldout_arms"] = {"hB": {"online_ms": arm_summary([a for a, _ in held], 2026101570),
                                "probes": arm_summary([float(a) for a, _ in held_probes], 2026101575, law)},
                         "hP": {"online_ms": arm_summary([b for _, b in held], 2026101580),
                                "probes": arm_summary([float(b) for _, b in held_probes], 2026101585, law)}}
    # Tuned-rho gap on the same points.
    s["rho_gap_q0_rT_over_B"] = ratio_stat(paired(runs, "Q", "rT", "qB"), 2026101590)
    s["rho_gap_q0_rT_over_P"] = ratio_stat(paired(runs, "Q", "rT", "qP"), 2026101591)
    s["rho_gap_fresh_rT_over_B"] = ratio_stat(paired(runs, "F", "rT", "fB", unit="point_id"), 2026101592, "means")
    s["rho_gap_fresh_rT_over_P"] = ratio_stat(paired(runs, "F", "rT", "fP", unit="point_id"), 2026101593, "means")
    s["rho_gap_fresh_geomean_rT_over_B"] = ratio_stat(paired(runs, "F", "rT", "fB", unit="point_id"), 2026101594, "geomean")
    s["rho_gap_fresh_geomean_rT_over_P"] = ratio_stat(paired(runs, "F", "rT", "fP", unit="point_id"), 2026101595, "geomean")
    # S and the BL gap.
    rho = [r for r in runs if r["arm"] == "rT" and r["status"] == "valid" and r["ops"]]
    sqrt_r = online["sqrt_r"]
    if rho:
        ms_per_step = median([r["online_ms"] / r["ops"] for r in rho])
        s["rho_ms_per_step"] = ms_per_step
        table = {}
        groups = (("q0_B", "Q", "qB", median), ("q0_P", "Q", "qP", median),
                  ("fresh_B", "F", "fB", statistics.mean), ("fresh_P", "F", "fP", statistics.mean))
        for label, panel, arm, agg in groups:
            times, ops = values(runs, panel, arm, "online_ms"), values(runs, panel, arm, "ops")
            if times:
                table[label] = {"online_ms": agg(times), "S_rho": agg(times) / ms_per_step / sqrt_r,
                                "S_probe": agg(ops) / sqrt_r}
        for label, column in (("heldout_B", 0), ("heldout_P", 1)):
            if held:
                times = [p[column] for p in held]
                ops = [p[column] for p in held_probes]
                table[label] = {"online_ms": statistics.mean(times),
                                "S_rho": statistics.mean(times) / ms_per_step / sqrt_r,
                                "S_probe": statistics.mean(ops) / sqrt_r}
        fresh_rho = [r["online_ms"] for r in rho if r["panel"] == "F"]
        q0_rho = [r["online_ms"] for r in rho if r["panel"] == "Q"]
        table["rho_tuned"] = {"q0_online_ms_median": median(q0_rho) if q0_rho else None,
                              "fresh_online_ms_mean": statistics.mean(fresh_rho) if fresh_rho else None,
                              "fresh_S_rho": statistics.mean(fresh_rho) / ms_per_step / sqrt_r if fresh_rho else None,
                              "fresh_steps_over_sqrt_r": statistics.mean([r["ops"] for r in rho if r["panel"] == "F"] or [0]) / sqrt_r}
        for where in ("q0", "fresh", "heldout"):
            if where + "_B" in table and where + "_P" in table:
                table[where + "_delta_S_rho"] = table[where + "_P"]["S_rho"] - table[where + "_B"]["S_rho"]
                table[where + "_delta_S_probe"] = table[where + "_P"]["S_probe"] - table[where + "_B"]["S_probe"]
        s["S"] = table
    bl = protocol["external_bl_reference"]
    for arm, key in (("fB", "rho_gap_fresh_rT_over_B"), ("fP", "rho_gap_fresh_rT_over_P")):
        if s.get(key):
            s["bl_gap_fresh_derived_IC_over_BL_" + arm] = {
                "estimate": bl["fresh_mean_rho_over_bl"] / s[key]["estimate"],
                "reading": "derived, cross-experiment: (this job's mean IC / mean tuned rho) x (BL run's mean tuned rho / mean BL) on the same 16 points"}
    # Decisions.
    exact_ok = all(v is not False for k, v in checks.items() if k != "all_executed_rows_valid")
    controls = {"fresh_aa": aa_pass(s["fresh_aa_B_over_Baa"]), "fresh_planted": planted_pass(s["fresh_planted_B_over_H"]),
                "q0_aa": aa_pass(s["q0_aa_B_over_Baa"]), "q0_planted": planted_pass(s["q0_planted_B_over_H"])}
    complete = s["fresh_primary_B_over_P"] and s["fresh_primary_B_over_P"]["units"] == d["fresh_points"]
    decision = {"controls": controls, "exactness_and_identity_ok": exact_ok}
    decision["online_fresh_primary"] = (classify(s["fresh_primary_B_over_P"])
                                        if exact_ok and all(controls.values()) and complete else "invalid")
    decision["q0_secondary"] = classify(s["q0_B_over_P"])
    complete_h = s["heldout_B_over_P"] and s["heldout_B_over_P"]["units"] == d["heldout_points"]
    decision["heldout_secondary"] = (classify(s["heldout_B_over_P"]) if exact_ok and complete_h
                                     else "invalid" if not exact_ok else "incomplete:" + classify(s["heldout_B_over_P"]))
    decision["ratchet"] = ("new one-target baseline: the feistel scan order (B's pipeline otherwise unchanged)"
                           if decision["online_fresh_primary"] == "improvement" else "no new baseline")
    return s, decision


def fmt(stat, digits=3):
    if not stat:
        return "n/a"
    return "%.*f [%.*f, %.*f] (n=%d)" % (digits, stat["estimate"], digits, stat["ci95"][0], digits,
                                          stat["ci95"][1], stat["units"])


def table_md(s, decision):
    c = decision["controls"]
    lines = ["| Statistic | Estimate [95%] | Reading |", "| --- | --- | --- |"]
    rows = [
        ("Fresh primary (section 23): left-major / feistel, online", "fresh_primary_B_over_P", decision["online_fresh_primary"]),
        ("Fresh: ratio of geometric means, online", "fresh_geomean_B_over_P", ""),
        ("Fresh: median per-point ratio, online", "fresh_median_B_over_P", ""),
        ("Fresh: section 23, probes", "fresh_probes_B_over_P", ""),
        ("Fresh A/A: left-major / left-major", "fresh_aa_B_over_Baa", "pass" if c["fresh_aa"] else "FAIL"),
        ("Fresh planted: left-major / planted half-skip", "fresh_planted_B_over_H", "pass" if c["fresh_planted"] else "FAIL"),
        ("Q0: left-major / feistel (median of blocks)", "q0_B_over_P", decision["q0_secondary"]),
        ("Q0 A/A", "q0_aa_B_over_Baa", "pass" if c["q0_aa"] else "FAIL"),
        ("Q0 planted", "q0_planted_B_over_H", "pass" if c["q0_planted"] else "FAIL"),
        ("Held-out 384 (section 23): left-major / feistel, online", "heldout_B_over_P", decision["heldout_secondary"]),
        ("Held-out: ratio of geometric means, online", "heldout_geomean_B_over_P", ""),
        ("Held-out: section 23, probes", "heldout_probes_B_over_P", ""),
        ("Tuned rho / IC left-major, Q0", "rho_gap_q0_rT_over_B", ""),
        ("Tuned rho / IC feistel, Q0", "rho_gap_q0_rT_over_P", ""),
        ("Tuned rho / IC left-major, fresh (section 23)", "rho_gap_fresh_rT_over_B", ""),
        ("Tuned rho / IC feistel, fresh (section 23)", "rho_gap_fresh_rT_over_P", ""),
        ("Tuned rho / IC left-major, fresh (geometric means)", "rho_gap_fresh_geomean_rT_over_B", ""),
        ("Tuned rho / IC feistel, fresh (geometric means)", "rho_gap_fresh_geomean_rT_over_P", ""),
    ]
    for label, key, reading in rows:
        lines.append("| %s | %s | %s |" % (label, fmt(s.get(key), 4), reading))
    lines.append("")
    for panel, arms in (("fresh", s.get("fresh_arms", {})), ("held-out", s.get("heldout_arms", {}))):
        for arm, summary in arms.items():
            p = summary.get("probes")
            if p:
                lines.append("- %s %s: probes mean/law %.3f [%.3f, %.3f], CV %.2f, geomean probes %.0f; online geomean %.1f ms" %
                             (panel, arm, p["mean_over_law"], p["mean_over_law_ci95"][0], p["mean_over_law_ci95"][1],
                              p["cv"], p["geomean"], summary["online_ms"]["geomean"]))
    lines.append("")
    lines.append("Primary verdict (16 fresh points): **%s**; held-out secondary: **%s**; Q0 secondary: %s; ratchet: %s." %
                 (decision["online_fresh_primary"], decision["heldout_secondary"], decision["q0_secondary"], decision["ratchet"]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="panel directory with runs.jsonl")
    parser.add_argument("--correctness-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    schedule = json.loads((HERE / "schedule.json").read_text())
    runs, problems, missing = load(args.receipt, schedule, protocol, args.correctness_only)
    checks, detail = correctness(runs, protocol)
    checks["schedule_complete_and_matching"] = not problems
    if args.correctness_only:
        out = {"problems": problems, "rows": len(runs), "checks": checks, "detail": detail,
               "invalid_rows": [{"serial": r["serial"], "arm": r["arm"], "issues": r["issues"]}
                                for r in runs if r["status"] == "invalid"]}
        (args.receipt / "correctness.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"checks": checks, "problems": problems}, sort_keys=True))
        return
    stats, decision = analyse(runs, protocol, checks)
    contention = [{"serial": r["serial"], "arm": r["arm"], "flags": r["contention"]} for r in runs if r.get("contention")]
    result = {"kind": protocol["kind"], "problems": problems, "checks": checks, "identity": detail,
              "statistics": stats, "decision": decision, "contention_flags": contention,
              "rows": [{k: r.get(k) for k in ("serial", "segment", "arm", "point_id", "seed", "slice", "status",
                                               "issues", "online_ms", "pdp_ms", "ops", "scalar", "process_wall_ms")}
                       for r in runs],
              "heldout_targets": [{"serial": r["serial"], "arm": r["arm"], "targets": r.get("targets")}
                                  for r in runs if r["kind"] == "ic_multi"]}
    (args.receipt / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (args.receipt / "result_table.md").write_text(table_md(stats, decision))
    print(json.dumps({"decision": decision, "checks": checks}, sort_keys=True))


if __name__ == "__main__":
    main()
