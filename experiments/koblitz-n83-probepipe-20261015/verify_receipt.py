#!/usr/bin/env python3
"""Audit a receipt of the n=83 probe-pipeline run and apply the frozen decision rule.

1. loads `runs.jsonl` against `schedule.json` (every scheduled serial has one
   row, arm/point/seed/slice match) and decodes every raw producer record;
2. checks the gates of `protocol.json`:
   * primary panel: on every point, the four IC arms (`pC`, `pP`, `pPaa`,
     `pX`) have identical probes and relation, one scalar across them and
     the tuned rho, and every scalar replays as [d]G = Q in the pinned
     oracle;
   * Q0 + B's 16 fresh points: both arms reproduce the probes and relation
     archived for the Feistel order (`inputs/archived_identities.json`), the
     scalars equal the archived ones and replay, and Q0 equals the
     validation sidecar;
3. computes every frozen statistic with its bootstrap interval;
4. applies the decision rule and writes `result.json` and `result_table.md`
   into the receipt directory.

`--correctness-only` (local smoke) runs steps 1-2 on whatever rows exist and
writes `correctness.json` with no timing values in it. Adapted from
`claude/n83-combined`'s `verify_receipt.py`.
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
sys.path.insert(0, str(HERE))
from panels import panel_points  # noqa: E402

PRIMARY_ARMS = ("pC", "pP", "pPaa", "pX")
OLD_ARMS = ("oC", "oP")


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


def geomean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


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
    panels = {name: panel_points(name) for name in ("primary", "old17")}
    runs = []
    for serial, row in sorted(by_serial.items()):
        segment, run = scheduled[serial]
        if (row["arm"] != run["arm"] or row["point_id"] != run["point_id"] or row["seed"] != run["seed"]
                or row.get("slice") != run.get("slice")):
            problems.append("row %d does not match the schedule" % serial)
        arm = protocol["arms"][run["arm"]]
        item = {"serial": serial, "segment": segment["id"], "panel": segment["panel"],
                "block": segment.get("block"), "arm": run["arm"], "kind": arm["kind"],
                "point_id": run["point_id"], "point": run["point"], "seed": run["seed"],
                "slice": run.get("slice"), "status": row["status"],
                "issues": list(row.get("issues", [])), "contention": row.get("contention_flags", [])}
        if row["status"] != "skipped_time_guard":
            raw = raw_record(receipt, row)
            fields = row.get("fields", {})
            item.update({
                "fields": fields,
                "online_ms": float(fields.get("online_ms", "nan")),
                "ops": int(fields["ops"]) if fields.get("ops", "None") not in ("None", "") else None,
                "scalar": fields.get("recovered_scalar"),
                "process_wall_ms": row.get("process_wall_ms"),
                "setup_ms": float(fields["setup_ms"]) if "setup_ms" in fields else None,
            })
            if raw is None:
                item["issues"].append("no raw producer record")
                item["status"] = "invalid"
            elif raw.get("issues"):
                item["issues"] += ["arm: " + issue for issue in raw["issues"]]
                item["status"] = "invalid"
            if arm["kind"] == "ic_multi" and raw is not None:
                lo, hi = (int(v) for v in run["slice"].split(":"))
                units = panels[arm["panel_file"]][lo:hi]
                item["targets"] = [{"unit": unit, "point": [str(v) for v in point],
                                    "online_ms": float(r.get("online_ms") or "nan"),
                                    "probes": r.get("probes"), "scalar": str(r.get("recovered_scalar")),
                                    "relation": r.get("point_indices")}
                                   for (unit, point), r in zip(units, raw["records"][:-1])]
        runs.append(item)
    return runs, problems, missing


def per_unit(runs, panel):
    """unit -> arm -> target record, from valid ic_multi rows of a panel."""
    out = {}
    for r in runs:
        if r["panel"] == panel and r["kind"] == "ic_multi" and r["status"] == "valid":
            for t in r.get("targets", []):
                out.setdefault(t["unit"], {})[r["arm"]] = t
    return out


def correctness(runs, protocol):
    checks, detail = {}, {}
    executed = [r for r in runs if r["status"] != "skipped_time_guard"]
    checks["all_executed_rows_valid"] = all(r["status"] == "valid" for r in executed)
    curve = oracle()
    fixture = json.loads((SNAPSHOT / "experiments/koblitz-single-target-n83-20261006/frozen/fixture.json").read_text())

    def same(a, b):
        return a["probes"] == b["probes"] and a["relation"] == b["relation"]

    def replay(point, scalar):
        return curve.mul(curve.g, int(scalar)) == curve.decode([int(v) for v in point])

    primary = per_unit(runs, "P")
    rho = {r["point_id"]: r for r in executed if r["arm"] == "rT" and r["status"] == "valid"}
    group_ok, scalar_ok, replay_ok = {}, {}, {}
    for unit, by_arm in sorted(primary.items()):
        arms = [by_arm[a] for a in PRIMARY_ARMS if a in by_arm]
        group_ok[unit] = all(same(arms[0], t) for t in arms[1:])
        scalars = {t["scalar"] for t in by_arm.values()}
        if unit in rho:
            scalars.add(str(rho[unit]["scalar"]))
        scalar_ok[unit] = len(scalars) == 1 and "None" not in scalars
        point = next(iter(by_arm.values()))["point"]
        replay_ok[unit] = scalar_ok[unit] and replay(point, next(iter(scalars)))
    checks["primary_ic_arms_identical_probes_and_relation"] = all(group_ok.values()) if group_ok else None
    checks["primary_one_scalar_ic_and_rho"] = all(scalar_ok.values()) if scalar_ok else None
    checks["primary_oracle_replay"] = all(replay_ok.values()) if replay_ok else None
    complete = [u for u, by_arm in primary.items() if all(a in by_arm for a in PRIMARY_ARMS) and u in rho]
    detail["primary_units_complete"] = len(complete)
    detail["primary_units_seen"] = len(primary)
    archived = json.loads((HERE / "inputs" / "archived_identities.json").read_text())["old17"]
    ok, scal, rep = {}, {}, {}
    for r in executed:
        if r["panel"] != "O" or r["kind"] != "ic_multi" or r["status"] != "valid":
            continue
        order = protocol["arms"][r["arm"]]["order"]
        for t in r.get("targets", []):
            ref = archived[t["unit"]]
            good = t["probes"] == ref[order]["probes"] and t["relation"] == ref[order]["relation"]
            ok[t["unit"]] = ok.get(t["unit"], True) and good
            scal[t["unit"]] = scal.get(t["unit"], True) and t["scalar"] == ref["scalar"]
            if t["unit"] not in rep:
                rep[t["unit"]] = replay(t["point"], ref["scalar"])
    checks["old17_reproduces_archived_feistel_probes_and_relation"] = all(ok.values()) if ok else None
    checks["old17_one_scalar_equal_to_archived"] = all(scal.values()) if scal else None
    checks["old17_oracle_replay"] = all(rep.values()) if rep else None
    detail["old17_units_seen"] = len(ok)
    if "q0" in scal:
        checks["q0_equals_validation_sidecar"] = (
            archived["q0"]["scalar"] == str(fixture["fixture_scalar_validation_only"]) and scal["q0"])
    detail["primary_group_identity_failures"] = sorted(u for u, v in group_ok.items() if not v)
    detail["primary_scalar_failures"] = sorted(u for u, v in scalar_ok.items() if not v)
    return checks, detail


# ---- statistics -----------------------------------------------------------

def ratio_of_means(pairs):
    return sum(a for a, _ in pairs) / sum(b for _, b in pairs)


def ratio_of_geomeans(log_pairs):
    return math.exp(sum(a - b for a, b in log_pairs) / len(log_pairs))


def stat(units, function, seed, label):
    if not units:
        return None
    return {"estimate": function(units), "ci95": boot(units, function, seed), "units": len(units),
            "estimator": label}


def pair_stats(rows, num, den, seed, key="online_ms"):
    pairs = [(r[num][key], r[den][key]) for r in rows]
    logs = [(math.log(a), math.log(b)) for a, b in pairs]
    return {"means": stat(pairs, ratio_of_means, seed, "ratio of means (section 23)"),
            "geomeans": stat(logs, ratio_of_geomeans, seed + 1, "ratio of geometric means (paired)")}


def arm_summary(values, seed, law=None):
    if not values:
        return None
    out = {"n": len(values), "geomean": geomean(values), "geomean_ci95": boot(values, geomean, seed),
           "mean": statistics.mean(values), "mean_ci95": boot(values, statistics.mean, seed + 1),
           "cv": cv(values)}
    if law:
        out["mean_over_law"] = out["mean"] / law
        out["mean_over_law_ci95"] = [v / law for v in out["mean_ci95"]]
    return out


def classify(stat_):
    if stat_ is None:
        return "invalid"
    lo, hi = stat_["ci95"]
    return "improvement" if lo > 1 else "regression" if hi < 1 else "not_separated"


def classify_both(means, geomeans):
    if means is None or geomeans is None:
        return "invalid"
    if means["ci95"][0] > 1 and geomeans["ci95"][0] > 1:
        return "improvement"
    if means["ci95"][1] < 1 and geomeans["ci95"][1] < 1:
        return "regression"
    return "not_separated"


def aa_pass(stat_):
    return stat_ is not None and 0.97 <= stat_["ci95"][0] and stat_["ci95"][1] <= 1.03


def panel_rows(runs, panel, arms):
    units = per_unit(runs, panel)
    return [dict(by_arm, unit=unit) for unit, by_arm in sorted(units.items()) if all(a in by_arm for a in arms)]


def analyse(runs, protocol, checks, detail):
    d, online = protocol["design"], protocol["online"]
    law, sqrt_r = online["law_probes"], online["sqrt_r"]
    s = {}
    prim = panel_rows(runs, "P", PRIMARY_ARMS)
    s["primary_units"] = len(prim)
    primary = pair_stats(prim, "pC", "pP", 2026103500)
    s["primary_R_means"], s["primary_R_geomeans"] = primary["means"], primary["geomeans"]
    s["primary_probes_C_over_P"] = pair_stats(prim, "pC", "pP", 2026103502, "probes")["means"]
    s["primary_aa_P_over_Paa"] = pair_stats(prim, "pP", "pPaa", 2026103530)["means"]
    s["primary_planted_X_over_P"] = pair_stats(prim, "pX", "pP", 2026103532)["means"]
    s["primary_arms"] = {arm: {"online_ms": arm_summary([r[arm]["online_ms"] for r in prim], 2026103540 + 10 * i),
                               "probes": arm_summary([float(r[arm]["probes"]) for r in prim], 2026103545 + 10 * i, law),
                               "ns_per_probe_mean": (sum(r[arm]["online_ms"] for r in prim) * 1e6 /
                                                     sum(r[arm]["probes"] for r in prim)) if prim else None}
                         for i, arm in enumerate(PRIMARY_ARMS)}
    by_slice = {}
    for r in prim:
        by_slice.setdefault(int(r["unit"][1:]) // d["slice"], []).append((r["pC"]["online_ms"], r["pP"]["online_ms"]))
    clusters = [tuple(sum(t[i] for t in v) for i in range(2)) for _, v in sorted(by_slice.items())]
    s["primary_R_means_slice_bootstrap"] = stat(clusters, ratio_of_means, 2026103550,
                                                "R_m with a bootstrap over 64-point slices (sensitivity)")
    s["primary_R_means_per_slice"] = [a / b for a, b in clusters]
    rho = {r["point_id"]: r for r in runs if r["arm"] == "rT" and r["status"] == "valid" and r.get("ops")}
    prim_rho = [dict(r, rT={"online_ms": rho[r["unit"]]["online_ms"], "probes": rho[r["unit"]]["ops"]})
                for r in prim if r["unit"] in rho]
    for arm, seed in (("pC", 2026103560), ("pP", 2026103562)):
        s["rho_gap_rT_over_" + arm] = pair_stats(prim_rho, "rT", arm, seed)
    s["rho_arm"] = arm_summary([r["rT"]["online_ms"] for r in prim_rho], 2026103570)
    if rho:
        ms_per_step = statistics.median([r["online_ms"] / r["ops"] for r in rho.values()])
        table = {"rho_ms_per_step": ms_per_step}
        for arm in ("pC", "pP"):
            times = [r[arm]["online_ms"] for r in prim]
            probes = [r[arm]["probes"] for r in prim]
            if times:
                table[arm] = {"online_ms_mean": statistics.mean(times),
                              "S_rho": statistics.mean(times) / ms_per_step / sqrt_r,
                              "S_probe": statistics.mean(probes) / sqrt_r}
        if prim_rho:
            table["rT"] = {"online_ms_mean": statistics.mean([r["rT"]["online_ms"] for r in prim_rho]),
                           "steps_over_sqrt_r": statistics.mean([r["rT"]["probes"] for r in prim_rho]) / sqrt_r}
        if "pC" in table and "pP" in table:
            table["delta_S_rho_P_minus_C"] = table["pP"]["S_rho"] - table["pC"]["S_rho"]
        s["S"] = table
    o17 = {}
    for r in runs:
        if r["panel"] == "O" and r["kind"] == "ic_multi" and r["status"] == "valid":
            for t in r.get("targets", []):
                o17.setdefault(t["unit"], {})[r["arm"]] = t
    fresh = [dict(v, unit=u) for u, v in sorted(o17.items()) if u != "q0" and all(a in v for a in OLD_ARMS)]
    s["old_fresh16_C_over_P"] = pair_stats(fresh, "oC", "oP", 2026103610)
    s["old_q0"] = {arm: o17["q0"][arm]["online_ms"] for arm in OLD_ARMS if arm in o17.get("q0", {})}
    exact_ok = all(v is not False for k, v in checks.items() if k != "all_executed_rows_valid")
    controls = {"aa": aa_pass(s["primary_aa_P_over_Paa"]),
                "planted": s["primary_planted_X_over_P"] is not None and s["primary_planted_X_over_P"]["ci95"][0] > 1}
    complete = s["primary_units"] == d["primary_points"] and detail.get("primary_units_complete") == d["primary_points"]
    decision = {"controls": controls, "exactness_and_identity_ok": exact_ok, "primary_complete": complete}
    decision["primary"] = (classify(s["primary_R_means"]) if exact_ok and all(controls.values()) and complete
                           else "invalid")
    decision["primary_geomeans_reported"] = classify(s["primary_R_geomeans"])
    decision["ratchet"] = ("new n=83 one-target baseline: lift_scan + Feistel order + software-pipelined, "
                           "prefetched root-table probes" if decision["primary"] == "improvement"
                           else "no new baseline")
    return s, decision


def fmt(stat_, digits=4):
    if not stat_:
        return "n/a"
    return "%.*f [%.*f, %.*f] (n=%d)" % (digits, stat_["estimate"], digits, stat_["ci95"][0], digits,
                                          stat_["ci95"][1], stat_["units"])


def table_md(s, decision):
    c = decision["controls"]
    lines = ["| Statistic | Estimate [95%] | Reading |", "| --- | --- | --- |"]
    rows = [
        ("Primary R_m: combined / combined+pipeline, ratio of means", s.get("primary_R_means"), decision["primary"]),
        ("R_g: ratio of geometric means (reported)", s.get("primary_R_geomeans"),
         decision["primary_geomeans_reported"]),
        ("R_m, slice bootstrap (sensitivity)", s.get("primary_R_means_slice_bootstrap"), ""),
        ("Probes: combined / pipeline (must be 1)", s.get("primary_probes_C_over_P"), ""),
        ("A/A: pipeline / pipeline", s.get("primary_aa_P_over_Paa"), "pass" if c["aa"] else "FAIL"),
        ("Planted: pipeline+full scan / pipeline", s.get("primary_planted_X_over_P"),
         "pass" if c["planted"] else "FAIL"),
        ("Tuned rho / pipeline (means)", s["rho_gap_rT_over_pP"]["means"], ""),
        ("Tuned rho / pipeline (geomeans)", s["rho_gap_rT_over_pP"]["geomeans"], ""),
        ("Tuned rho / combined (means)", s["rho_gap_rT_over_pC"]["means"], ""),
        ("Old 16 fresh combined / pipeline (means, secondary)", s["old_fresh16_C_over_P"]["means"], ""),
    ]
    for label, value, reading in rows:
        lines.append("| %s | %s | %s |" % (label, fmt(value), reading))
    lines.append("")
    for arm, summary in s.get("primary_arms", {}).items():
        p = summary.get("probes")
        if p:
            lines.append("- primary %s: online mean %.1f ms, geomean %.1f ms, %.1f ns/probe; probes mean/law %.3f" %
                         (arm, summary["online_ms"]["mean"], summary["online_ms"]["geomean"],
                          summary["ns_per_probe_mean"], p["mean_over_law"]))
    table = s.get("S", {})
    for arm in ("pC", "pP"):
        if arm in table:
            lines.append("- S_rho %s: %.5f (S_probe %.5f)" % (arm, table[arm]["S_rho"], table[arm]["S_probe"]))
    if "delta_S_rho_P_minus_C" in table:
        lines.append("- delta S_rho, pipeline minus combined: %.5f" % table["delta_S_rho_P_minus_C"])
    lines.append("")
    lines.append("Primary verdict (ratio of means): **%s**; ratchet: %s." % (decision["primary"], decision["ratchet"]))
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
    stats, decision = analyse(runs, protocol, checks, detail)
    contention = [{"serial": r["serial"], "arm": r["arm"], "flags": r["contention"]} for r in runs if r.get("contention")]
    result = {"kind": protocol["kind"], "problems": problems, "checks": checks, "identity": detail,
              "statistics": stats, "decision": decision, "contention_flags": contention,
              "rows": [{k: r.get(k) for k in ("serial", "segment", "arm", "point_id", "seed", "slice", "status",
                                               "issues", "online_ms", "ops", "scalar", "process_wall_ms", "setup_ms")}
                       for r in runs],
              "targets": [{"serial": r["serial"], "arm": r["arm"], "segment": r["segment"],
                           "targets": [{k: t[k] for k in ("unit", "online_ms", "probes", "scalar", "relation")}
                                       for t in r.get("targets", [])]}
                          for r in runs if r["kind"] == "ic_multi"]}
    (args.receipt / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (args.receipt / "result_table.md").write_text(table_md(stats, decision))
    print(json.dumps({"decision": decision, "checks": checks}, sort_keys=True))


if __name__ == "__main__":
    main()
