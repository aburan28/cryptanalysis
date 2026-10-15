#!/usr/bin/env python3
"""Audit a reconciliation receipt and apply the frozen statistics and decision rule.

Reads one receipt directory written by `run_schedule.py` (runner_start.json,
runs.jsonl, runs/*.stdout.txt, tables/*.json) and, fail-closed:

1. checks that every scheduled run has exactly one row, decodes each arm's raw
   producer record, and classifies rows (valid, invalid, skipped by the time
   guard, contention-flagged);
2. runs the identity checks of `protocol.json` `controls.identity_checks`:
   one scalar per point, Q0's equal to the validation sidecar (opened only
   here), every scalar replayed as [d]G = Q in the pinned `oracle.py`, walk
   steps identical across rA819/rA770/rA770aa per seed and across blocks,
   IC probes identical across all IC arms per point, every fresh B-producer
   table's 600 logs equal to B's archived table's;
3. computes, per complete Q block, the cells L_A and L_B, the gap G and its
   exact seven-term chain, the A/A and positive controls, the tuned-rho
   contrasts and the deterministic steps x ns/step split, with bootstrap
   intervals over blocks; over the complete fresh points, the rho
   implementation, revision, tuned and seed-family contrasts and B's
   section 23 statistic per rho arm, with bootstrap intervals over points;
4. applies the decision rule and writes `result.json` and `result_table.md`.

`--correctness-only` (local smoke) runs steps 1-2 on whatever rows exist and
writes `correctness.json` with no timing values in it.
"""

import argparse
import base64
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
B_DIR = HERE.parent / "koblitz-single-target-n83-tier1-20261014"
CHAIN = ["rev_rho", "impl_rho", "seed", "boundary", "rev_ic", "prod_ic", "cache"]
A_PUBLISHED_LN = math.log(1 / 1.382330)   # A: IC/strong 1.382330 (geometric mean)
B_PUBLISHED_LN = math.log(1.779)          # B run 38523707244, Panel A median rho/IC


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def raw_record(receipt, row):
    for line in (receipt / row["stdout_file"]).read_text().splitlines():
        if line.startswith("raw_b64="):
            return json.loads(base64.b64decode(line[len("raw_b64="):]))
    return None


def bootstrap(rows, statistic, seed, draws=10000):
    rng = random.Random(seed)
    n = len(rows)
    values = sorted(statistic([rows[rng.randrange(n)] for _ in range(n)]) for _ in range(draws))
    return values


def interval(values, level):
    lo = (1 - level) / 2
    return [values[int(math.floor(lo * (len(values) - 1)))],
            values[int(math.ceil((1 - lo) * (len(values) - 1)))]]


def mean(values):
    return sum(values) / len(values)


def summarize(per_unit, seed, bonferroni):
    """Mean over units with a 95% and a Bonferroni interval from one bootstrap."""
    boot = bootstrap(per_unit, mean, seed)
    return {"mean": mean(per_unit), "ci95": interval(boot, 0.95),
            "ci_bonferroni": interval(boot, 1 - 0.05 / bonferroni), "units": len(per_unit),
            "per_unit": per_unit}


def oracle():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402
    beats = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                       .read_text())["beats"]
    return panel.cached_curve(dict(beats["koblitz.compact_orbit.n83_single_target"]["curve_fixture"]))


def load(receipt, protocol, schedule, partial):
    rows = jsonl(receipt / "runs.jsonl")
    by_serial = {}
    problems = []
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
        item = {"serial": serial, "segment": segment["id"], "block": segment["block"], "panel": segment["panel"],
                "arm": run["arm"], "point_id": run["point_id"], "point": run["point"], "seed": run["seed"],
                "status": row["status"], "issues": list(row.get("issues", [])),
                "contention": row.get("contention_flags", [])}
        if row["status"] != "skipped_time_guard":
            raw = raw_record(receipt, row)
            fields = row.get("fields", {})
            item.update({
                "raw_issues": (raw or {}).get("issues"),
                "scalar": fields.get("recovered_scalar"),
                "ops": int(fields["ops"]) if fields.get("ops", "None") not in ("None", "") else None,
                "online_ms": float(fields.get("online_ms", "nan")),
                "online_A": float(fields.get("online_ms_at_A_boundary", "nan")),
                "online_B": float(fields.get("online_ms_at_B_boundary", "nan")),
                "setup_ms": float(fields.get("setup_ms", "nan")),
                "process_wall_ms": row.get("process_wall_ms"),
                "cpu_ms": (row.get("child_cpu_user_ms") or 0) + (row.get("child_cpu_system_ms") or 0),
                "peak_rss_kb": row.get("child_peak_rss_kb_cumulative"),
                "records": (raw or {}).get("records"),
            })
            if raw is None:
                item["issues"].append("no raw producer record")
                item["status"] = "invalid"
            if item["scalar"] in (None, "None"):
                item["issues"].append("no recovered scalar")
                item["status"] = "invalid"
        runs.append(item)
    return runs, problems, missing


def identity_checks(runs, protocol, receipt):
    checks = {}
    executed = [r for r in runs if r["status"] != "skipped_time_guard"]
    curve = oracle()
    fixture = json.loads((SNAPSHOT / "experiments/koblitz-single-target-n83-20261006/frozen/fixture.json").read_text())
    by_point = {}
    for run in executed:
        by_point.setdefault(run["point_id"], []).append(run)
    scalars, replays = {}, {}
    for point_id, items in sorted(by_point.items()):
        values = {r["scalar"] for r in items if r["scalar"] not in (None, "None")}
        scalars[point_id] = sorted(values)
        if len(values) == 1:
            d = int(next(iter(values)))
            q = curve.decode([int(v) for v in items[0]["point"]])
            replays[point_id] = curve.mul(curve.g, d) == q
        else:
            replays[point_id] = False
    checks["one_scalar_per_point"] = all(len(v) == 1 for v in scalars.values())
    checks["oracle_replay_every_point"] = all(replays.values())
    checks["q0_equals_validation_sidecar"] = (scalars.get("q0") == [fixture["fixture_scalar_validation_only"]]
                                              if "q0" in scalars else None)
    steps = {}
    for run in executed:
        if run["arm"].startswith("r") and run["ops"] is not None:
            family = "adapter" if run["arm"] in ("rA819", "rA770", "rA770aa") else run["arm"]
            steps.setdefault((family, run["point_id"], run["seed"]), set()).add(run["ops"])
    checks["rho_steps_identical_per_seed_point_and_family"] = all(len(v) == 1 for v in steps.values())
    probes = {}
    for run in executed:
        if run["arm"].startswith("i") and run["ops"] is not None:
            probes.setdefault(run["point_id"], set()).add(run["ops"])
    checks["ic_probes_identical_per_point"] = all(len(v) == 1 for v in probes.values())
    sys.path.insert(0, str(HERE))
    import verify_log_table  # noqa: E402
    reference = json.loads((B_DIR / protocol["sources"]["reused_from_B"]["factor_log_table"]).read_text())["logs"]
    tables = []
    for path in sorted((receipt / "tables").glob("*.json")):
        result = verify_log_table.verify(path, HERE / protocol["inputs"]["base"], curve)
        same = json.loads(path.read_text())["logs"] == reference
        tables.append({"file": path.name, "oracle_status": result["status"], "logs_equal_B_archived": same})
    checks["fresh_tables_equal_B_archived_logs"] = all(t["oracle_status"] == "PASS" and t["logs_equal_B_archived"]
                                                       for t in tables) if tables else None
    detail = {"scalars": scalars, "replays": replays,
              "rho_steps": {"%s|%s|%s" % key: sorted(value) for key, value in sorted(steps.items())},
              "ic_probes": {key: sorted(value) for key, value in sorted(probes.items())},
              "tables": tables}
    return checks, detail


def q_panel(runs, protocol, flagged_ok=True):
    q = protocol["panels"]["Q"]
    sa, sb = q["rho_seeds"]["SA"], q["rho_seeds"]["SB"][0]
    blocks = {}
    for run in runs:
        if run["panel"] == "Q":
            blocks.setdefault(run["block"], []).append(run)
    complete = {}
    for block, items in sorted(blocks.items()):
        if (len(items) == q["runs_per_block"] and all(r["status"] == "valid" for r in items) and
                (flagged_ok or not any(r["contention"] for r in items))):
            complete[block] = {(r["arm"], r["seed"]): r for r in items}
    per_block = []
    for block, cell in sorted(complete.items()):
        def t(arm, seed=0, boundary="native"):
            run = cell[(arm, seed)]
            value = {"native": run["online_ms"], "A": run["online_A"], "B": run["online_B"]}[boundary]
            return math.log(value)

        def ms(arm, seeds, boundary="A"):
            return mean([t(arm, s, boundary) for s in seeds])

        rA819, rA770 = ms("rA819", sa), ms("rA770", sa)
        rB_sa, rB_sb = ms("rB770", sa), t("rB770", sb, "A")
        rA770_sb = t("rA770", sb)
        iA819, iA770, iB_f, iB_c = t("iA819f"), t("iA770f"), t("iB770f"), t("iB770c")
        L_A = rA819 - iA819
        L_B = t("rB770", sb, "B") - iB_c
        terms = {
            "rev_rho": rA770 - rA819,
            "impl_rho": 0.5 * ((rB_sa - rA770) + (rB_sb - rA770_sb)),
            "seed": 0.5 * ((rA770_sb - rA770) + (rB_sb - rB_sa)),
            "boundary": t("rB770", sb, "B") - rB_sb,
            "rev_ic": -(iA770 - iA819),
            "prod_ic": -(iB_f - iA770),
            "cache": -(iB_c - iB_f),
        }
        steps = {arm: {s: cell[(arm, s)]["ops"] for s in sa + [sb]} for arm in ("rA770", "rB770", "rT770")}
        lns = lambda arm, seeds: mean([math.log(steps[arm][s]) for s in seeds])  # noqa: E731
        per_block.append({
            "block": block, "L_A": L_A, "L_B": L_B, "G": L_B - L_A, "terms": terms,
            "chain_residual": (L_B - L_A) - sum(terms.values()),
            "impl_order_seedA_first": {"impl": rB_sa - rA770, "seed": rB_sb - rB_sa},
            "impl_order_seedB_first": {"seed": rA770_sb - rA770, "impl": rB_sb - rA770_sb},
            "tuned": ms("rT770", sa) - rA770,
            "L_T_with_A_ic": ms("rT770", sa) - iA819,
            "L_T_with_B_ic": t("rT770", sb) - iB_c,
            "aa_rho": mean([t("rA770aa", s) - t("rA770", s) for s in sa + [sb]]),
            "aa_ic": t("iB770caa") - iB_c,
            "positive_control": t("rA770", 202610064) - t("rA770", 202610063),
            "positive_control_expected": math.log(steps["rA770"][202610064] / steps["rA770"][202610063]),
            "split": {
                "impl_steps_SA": lns("rB770", sa) - lns("rA770", sa),
                "impl_ns_per_step_SA": (rB_sa - lns("rB770", sa)) - (rA770 - lns("rA770", sa)),
                "seed_steps_rB770": math.log(steps["rB770"][sb]) - lns("rB770", sa),
                "seed_steps_rA770": math.log(steps["rA770"][sb]) - lns("rA770", sa),
            },
        })
    return complete, per_block


def describe_arms(runs):
    out = {}
    for run in runs:
        if run["status"] != "valid":
            continue
        key = "%s|%s|%s" % (run["arm"], run["point_id"], run["seed"] if run["arm"].startswith("r") else "-")
        out.setdefault(key, []).append(run)
    table = {}
    for key, items in sorted(out.items()):
        online = [r["online_ms"] for r in items]
        ops = items[0]["ops"]
        table[key] = {"runs": len(items), "online_ms_median": statistics.median(online),
                      "online_ms_min": min(online), "online_ms_max": max(online),
                      "ops": ops, "ns_per_op_median": statistics.median(online) * 1e6 / ops if ops else None,
                      "setup_ms_median": statistics.median(r["setup_ms"] for r in items),
                      "process_wall_ms_median": statistics.median(r["process_wall_ms"] for r in items),
                      "peak_rss_kb_max": max(r["peak_rss_kb"] or 0 for r in items)}
    return table


def f_panel(runs, protocol):
    f = protocol["panels"]["F"]
    points = {}
    for run in runs:
        if run["panel"] == "F":
            points.setdefault(run["point_id"], []).append(run)
    complete = {}
    for point_id, items in sorted(points.items()):
        if len(items) == f["runs_per_point"] and all(r["status"] == "valid" for r in items):
            complete[point_id] = items
    rows = []
    for point_id, items in sorted(complete.items()):
        w = int(point_id[1:])
        x = {}
        seed_family = []
        for arm in f["rho_arms"]:
            by_seed = {r["seed"]: r["online_ms"] for r in items if r["arm"] == arm}
            x[arm] = mean([math.log(v) for v in by_seed.values()])
            seed_family.append(math.log(by_seed[830000 + w]) - math.log(by_seed[202610061 + w]))
            x[arm + "_ms_mean"] = mean(list(by_seed.values()))
        ic = [r["online_ms"] for r in items if r["arm"] == "iB770c"][0]
        rows.append({"point": point_id, "x": x, "ic_ln": math.log(ic), "ic_ms": ic,
                     "impl_rho": x["rB770"] - x["rA770"], "rev_rho": x["rA770"] - x["rA819"],
                     "tuned": x["rT770"] - x["rA770"], "seed_family": mean(seed_family)})
    out = {"complete_points": len(rows), "rows": rows}
    if len(rows) >= 2:
        for name, seed in (("impl_rho", 2026101402), ("rev_rho", 2026101403), ("tuned", 2026101404),
                           ("seed_family", 2026101405)):
            out[name] = summarize([r[name] for r in rows], seed, 1)
        sec23 = {}
        for arm in f["rho_arms"]:
            def ratio(sample, arm=arm):
                return mean([r["x"][arm + "_ms_mean"] for r in sample]) / mean([r["ic_ms"] for r in sample])
            boot = bootstrap(rows, ratio, 2026101406)
            per_point = [r["x"][arm + "_ms_mean"] / r["ic_ms"] for r in rows]
            sec23[arm] = {"mean_rho_over_mean_ic": ratio(rows), "ci95": interval(boot, 0.95),
                          "median_per_point_ratio": statistics.median(per_point),
                          "points_ic_faster": sum(1 for v in per_point if v > 1)}
        out["section_23"] = sec23
    return out


def classify(per_block, m):
    stats = {name: summarize([b["terms"][name] for b in per_block], 2026101401 + i, m)
             for i, name in enumerate(CHAIN)}
    L_A = summarize([b["L_A"] for b in per_block], 2026101410, m)
    L_B = summarize([b["L_B"] for b in per_block], 2026101411, m)
    G = summarize([b["G"] for b in per_block], 2026101412, m)
    for i, name in enumerate(CHAIN):
        s = stats[name]
        flip = summarize([b["L_A"] + b["terms"][name] for b in per_block], 2026101420 + i, m)
        s["L_A_plus_this"] = flip
        s["share_of_G"] = s["mean"] / G["mean"] if G["mean"] else None
        if L_A["ci95"][1] < 0 and flip["ci_bonferroni"][0] > 0:
            s["class"] = "sufficient_to_flip"
        elif (s["ci_bonferroni"][0] > 0 or s["ci_bonferroni"][1] < 0) and abs(s["mean"]) >= 0.05:
            s["class"] = "contributes"
        elif -0.05 <= s["ci95"][0] and s["ci95"][1] <= 0.05:
            s["class"] = "negligible"
        else:
            s["class"] = "unresolved"
    return stats, L_A, L_B, G


def decide(per_block, m):
    stats, L_A, L_B, G = classify(per_block, m)
    a_cell = ("A_reproduces" if L_A["ci95"][1] < 0 else
              "A_not_reproduced" if L_A["ci95"][0] > 0 else "not_separated")
    b_cell = ("B_reproduces" if L_B["ci95"][0] > 0 else
              "B_not_reproduced" if L_B["ci95"][1] < 0 else "not_separated")
    responsible, how = [], None
    if a_cell == "A_not_reproduced":
        responsible, how = ["host_or_instance"], "A's direction does not survive the move to this runner"
    elif a_cell == "A_reproduces" and b_cell == "B_reproduces":
        sufficient = sorted((n for n in CHAIN if stats[n]["class"] == "sufficient_to_flip"),
                            key=lambda n: -stats[n]["mean"])
        if sufficient:
            responsible, how = sufficient, "each named factor alone flips A's configuration"
        else:
            ranked = sorted((n for n in CHAIN if stats[n]["class"] in ("contributes",) and stats[n]["mean"] > 0),
                            key=lambda n: -stats[n]["mean"])
            chosen = []
            for name in ranked:
                chosen.append(name)
                combined = summarize([b["L_A"] + sum(b["terms"][c] for c in chosen) for b in per_block],
                                     2026101430 + len(chosen), m)
                if combined["ci_bonferroni"][0] > 0:
                    responsible, how = list(chosen), "smallest set of contributing factors that flips A's configuration"
                    break
            if not responsible:
                how = "no set of contributing factors flips A's configuration with the Bonferroni bound"
    elif a_cell == "A_reproduces" and b_cell == "B_not_reproduced":
        responsible, how = ["host_or_instance"], "B's Q0 direction does not survive on this runner"
    else:
        how = "a configuration cell is not separated from parity"
    return {"A_cell": a_cell, "B_cell": b_cell, "L_A": L_A, "L_B": L_B, "G": G, "factors": stats,
            "responsible": responsible, "how": how}


def fmt(x, digits=3):
    return "n/a" if x is None else ("%.*f" % (digits, x))


def table_md(result):
    lines = ["| Quantity | mean (ln) | ratio | 95% | Bonferroni | class |", "|---|---:|---:|---|---|---|"]
    dec = result.get("decision")
    if not dec:
        return "No decision: " + result["reading"] + "\n"
    for name in ("L_A", "L_B", "G"):
        s = dec[name]
        lines.append("| %s | %s | %s | [%s, %s] | [%s, %s] | |" % (
            name, fmt(s["mean"]), fmt(math.exp(s["mean"])), fmt(s["ci95"][0]), fmt(s["ci95"][1]),
            fmt(s["ci_bonferroni"][0]), fmt(s["ci_bonferroni"][1])))
    for name in CHAIN:
        s = dec["factors"][name]
        lines.append("| %s | %s | %s | [%s, %s] | [%s, %s] | %s |" % (
            name, fmt(s["mean"]), fmt(math.exp(s["mean"])), fmt(s["ci95"][0]), fmt(s["ci95"][1]),
            fmt(s["ci_bonferroni"][0]), fmt(s["ci_bonferroni"][1]), s["class"]))
    lines.append("")
    lines.append("Reading: **%s**; A cell %s, B cell %s; responsible: %s (%s)." % (
        result["reading"], dec["A_cell"], dec["B_cell"], ", ".join(dec["responsible"]) or "none", dec["how"]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--correctness-only", action="store_true")
    args = parser.parse_args()
    receipt = args.receipt.resolve(strict=True)
    protocol = json.loads((HERE / "protocol.json").read_text())
    schedule = json.loads((HERE / protocol["design"]["schedule_file"]).read_text())
    start = json.loads((receipt / "runner_start.json").read_text())
    provenance = {
        "protocol_sha256_now": sha256(HERE / "protocol.json"),
        "protocol_sha256_at_run": start["protocol_sha256"],
        "schedule_sha256_at_run": start["schedule_sha256"],
        "log_table_sha256_at_run": start["log_table_sha256"],
    }
    runs, problems, missing = load(receipt, protocol, schedule, partial=args.correctness_only)
    checks, detail = identity_checks(runs, protocol, receipt)
    status_counts = {}
    for run in runs:
        status_counts[run["status"]] = status_counts.get(run["status"], 0) + 1
    invalid = [{"serial": r["serial"], "arm": r["arm"], "point": r["point_id"], "issues": r["issues"],
                "raw_issues": r.get("raw_issues")} for r in runs if r["status"] == "invalid"]
    if args.correctness_only:
        out = {"kind": "n83_reconcile_correctness_check", "rows": len(runs), "status_counts": status_counts,
               "invalid": invalid, "checks": checks, "scalars": detail["scalars"], "replays": detail["replays"],
               "rho_steps": detail["rho_steps"], "ic_probes": detail["ic_probes"], "tables": detail["tables"],
               "arms_run": sorted({r["arm"] for r in runs}), "problems": problems,
               "provenance": provenance, "note": "correctness only: no timing value is written"}
        (receipt / "correctness.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"checks": checks, "status_counts": status_counts, "invalid": len(invalid)}, sort_keys=True))
        if invalid or not all(v for v in checks.values() if v is not None):
            raise SystemExit(3)
        return
    if provenance["protocol_sha256_now"] != provenance["protocol_sha256_at_run"]:
        problems.append("protocol.json changed after the run")
    changed = sorted(name for name, digest in protocol.get("frozen_files_sha256", {}).items()
                     if name != "verify_receipt.py" and sha256(HERE / name) != digest)
    if changed:
        problems.append("frozen files differ from protocol.json: " + ", ".join(changed))
    complete, per_block = q_panel(runs, protocol)
    _, per_block_unflagged = q_panel(runs, protocol, flagged_ok=False)
    fresh = f_panel(runs, protocol)
    result = {"kind": "n83_reconcile_result", "provenance": provenance, "status_counts": status_counts,
              "invalid_rows": invalid, "problems": problems, "identity_checks": checks,
              "identity_detail": detail, "complete_q_blocks": sorted(complete),
              "contention_flagged_rows": [{"serial": r["serial"], "arm": r["arm"], "flags": r["contention"]}
                                          for r in runs if r.get("contention")],
              "arms": describe_arms(runs), "q_blocks": per_block, "fresh": fresh}
    m = len(CHAIN)
    valid = (not problems and not invalid and all(v for v in checks.values() if v is not None) and
             len(per_block) >= 3 and fresh["complete_points"] >= 12)
    if not valid:
        result["reading"] = "no_result"
    else:
        aa_rho = summarize([b["aa_rho"] for b in per_block], 2026101440, 1)
        aa_ic = summarize([b["aa_ic"] for b in per_block], 2026101441, 1)
        pc = summarize([b["positive_control"] - b["positive_control_expected"] for b in per_block], 2026101442, 1)
        controls = {
            "aa_rho": dict(aa_rho, passed=abs(aa_rho["mean"]) <= 0.03 and -0.05 <= aa_rho["ci95"][0] and aa_rho["ci95"][1] <= 0.05),
            "aa_ic": dict(aa_ic, passed=abs(aa_ic["mean"]) <= 0.03 and -0.05 <= aa_ic["ci95"][0] and aa_ic["ci95"][1] <= 0.05),
            "positive_control_minus_expected": dict(pc, passed=abs(pc["mean"]) <= 0.10),
        }
        result["controls"] = controls
        result["decision"] = decide(per_block, m)
        result["also"] = {
            "tuned": summarize([b["tuned"] for b in per_block], 2026101450, 1),
            "L_T_with_A_ic": summarize([b["L_T_with_A_ic"] for b in per_block], 2026101451, 1),
            "L_T_with_B_ic": summarize([b["L_T_with_B_ic"] for b in per_block], 2026101452, 1),
            "split": {k: summarize([b["split"][k] for b in per_block], 2026101460 + i, 1)
                      for i, k in enumerate(sorted(per_block[0]["split"]))},
            "impl_order_seedA_first": {k: mean([b["impl_order_seedA_first"][k] for b in per_block]) for k in ("impl", "seed")},
            "impl_order_seedB_first": {k: mean([b["impl_order_seedB_first"][k] for b in per_block]) for k in ("impl", "seed")},
            "host_residual_A": A_PUBLISHED_LN - result["decision"]["L_A"]["mean"],
            "host_residual_B": B_PUBLISHED_LN - result["decision"]["L_B"]["mean"],
            "max_abs_chain_residual": max(abs(b["chain_residual"]) for b in per_block),
        }
        if not all(c["passed"] for c in controls.values()):
            result["reading"] = "inconclusive_controls"
        else:
            result["reading"] = "decided"
            if len(per_block_unflagged) != len(per_block):
                if len(per_block_unflagged) >= 3:
                    other = decide(per_block_unflagged, m)
                    result["decision_unflagged_blocks"] = other
                    if other["responsible"] != result["decision"]["responsible"]:
                        result["reading"] = "sensitive_to_contention"
                else:
                    result["reading"] = "sensitive_to_contention"
    (receipt / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (receipt / "result_table.md").write_text(table_md(result))
    print(json.dumps({"reading": result["reading"],
                      "responsible": result.get("decision", {}).get("responsible"),
                      "status_counts": status_counts}, sort_keys=True))


if __name__ == "__main__":
    main()
