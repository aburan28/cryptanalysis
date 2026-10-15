#!/usr/bin/env python3
"""Audit a receipt of the n=83 lift_scan run and apply the frozen decision rule.

1. loads `runs.jsonl` against `schedule.json` (every scheduled serial has one
   row, arm/point/seed match) and decodes every raw producer record;
2. checks the gates of `protocol.json`: exactness (stage 12,000,064 words,
   online every probe word on Q0 and the 16 fresh points), pair identity
   (probes, relation and scalar per point; IC and tuned rho agree; oracle
   replay [d]G = Q; Q0 equals the validation sidecar);
3. computes every frozen statistic with its bootstrap interval;
4. applies the decision rule and writes `result.json` and `result_table.md`
   into the receipt directory.

`--correctness-only` (local smoke) runs steps 1-2 on whatever rows exist and
writes `correctness.json` with no timing values in it.
"""

import argparse
import base64
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"


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


def oracle():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402
    beats = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                       .read_text())["beats"]
    return panel.cached_curve(dict(beats["koblitz.compact_orbit.n83_single_target"]["curve_fixture"]))


def load(receipt, schedule, partial):
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
        item = {"serial": serial, "segment": segment["id"], "panel": segment["panel"],
                "block": segment.get("block"), "arm": run["arm"], "point_id": run["point_id"],
                "point": run["point"], "seed": run["seed"], "status": row["status"],
                "issues": list(row.get("issues", [])), "contention": row.get("contention_flags", [])}
        if row["status"] != "skipped_time_guard":
            raw = raw_record(receipt, row)
            fields = row.get("fields", {})
            item.update({
                "fields": fields,
                "online_ms": float(fields.get("online_ms", "nan")),
                "canon_ms": float(fields["canon_ms"]) if "canon_ms" in fields else None,
                "pdp_ms": float(fields["pdp_ms"]) if "pdp_ms" in fields else None,
                "ops": int(fields["ops"]) if fields.get("ops", "None") not in ("None", "") else None,
                "scalar": fields.get("recovered_scalar"),
                "relation": fields.get("relation"),
                "words_verified": fields.get("words_verified"),
                "pair_certificate": fields.get("pair_certificate"),
                "process_wall_ms": row.get("process_wall_ms"),
                "raw": raw,
            })
            if raw is None:
                item["issues"].append("no raw producer record")
                item["status"] = "invalid"
            elif raw.get("issues"):
                item["issues"] += ["arm: " + issue for issue in raw["issues"]]
                item["status"] = "invalid"
        runs.append(item)
    return runs, problems, missing


def correctness(runs, protocol):
    checks, detail = {}, {}
    executed = [r for r in runs if r["status"] != "skipped_time_guard"]
    checks["all_executed_rows_valid"] = all(r["status"] == "valid" for r in executed)
    stage_v = [r for r in executed if r["arm"] == "sV"]
    checks["stage_exactness_12000064_words"] = (bool(stage_v) and all(
        r["status"] == "valid" and r["words_verified"] == str(protocol["stage"]["verify_words"]) for r in stage_v))
    online_v = [r for r in executed if r["arm"] == "qV"]
    checks["online_exactness_every_probe_word"] = (bool(online_v) and all(
        r["status"] == "valid" and r["words_verified"] == str(r["ops"]) for r in online_v))
    detail["online_verified_words"] = {r["point_id"]: r["words_verified"] for r in online_v}
    stage_rows = [r for r in executed if r["panel"] in ("S", "X") and r["arm"].startswith("s")]
    checks["stage_pair_certificate_frozen"] = all(
        r["pair_certificate"] == protocol["stage"]["frozen_pair_certificate"] for r in stage_rows)
    by_point = {}
    for r in executed:
        if r["point_id"] != "e1":
            by_point.setdefault(r["point_id"], []).append(r)
    probes, relations, scalars, replays = {}, {}, {}, {}
    curve = oracle()
    fixture = json.loads((SNAPSHOT / "experiments/koblitz-single-target-n83-20261006/frozen/fixture.json").read_text())
    for point_id, items in sorted(by_point.items()):
        ic_items = [r for r in items if protocol["arms"][r["arm"]]["kind"] == "ic"]
        probes[point_id] = sorted({r["ops"] for r in ic_items})
        relations[point_id] = sorted({r["relation"] for r in ic_items})
        scalars[point_id] = sorted({r["scalar"] for r in items if r["scalar"] not in (None, "None")})
        if len(scalars[point_id]) == 1:
            q = curve.decode([int(v) for v in items[0]["point"]])
            replays[point_id] = curve.mul(curve.g, int(scalars[point_id][0])) == q
        else:
            replays[point_id] = False
    checks["ic_probes_identical_per_point"] = all(len(v) == 1 for v in probes.values())
    checks["ic_relation_identical_per_point"] = all(len(v) == 1 for v in relations.values())
    checks["one_scalar_per_point_ic_and_rho"] = all(len(v) == 1 for v in scalars.values())
    checks["oracle_replay_every_point"] = bool(replays) and all(replays.values())
    checks["q0_equals_validation_sidecar"] = (scalars.get("q0") == [fixture["fixture_scalar_validation_only"]]
                                              if "q0" in scalars else None)
    detail.update({"probes": probes, "scalars": scalars, "replays": replays,
                   "relations_per_point": {k: len(v) for k, v in relations.items()}})
    return checks, detail


def paired(runs, panel, num, den, key="online_ms", unit="block"):
    """Per-unit (num, den) pairs from complete, valid units."""
    units = {}
    for r in runs:
        if r["panel"] == panel and r["status"] == "valid" and r["arm"] in (num, den):
            units.setdefault(r[unit], {})[r["arm"]] = r[key]
    return [(v[num], v[den]) for _, v in sorted(units.items()) if num in v and den in v]


def ratio_stat(pairs, seed, estimator="median"):
    if not pairs:
        return None
    if estimator == "median":
        ratios = [a / b for a, b in pairs]
        return {"estimate": median(ratios), "ci95": boot(ratios, median, seed), "units": len(ratios),
                "per_unit": ratios, "estimator": "median of per-unit ratios"}
    return {"estimate": ratio_of_means(pairs), "ci95": boot(pairs, ratio_of_means, seed), "units": len(pairs),
            "per_unit": [a / b for a, b in pairs], "estimator": "ratio of means (section 23)"}


def classify(stat):
    if stat is None:
        return "invalid"
    lo, hi = stat["ci95"]
    return "improvement" if lo > 1 else "regression" if hi < 1 else "not_separated"


def aa_pass(stat):
    return stat is not None and 0.97 <= stat["ci95"][0] and stat["ci95"][1] <= 1.03


def planted_pass(stat):
    return stat is not None and stat["ci95"][0] > 1


def analyse(runs, protocol, checks):
    d = protocol["design"]
    s = {}
    # Stage level.
    s["stage_primary_canon_B_over_A"] = ratio_stat(paired(runs, "S", "sB", "sA", "canon_ms"), 20261011)
    s["stage_secondary_target_stage_B_over_A"] = ratio_stat(paired(runs, "S", "sB", "sA"), 20261012)
    s["stage_aa_canon"] = ratio_stat(paired(runs, "S", "sB", "sBaa", "canon_ms"), 20261013)
    s["stage_aa_target_stage"] = ratio_stat(paired(runs, "S", "sB", "sBaa"), 20261014)
    s["stage_planted_canon_x2_over_B"] = ratio_stat(paired(runs, "S", "sBx2", "sB", "canon_ms"), 20261015)
    # Online level, Q0.
    s["online_q0_primary_full_over_lift"] = ratio_stat(paired(runs, "Q", "qF", "qL"), 20261016)
    s["online_q0_gap_over_lift"] = ratio_stat(paired(runs, "Q", "qG", "qL"), 20261017)
    s["online_q0_full_over_gap"] = ratio_stat(paired(runs, "Q", "qF", "qG"), 20261018)
    s["online_q0_aa"] = ratio_stat(paired(runs, "Q", "qF", "qFaa"), 20261019)
    s["online_q0_planted_x2_over_full"] = ratio_stat(paired(runs, "Q", "qFx2", "qF"), 20261020)
    # Online level, fresh points (units are points).
    fresh = paired(runs, "F", "fF", "fL", unit="point_id")
    s["online_fresh_primary_full_over_lift"] = ratio_stat(fresh, 2026101400, "means")
    s["online_fresh_secondary_median"] = ratio_stat(fresh, 2026101401)
    # Where canonicalization sits: marginal cost of one full scan per probe.
    x2 = paired(runs, "Q", "qFx2", "qF")
    if x2:
        shares = [(a - b) / b for a, b in x2]
        s["canonicalization_share_of_q0_interval"] = {"estimate": median(shares), "ci95": boot(shares, median, 20261021),
                                                      "units": len(shares), "per_unit": shares}
    saving = paired(runs, "Q", "qF", "qL")
    if saving:
        fractions = [(a - b) / a for a, b in saving]
        s["realized_saving_fraction_q0"] = {"estimate": median(fractions), "per_unit": fractions}
    q_full = [r for r in runs if r["panel"] == "Q" and r["arm"] == "qF" and r["status"] == "valid"]
    if q_full:
        s["q0_full_pdp_share"] = median([r["pdp_ms"] / r["online_ms"] for r in q_full])
        probes = q_full[0]["ops"]
        s["q0_probes"] = probes
        if x2:
            s["q0_full_scan_ns_per_probe_marginal"] = median([(a - b) * 1e6 / probes for a, b in x2])
        s["q0_ns_per_probe"] = {arm: median([r["online_ms"] * 1e6 / r["ops"] for r in runs
                                             if r["panel"] == "Q" and r["arm"] == arm and r["status"] == "valid"])
                                for arm in d["q0_ic_arms"] if any(r["arm"] == arm and r["panel"] == "Q" for r in runs)}
    # Tuned-rho gap on the same points.
    s["rho_gap_q0_rT_over_full"] = ratio_stat(paired(runs, "Q", "rT", "qF"), 20261022)
    s["rho_gap_q0_rT_over_lift"] = ratio_stat(paired(runs, "Q", "rT", "qL"), 20261023)
    s["rho_gap_q0_means_rT_over_full"] = ratio_stat(paired(runs, "Q", "rT", "qF"), 20261022, "means")
    s["rho_gap_q0_means_rT_over_lift"] = ratio_stat(paired(runs, "Q", "rT", "qL"), 20261023, "means")
    s["rho_gap_fresh_rT_over_full"] = ratio_stat(paired(runs, "F", "rT", "fF", unit="point_id"), 2026101402, "means")
    s["rho_gap_fresh_rT_over_lift"] = ratio_stat(paired(runs, "F", "rT", "fL", unit="point_id"), 2026101403, "means")
    # S.
    rho = [r for r in runs if r["arm"] == "rT" and r["status"] == "valid" and r["ops"]]
    sqrt_r = protocol["online"]["sqrt_r"]
    if rho:
        ms_per_step = median([r["online_ms"] / r["ops"] for r in rho])
        s["rho_ms_per_step"] = ms_per_step

        def s_rho(ms):
            return ms / ms_per_step / sqrt_r

        table = {}
        for label, panel, arm, agg in (("q0_full", "Q", "qF", median), ("q0_lift", "Q", "qL", median),
                                       ("fresh_full", "F", "fF", statistics.mean), ("fresh_lift", "F", "fL", statistics.mean)):
            values = [r["online_ms"] for r in runs if r["panel"] == panel and r["arm"] == arm and r["status"] == "valid"]
            if values:
                ops = [r["ops"] for r in runs if r["panel"] == panel and r["arm"] == arm and r["status"] == "valid"]
                table[label] = {"online_ms": agg(values), "S_rho": s_rho(agg(values)),
                                "S_probe": agg(ops) / sqrt_r}
        rho_values = {"q0": median([r["online_ms"] for r in rho if r["panel"] == "Q"] or [float("nan")]),
                      "fresh": statistics.mean([r["online_ms"] for r in rho if r["panel"] == "F"] or [float("nan")])}
        table["rho_tuned"] = {"q0_online_ms_median": rho_values["q0"], "fresh_online_ms_mean": rho_values["fresh"],
                              "q0_S_rho": s_rho(rho_values["q0"]), "fresh_S_rho": s_rho(rho_values["fresh"]),
                              "steps_over_sqrt_r_q0": median([r["ops"] for r in rho if r["panel"] == "Q"] or [0]) / sqrt_r}
        for where in ("q0", "fresh"):
            if where + "_full" in table and where + "_lift" in table:
                table[where + "_delta_S_rho"] = table[where + "_lift"]["S_rho"] - table[where + "_full"]["S_rho"]
                table[where + "_delta_S_probe"] = table[where + "_lift"]["S_probe"] - table[where + "_full"]["S_probe"]
        s["S"] = table
    # Decisions.
    # Exactness and identity gate the verdicts; a single invalid row only
    # removes its unit (and an incomplete level is invalid).
    exact_ok = all(v is not False for k, v in checks.items() if k != "all_executed_rows_valid")
    stage_controls = aa_pass(s["stage_aa_canon"]) and aa_pass(s["stage_aa_target_stage"]) and \
        planted_pass(s["stage_planted_canon_x2_over_B"])
    online_controls = aa_pass(s["online_q0_aa"]) and planted_pass(s["online_q0_planted_x2_over_full"])
    complete_stage = s["stage_primary_canon_B_over_A"] and s["stage_primary_canon_B_over_A"]["units"] == d["stage_blocks"]
    complete_q0 = s["online_q0_primary_full_over_lift"] and s["online_q0_primary_full_over_lift"]["units"] == d["q0_blocks"]
    complete_fresh = s["online_fresh_primary_full_over_lift"] and s["online_fresh_primary_full_over_lift"]["units"] == d["fresh_points"]
    decision = {
        "controls": {"stage_aa_canon": aa_pass(s["stage_aa_canon"]), "stage_aa_target_stage": aa_pass(s["stage_aa_target_stage"]),
                     "stage_planted": planted_pass(s["stage_planted_canon_x2_over_B"]),
                     "online_aa": aa_pass(s["online_q0_aa"]), "online_planted": planted_pass(s["online_q0_planted_x2_over_full"])},
        "exactness_and_identity_ok": exact_ok,
    }
    decision["stage"] = (classify(s["stage_primary_canon_B_over_A"])
                         if exact_ok and stage_controls and complete_stage else "invalid")
    decision["stage_secondary_target_stage"] = classify(s["stage_secondary_target_stage_B_over_A"])
    if exact_ok and online_controls and complete_q0 and complete_fresh:
        decision["online_q0"] = classify(s["online_q0_primary_full_over_lift"])
        decision["online_fresh"] = classify(s["online_fresh_primary_full_over_lift"])
        decision["online"] = ("improvement" if decision["online_q0"] == decision["online_fresh"] == "improvement"
                              else "regression" if "regression" in (decision["online_q0"], decision["online_fresh"])
                              else "not_separated")
    else:
        decision["online_q0"] = decision["online_fresh"] = decision["online"] = "invalid"
    decision["ratchet"] = ("new one-target baseline: lift_scan pipeline" if decision["online"] == "improvement"
                           else "stage improvement only" if decision["stage"] == "improvement" else "no new baseline")
    return s, decision


def fmt(stat, digits=3):
    if not stat:
        return "n/a"
    return "%.*f [%.*f, %.*f] (n=%d)" % (digits, stat["estimate"], digits, stat["ci95"][0], digits,
                                          stat["ci95"][1], stat["units"])


def table_md(s, decision):
    lines = ["| Statistic | Estimate [95%] | Reading |", "| --- | --- | --- |"]
    rows = [
        ("Stage primary: canonicalization phase, variant B / lift_scan", "stage_primary_canon_B_over_A", decision["stage"]),
        ("Stage secondary: target stage, B / lift_scan", "stage_secondary_target_stage_B_over_A", decision["stage_secondary_target_stage"]),
        ("Stage A/A: canonicalization phase, B / B", "stage_aa_canon", "pass" if decision["controls"]["stage_aa_canon"] else "FAIL"),
        ("Stage A/A: target stage, B / B", "stage_aa_target_stage", "pass" if decision["controls"]["stage_aa_target_stage"] else "FAIL"),
        ("Stage planted: canonicalization phase, B+B / B", "stage_planted_canon_x2_over_B", "pass" if decision["controls"]["stage_planted"] else "FAIL"),
        ("Online Q0 primary: full / lift_scan", "online_q0_primary_full_over_lift", decision["online_q0"]),
        ("Online fresh primary (section 23): full / lift_scan", "online_fresh_primary_full_over_lift", decision["online_fresh"]),
        ("Online fresh secondary: median per-point ratio", "online_fresh_secondary_median", ""),
        ("Online Q0 secondary: variant B / lift_scan", "online_q0_gap_over_lift", ""),
        ("Online Q0 secondary: full / variant B", "online_q0_full_over_gap", ""),
        ("Online A/A: full / full", "online_q0_aa", "pass" if decision["controls"]["online_aa"] else "FAIL"),
        ("Online planted: full+full / full", "online_q0_planted_x2_over_full", "pass" if decision["controls"]["online_planted"] else "FAIL"),
        ("Canonicalization share of the Q0 interval (one full scan per probe)", "canonicalization_share_of_q0_interval", "derived"),
        ("Tuned rho / IC full, Q0 (median of blocks)", "rho_gap_q0_rT_over_full", ""),
        ("Tuned rho / IC lift_scan, Q0 (median of blocks)", "rho_gap_q0_rT_over_lift", ""),
        ("Tuned rho / IC full, Q0 (ratio of means)", "rho_gap_q0_means_rT_over_full", ""),
        ("Tuned rho / IC lift_scan, Q0 (ratio of means)", "rho_gap_q0_means_rT_over_lift", ""),
        ("Tuned rho / IC full, fresh (section 23)", "rho_gap_fresh_rT_over_full", ""),
        ("Tuned rho / IC lift_scan, fresh (section 23)", "rho_gap_fresh_rT_over_lift", ""),
    ]
    for label, key, reading in rows:
        lines.append("| %s | %s | %s |" % (label, fmt(s.get(key), 4), reading))
    lines.append("")
    lines.append("Online verdict: **%s**; stage verdict: **%s**; ratchet: %s." %
                 (decision["online"], decision["stage"], decision["ratchet"]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="panel directory with runs.jsonl")
    parser.add_argument("--correctness-only", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    schedule = json.loads((HERE / "schedule.json").read_text())
    runs, problems, missing = load(args.receipt, schedule, args.correctness_only)
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
              "rows": [{k: r.get(k) for k in ("serial", "segment", "arm", "point_id", "seed", "status", "issues",
                                               "online_ms", "canon_ms", "pdp_ms", "ops", "scalar", "process_wall_ms")}
                       for r in runs]}
    (args.receipt / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (args.receipt / "result_table.md").write_text(table_md(stats, decision))
    print(json.dumps({"decision": decision, "checks": checks}, sort_keys=True))


if __name__ == "__main__":
    main()
