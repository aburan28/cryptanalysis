#!/usr/bin/env python3
"""Audit a receipt of run_schedule.py and apply the frozen statistics (protocol.json).

    python3 verify_receipt.py --receipt-dir R --crypto-repo C [--smoke]

Reads `R/runs.jsonl`, every arm's report, the controls, and section 23's
claims summary (`R/claims_s23/claims/summary.json`, written by claims.py before this
runs). Writes `R/result.json` and `R/result_table.md`. Nothing is re-run;
`--smoke` only relaxes the completeness rule (64 R1 rows a size).
"""

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
TARGETS = json.loads((HERE / "inputs" / "targets.json").read_text())
SIZES = [(1, 47), (0, 57), (0, 41), (0, 53), (1, 59), (0, 61)]
REFS = ["parallel", "strong", "strong_wide", "tuned"]
BOOT, SEED = 10000, 2026101501
BL_CONSTANT = 1.93 * 1.21


def rows_of(log):
    return [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]


def chosen(rows):
    """First clean valid attempt per (arm, size, target, run); if every attempt
    was flagged as contended, the first valid one, marked (protocol isolation)."""
    out, attempts = {}, {}
    for row in rows:
        if "arm" not in row or "control" in row or row.get("status") == "skipped_time_guard":
            continue
        key = (row["arm"], row["size"], row["target"], row["run"])
        attempts.setdefault(key, []).append(row)
    for key, tries in attempts.items():
        clean = [r for r in tries if r["status"] == "valid" and not r["contended"]]
        valid = [r for r in tries if r["status"] == "valid"]
        if clean or valid:
            out[key] = dict(clean[0] if clean else valid[0], flagged_row=not clean)
    return out, attempts


def boot_ratio(num, den, rng):
    """Ratio of means with a paired bootstrap interval over targets."""
    k = len(num)
    point = statistics.fmean(num) / statistics.fmean(den)
    draws = []
    for _ in range(BOOT):
        idx = [rng.randrange(k) for _ in range(k)]
        draws.append(sum(num[j] for j in idx) / sum(den[j] for j in idx))
    draws.sort()
    return {"value": point, "ci95": [draws[int(0.025 * BOOT)], draws[int(0.975 * BOOT) - 1]]}


def reading(ci, above, below):
    if ci[0] > 1:
        return above
    if ci[1] < 1:
        return below
    return "not_separated"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--crypto-repo", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    R = args.receipt_dir
    sys.path.insert(0, str(args.crypto_repo / "research" / "ic_candidate_tournament_20260915"))
    sys.path.insert(0, str(args.crypto_repo / "research" / "sat_factor_base_review_20260908" / "autolab"))
    import oracle  # noqa: E402
    import boundary_autolab as lab  # noqa: E402

    rows = rows_of(R / "runs.jsonl")
    pick, attempts = chosen(rows)
    problems = []

    # Controls.
    ctl = {r["control"]: r for r in rows if "control" in r}
    expected = {c["id"]: c for c in PROTOCOL["controls"]["cases"]}
    q0_scalar = PROTOCOL["controls"]["q0"]["expected_scalar"]
    identity_ok = bool(ctl) and all(
        ctl.get(cid, {}).get("walk_steps") == c["expected_walk_steps"]
        and ctl.get(cid, {}).get("recovered_scalar") == q0_scalar for cid, c in expected.items())
    positive = None
    if ctl.get("positive_hi", {}).get("valid") and ctl.get("positive_lo", {}).get("valid"):
        got = math.log(ctl["positive_hi"]["online_ms"] / ctl["positive_lo"]["online_ms"])
        want = math.log(14229982 / 5353957)
        positive = {"ln_time_ratio": got, "ln_step_ratio": want, "passed": abs(got - want) <= 0.10}
    controls = {"ran": bool(ctl), "identity_passed": identity_ok, "positive": positive,
                "cases": {k: {x: v.get(x) for x in ("valid", "walk_steps", "online_ms", "recovered_scalar", "contended")}
                          for k, v in ctl.items()}}

    # Section 23's claims summary for the IC rows (in-process rho).
    claims_path = R / "claims_s23" / "claims" / "summary.json"
    s23_claims = json.loads(claims_path.read_text()) if claims_path.exists() else []
    s23_pass = {c["row"]: c["status"] == "PASS" for c in s23_claims}
    ledger = lab.load_ledger(lab.load_protocol())

    rng = random.Random(SEED)
    sizes_out, ext_claims = [], []
    by_key = {(t["a"], t["n"], t["target"]): t for t in TARGETS["targets"]}
    for a, n in SIZES:
        size = f"k{a}n{n}"
        r = int(TARGETS["curves"][size]["subgroup_order"])
        per, size_problems = [], []
        targets_here = sorted({k[2] for k in attempts if k[1] == size and k[3] == 1})
        if not targets_here:
            continue
        curve = None
        for t in targets_here:
            got = {arm: pick.get((arm, size, t, 1)) for arm in ("ic", "strong", "strong_wide", "tuned")}
            if any(v is None for v in got.values()):
                size_problems.append(f"{t}: no clean valid attempt for " +
                                     ",".join(k for k, v in got.items() if v is None))
                continue
            ic = json.loads((R / got["ic"]["file"]).read_text())
            ext = {arm: json.loads((R / got[arm]["file"]).read_text()) for arm in ("strong", "strong_wide", "tuned")}
            fixture = ic["identity_inputs"]["fixture"]
            if curve is None:
                curve = oracle.Curve(fixture)
            scal = {"ic": ic["certificates"]["ic"]["scalar"], "parallel": ic["certificates"]["rho"]["scalar"],
                    "strong": ext["strong"]["recovered_scalar"], "tuned": ext["tuned"]["recovered_scalar"]}
            point = by_key[(a, n, t)]["point"]
            checks = {
                "one_scalar": len(set(scal.values())) == 1,
                "frozen_point": ic["certificates"]["ic"]["target"] == point
                and all(e["public_target_q"] == point for e in ext.values()),
                "same_curve": all(e["subgroup_order"] == fixture["subgroup_order"]
                                  and e["generator"] == fixture["generator"] for e in ext.values()),
                "oracle_replay": curve.mul(curve.g, int(scal["tuned"])) == curve.decode(point),
                # claims.py assembles clean rows only; a flagged IC row has no claim.
                "s23_claim_pass": True if got["ic"]["flagged_row"] else s23_pass.get(f"{size}/{t}-R1"),
            }
            if not all(v is True for v in checks.values()):
                size_problems.append(f"{t}: identity {checks}")
                continue
            reps = ic["repetitions"]
            row = {
                "target": t,
                "flagged": any(v["flagged_row"] for v in got.values()),
                "ic_online_ms": ic["median"]["ic_online_wall_ms"],
                "ic_setup_ms": statistics.median(x["setup_ns"] for x in reps) / 1e6,
                "parallel_online_ms": ic["median"]["rho_online_wall_ms"],
                "parallel_setup_ms": statistics.median(x["rho_setup_ns"] for x in reps) / 1e6,
                "parallel_steps": ic["rho_counts"]["steps"],
            }
            for arm in ("strong", "strong_wide", "tuned"):
                e = ext[arm]
                row[f"{arm}_online_ms"] = e["online_ms"]
                row[f"{arm}_walk_ms"] = e["online_phase_ns"]["walk_and_collision"] / 1e6
                row[f"{arm}_setup_ms"] = e["preparation_ns_excluded"] / 1e6
                row[f"{arm}_steps"] = e["outcome"]["walk_steps"]
                row[f"{arm}_field_type"] = e["field_type"]
            per.append(row)
            # The vs_rho claim with this external rho substituted, through the same checker.
            cpath = R / "claims_s23" / "claims" / size / f"{t}-R1.claim.json"
            if cpath.exists():
                base = json.loads(cpath.read_text())["claim"]
                for arm in ("strong", "strong_wide", "tuned"):
                    e = ext[arm]
                    claim = dict(base)
                    claim.update({
                        "rho_online_wall_ms": e["online_ms"],
                        "online_speedup": e["online_ms"] / base["ic_online_wall_ms"],
                        "rho_scalar_verified": e["generic_scalar_replay_verified"],
                        "rho_replay_certificate_sha256": e["public_input_sha256"],
                        "rho_reference_uid": f"s23-tuned-rho:{arm}:{e['run_id']}",
                        "rho_policy": {"worker_count": 1, "walk_policy": json.dumps(e["rho_policy"], sort_keys=True),
                                       "collision_policy": "StrongRhoG distinguished points, one target",
                                       "distinguished_point_memory_bytes": e["outcome"]["table_payload_lower_bound_bytes"],
                                       "lanes": e["rho_policy"]["lanes"],
                                       "distinguished_point_bits": e["rho_policy"]["distinguished_bits"]},
                        "verdict": "index calculus online faster" if e["online_ms"] > base["ic_online_wall_ms"]
                        else "rho online faster",
                    })
                    res = lab.validate_claim(claim, stage="vs_rho", ledger=ledger)
                    ext_claims.append({"row": f"{size}/{t}-R1", "arm": arm, "status": res["status"],
                                       "errors": res["validation_errors"]})
        complete = len(per) == (len(targets_here) if args.smoke else 64) and not size_problems
        entry = {"size": size, "a": a, "n": n, "r": r, "rows_used": len(per), "complete": complete,
                 "problems": size_problems}
        if per and complete:
            ic_on = [x["ic_online_ms"] for x in per]
            ic_cold = [x["ic_setup_ms"] + x["ic_online_ms"] for x in per]
            setup_mean = statistics.fmean(x["ic_setup_ms"] for x in per)
            refs = {}
            for ref in REFS:
                on = [x[f"{ref}_online_ms"] for x in per]
                cold = [x[f"{ref}_setup_ms"] + x[f"{ref}_online_ms"] for x in per]
                online = boot_ratio(on, ic_on, rng)
                coldr = boot_ratio(ic_cold, cold, rng)
                saving = statistics.fmean(on) - statistics.fmean(ic_on)
                step_ms = statistics.median(x[f"{ref}_online_ms"] / x[f"{ref}_steps"] for x in per)
                bl_ms = BL_CONSTANT * r * step_ms ** 2 / (2 * n * setup_mean)
                refs[ref] = {
                    "rho_online_ms_mean": statistics.fmean(on),
                    "rho_setup_ms_mean": statistics.fmean(x[f"{ref}_setup_ms"] for x in per),
                    "online_rho_over_ic": online,
                    "online_reading": reading(online["ci95"], "ic_online_faster", "rho_online_faster"),
                    "online_median_of_row_ratios": statistics.median(o / i for o, i in zip(on, ic_on)),
                    "rows_ic_faster": sum(o > i for o, i in zip(on, ic_on)),
                    "cold_ic_over_rho": coldr,
                    "cold_reading": reading(coldr["ci95"], "rho_cold_faster", "ic_cold_faster"),
                    "break_even_targets": setup_mean / saving if saving > 0 else "never",
                    "ms_per_step_median": step_ms,
                    "steps_over_floor_mean": statistics.fmean(x[f"{ref}_steps"] for x in per)
                    / math.sqrt(math.pi * r / (4 * n)),
                    "bl_model": {"bl_online_ms": bl_ms, "ic_online_over_bl": statistics.fmean(ic_on) / bl_ms},
                }
                if ref != "parallel":
                    walk = [x[f"{ref}_walk_ms"] for x in per]
                    refs[ref]["online_rho_over_ic_walk_only_recut"] = statistics.fmean(walk) / statistics.fmean(ic_on)
                    refs[ref]["field_type"] = sorted({x[f"{ref}_field_type"] for x in per})
                clean = [x for x in per if not x["flagged"]]
                if len(clean) < len(per) and len(clean) >= 2:
                    refs[ref]["online_rho_over_ic_without_flagged_rows"] = (
                        statistics.fmean(x[f"{ref}_online_ms"] for x in clean)
                        / statistics.fmean(x["ic_online_ms"] for x in clean))
            entry.update({"ic_online_ms_mean": statistics.fmean(ic_on), "ic_setup_ms_mean": setup_mean,
                          "flagged_rows_used": sum(x["flagged"] for x in per),
                          "s_unit_note": "wall ms; S per reference = ms / (that reference's ms per step) / sqrt(r)",
                          "references": refs})
        # A/A.
        aa = []
        for i in range(1, 5):
            t = f"T{i:02d}"
            for arm in ("ic", "strong", "strong_wide", "tuned"):
                p1, p2 = pick.get((arm, size, t, 1)), pick.get((arm, size, t, 2))
                if not (p1 and p2):
                    continue
                d1, d2 = (json.loads((R / p["file"]).read_text()) for p in (p1, p2))
                if arm == "ic":
                    aa.append({"target": t, "arm": arm, "online_R2_over_R1":
                               d2["median"]["ic_online_wall_ms"] / d1["median"]["ic_online_wall_ms"]})
                else:
                    aa.append({"target": t, "arm": arm, "online_R2_over_R1": d2["online_ms"] / d1["online_ms"],
                               "steps_identical": d1["outcome"]["walk_steps"] == d2["outcome"]["walk_steps"]})
        entry["aa"] = aa
        if any(x.get("steps_identical") is False for x in aa):
            size_problems.append("A/A rho steps differ")
        sizes_out.append(entry)

    contended = [{k: r[k] for k in ("arm", "size", "target", "run", "attempt", "contention_flags")}
                 for r in rows if r.get("contended") and "size" in r]
    invalid = [{k: r[k] for k in ("arm", "size", "target", "run", "attempt", "issues")}
               for r in rows if r.get("status") == "invalid" and "size" in r]
    skipped = [r for r in rows if r.get("status") == "skipped_time_guard"]
    status = "void_identity_control" if not identity_ok else (
        "inconclusive_controls" if not (positive and positive["passed"]) else "measured")
    result = {"kind": "s23_tuned_rho_result", "status": status, "smoke": args.smoke, "controls": controls,
              "sizes": sizes_out, "s23_claims": {"rows": len(s23_claims),
                                                  "pass": sum(1 for c in s23_claims if c["status"] == "PASS")},
              "external_claims": {"rows": len(ext_claims), "pass": sum(1 for c in ext_claims if c["status"] == "PASS"),
                                  "failing": [c for c in ext_claims if c["status"] != "PASS"][:20]},
              "attempts_invalid": invalid, "attempts_contended": contended, "blocks_skipped": len(skipped),
              "problems": problems}
    (R / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    lines = ["| size | ref | rho/IC online [95%] | reading | IC/rho cold [95%] | break-even | IC online / BL model | rho ms/step |",
             "|---|---|---|---|---|---|---|---|"]
    for s in sizes_out:
        for ref, v in s.get("references", {}).items():
            o, c = v["online_rho_over_ic"], v["cold_ic_over_rho"]
            be = v["break_even_targets"]
            lines.append("| %s | %s | %.3g [%.3g, %.3g] | %s | %.3g [%.3g, %.3g] | %s | %.3g | %.4g |" % (
                s["size"], ref, o["value"], *o["ci95"], v["online_reading"], c["value"], *c["ci95"],
                be if isinstance(be, str) else "%.3g" % be, v["bl_model"]["ic_online_over_bl"], v["ms_per_step_median"]))
        if not s.get("references"):
            lines.append("| %s | - | withheld: %s | | | | | |" % (s["size"], "; ".join(s["problems"][:3]) or "incomplete"))
    lines.append("")
    lines.append(f"Status: **{status}**; identity control {identity_ok}; positive control {positive}; "
                 f"section 23 claims {result['s23_claims']}; external claims {result['external_claims']['pass']}"
                 f"/{result['external_claims']['rows']} PASS; skipped blocks {len(skipped)}.")
    (R / "result_table.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": status, "sizes": [(s["size"], s["rows_used"], s["complete"]) for s in sizes_out]}))


if __name__ == "__main__":
    main()
