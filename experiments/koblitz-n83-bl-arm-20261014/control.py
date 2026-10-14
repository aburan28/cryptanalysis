#!/usr/bin/env python3
"""Positive control: on small curves, BL's online step count and its speedup over plain rho match the model.

For every frozen control (protocol.json `controls.positive`): build tables with
a step-count stop (`stop_steps`, one table per size), verify every record with
the binary's `verify-table`, then solve N known-answer targets with the table
(BL online) and the same N targets without it (plain rho, same binary, same
jumps, same DP rule). Every recovered scalar must equal its planted one.
The decision compares mean step counts with the frozen model
(`bl_tools.predict_online_steps`, `predict_plain_steps`): the plain-rho mean
against its model (detector calibration) and BL's speedup over plain rho
against the model's speedup (the gate, protocol amendment A1); the absolute BL
step ratio is reported, not gated. Counts only, no timing is read or claimed. Runs are spread over `--workers` processes
(counts do not depend on placement).
"""

import argparse
import concurrent.futures
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bl_tools as bt  # noqa: E402


def planted(curve, r, i):
    digest = hashlib.sha256(("n83-bl-arm-positive-control|%d,%d|%d" % (curve[0], curve[1], i)).encode()).digest()
    return int.from_bytes(digest[:8], "little") % (r - 1) + 1


def one_online(job):
    spec, bin_dir, curve, dp, jump_seed, walk_seed, scalar, table, blake = job
    argv, env = bt.online_control_command(spec, bin_dir, curve, dp, jump_seed, walk_seed, scalar, table, blake)
    code, out, err, wall, _ = bt.run_pinned(argv, env, None, timeout=600)
    row = bt.parse_online(spec, out)
    row.update({"walk_seed": walk_seed, "planted": scalar, "exit": code,
                "stderr_tail": err[-400:] if code else ""})
    row["verified"] = bool(row["verified"]) and code == 0 and row.get("recovered") == scalar
    return row


def bootstrap_mean_ci(values, seed, draws=10000):
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return [means[int(0.025 * draws)], means[int(0.975 * draws) - 1]]


def run_control(control, protocol, bin_dir, out_dir, workers, n_override=None):
    spec = protocol["rho_step_implementations"][control["implementation"]]["bl"]
    spec = dict(spec, lanes=control.get("lanes", spec["lanes"]))
    curve = tuple(control["curve"])
    dp = control["dp_bits"]
    jump_seed = control["bl_jump_seed"]
    targets = n_override or control["targets"]
    folder = out_dir / control["id"]
    folder.mkdir(parents=True, exist_ok=False)
    model = protocol["model"]
    result = {"id": control["id"], "implementation": control["implementation"], "curve": list(curve),
              "dp_bits": dp, "lanes": spec["lanes"], "targets": targets, "tables": [], "checks": {}}
    tables = []
    for size in control["precompute_steps"]:
        table = folder / ("table_%d.bin" % size)
        argv, env = bt.precompute_command(spec, bin_dir, curve, dp, jump_seed, control["precompute_seed"],
                                          table, {"stop_steps": size})
        code, out, err, wall, _ = bt.run_pinned(argv, env, None, timeout=3600)
        summary = ([r for r in bt.json_lines(out) if r.get("kind") == "bl_precompute"] or [{}])[-1]
        if code != 0 or not summary:
            raise SystemExit("precompute failed for %s: %s" % (control["id"], err[-2000:]))
        argv, env = bt.verify_command(spec, bin_dir, curve, dp, table, summary["table_blake3"], workers)
        vcode, vout, verr, _, _ = bt.run_pinned(argv, env, None, timeout=3600)
        verification = ([r for r in bt.json_lines(vout) if r.get("kind") == "bl_table_verification"] or [{}])[-1]
        tables.append((size, table, summary))
        result["tables"].append({"stop_steps": size, "summary": summary, "sha256": bt.sha256(table),
                                 "verification": verification, "verify_exit": vcode})
    r = int(result["tables"][0]["summary"]["identity"]["subgroup_order"])
    automorphisms = int(result["tables"][0]["summary"]["identity"]["automorphism_size"])
    scalars = [planted(curve, r, i) for i in range(targets)]
    seeds = [control["walk_seed_base"] + i for i in range(targets)]
    jobs = {("plain", None): [(spec, bin_dir, curve, dp, jump_seed, s, d, None, None) for s, d in zip(seeds, scalars)]}
    for size, table, summary in tables:
        jobs[("bl", size)] = [(spec, bin_dir, curve, dp, jump_seed, s, d, str(table), summary["table_blake3"])
                              for s, d in zip(seeds, scalars)]
    rows = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for key, batch in jobs.items():
            rows[key] = list(pool.map(one_online, batch))
    with (folder / "rows.jsonl").open("w") as stream:
        for (arm, size), batch in rows.items():
            for row in batch:
                stream.write(json.dumps(dict(row, arm=arm, stop_steps=size), sort_keys=True) + "\n")
    band = model["positive_control_band"]
    plain_steps = [row["steps"] for row in rows[("plain", None)]]
    plain_pred = bt.predict_plain_steps(r, automorphisms, spec["lanes"], dp)
    plain_mean = sum(plain_steps) / len(plain_steps)
    result["plain"] = {"mean_steps": plain_mean, "ci95": bootstrap_mean_ci(plain_steps, 1),
                       "predicted_steps": plain_pred, "measured_over_predicted": plain_mean / plain_pred,
                       "floor_sqrt_pi_l_over_2": math.sqrt(math.pi * bt.classes(r, automorphisms) / 2)}
    checks = {"all_verified": all(row["verified"] for batch in rows.values() for row in batch),
              "tables_verified": all(t["verification"].get("status") == "PASS" and t["verify_exit"] == 0
                                     for t in result["tables"]),
              "plain_matches_model": band[0] <= plain_mean / plain_pred <= band[1]}
    result["bl"] = []
    reported = {}
    for size, table, summary in tables:
        steps = [row["steps"] for row in rows[("bl", size)]]
        mean = sum(steps) / len(steps)
        pred = bt.predict_online_steps(r, automorphisms, spec["lanes"], dp, summary["covered_points"])
        hits = sum(row["solved_by"] == "precomputed_table" for row in rows[("bl", size)])
        speedup = plain_mean / mean
        speedup_pred = plain_pred / pred
        entry = {"stop_steps": size, "table_entries": summary["table_entries"],
                 "covered_points": summary["covered_points"], "mean_steps": mean,
                 "ci95": bootstrap_mean_ci(steps, 2 + size), "predicted_steps": pred,
                 "measured_over_predicted": mean / pred, "table_hits": hits,
                 "speedup_over_plain": speedup, "speedup_predicted": speedup_pred,
                 "speedup_measured_over_predicted": speedup / speedup_pred}
        result["bl"].append(entry)
        # Gate (protocol amendment A1): the speedup over plain rho, same binary.
        checks["speedup_matches_model_%d" % size] = band[0] <= speedup / speedup_pred <= band[1]
        reported["bl_steps_within_band_of_model_%d" % size] = band[0] <= mean / pred <= band[1]
    result["checks"] = checks
    result["reported_not_gating"] = reported
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    for t in result["tables"]:
        Path(folder / ("table_%d.bin" % t["stop_steps"])).unlink()
    (folder / "control.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", help="comma-separated control ids")
    parser.add_argument("--targets", type=int, help="smoke only: fewer targets than frozen")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    wanted = set(args.only.split(",")) if args.only else None
    results = []
    for control in protocol["controls"]["positive"]["runs"]:
        if wanted and control["id"] not in wanted:
            continue
        result = run_control(control, protocol, args.bin_dir.resolve(), args.out.resolve(), args.workers, args.targets)
        results.append({"id": result["id"], "status": result["status"], "checks": result["checks"],
                        "plain": result["plain"]["measured_over_predicted"],
                        "bl": [(e["stop_steps"], round(e["measured_over_predicted"], 4),
                                round(e["speedup_over_plain"], 3), round(e["speedup_predicted"], 3)) for e in result["bl"]]})
        print(json.dumps(results[-1], sort_keys=True), flush=True)
    summary = {"kind": "bl_positive_control_summary", "targets_override": args.targets,
               "status": "PASS" if results and all(r["status"] == "PASS" for r in results) else "FAIL",
               "controls": results, "note": "step counts only; no timing is read or claimed"}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": summary["status"]}))
    if summary["status"] != "PASS":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
