#!/usr/bin/env python3
"""Run one frozen arm of the n=83 reconciliation on one public point.

`run_schedule.py` launches this wrapper pinned to the execution CPU; the
producer inherits the affinity and a clean, whitelisted environment. The
producer's own online clock is the metric. The wrapper's start-up, input
writing and checks are outside it. The raw producer output is printed
base64-encoded so the stdout file is the archived receipt; the last line
carries `online_ms=`, `verified=1`, the recovered scalar and the work count.

Each record also carries the online time re-cut at the *other* experiment's
boundary (`online_ms_at_A_boundary` / `online_ms_at_B_boundary`), from the
producers' own phase timers, so the boundary factor needs no extra run:

* A's rho boundary (n83_strong_point_eval / n83_rho_optimization_eval):
  target membership and subgroup check + walk starts + walk/collision +
  generic scalar replay.
* B's rho boundary (rung 3): walk starts + walk/collision + [d]G = Q checks;
  the public-point subgroup check is timed as `target_generation_ms_excluded`.
* A's and B's IC boundaries are the same five phases (query hash, PDP,
  relation check, descent, recovery check); both producers report them.
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PHASES = ("target_query_ms", "target_pdp_ms", "target_relation_check_ms",
          "target_descent_ms", "target_recovery_check_ms")
BASE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "RAYON_NUM_THREADS": "1",
            "KIC_THREADS": "1", "KIC_RHO_THREADS": "1", "OMP_NUM_THREADS": "1"}


def target_sha256(point):
    return hashlib.sha256(("%d,%d" % (int(point[0]), int(point[1]))).encode()).hexdigest()


def same(a, b):
    try:
        return [int(v) for v in a] == [int(v) for v in b]
    except (TypeError, ValueError):
        return False


def rows(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def write_point(folder, point):
    path = folder / "point.jsonl"
    path.write_text(json.dumps([str(v) for v in point], separators=(",", ":")) + "\n")
    return path


def run(command, env):
    return subprocess.run(command, env=env, capture_output=True, text=True)


def rho_strong_g(args, point, folder):
    """A's StrongRhoG<WideGf2,u64> adapter, or A's configured (tuned) worker."""
    target = write_point(folder, point)
    command = [str(args.binary), str(target), str(args.seed)]
    if args.kind == "rho_tuned":
        command.append(str(args.config))
    proc = run(command, dict(BASE_ENV))
    produced = [r for r in rows(proc.stdout) if r.get("schema") == "n83-exact-public-strong-evaluation/v1"
                or str(r.get("schema", "")).startswith("n83-")]
    record = produced[-1] if produced else {}
    issues = []
    if proc.returncode != 0:
        issues.append("rho exit %d" % proc.returncode)
    if record.get("status") != "PASS_VERIFIED_PUBLIC_TARGET" or record.get("group_verified") is not True:
        issues.append("rho record not verified")
    if not same(record.get("published_q"), point) or record.get("known_answer_input") is not False:
        issues.append("rho did not solve the supplied public point")
    policy = record.get("rho_policy") or {}
    if args.kind == "rho_adapter" and (policy.get("lanes"), policy.get("distinguished_bits"),
                                       policy.get("escape_fruitless")) != (32, 4, False):
        issues.append("adapter is not at the strong defaults")
    if args.kind == "rho_tuned":
        config = json.loads(Path(args.config).read_text())
        if (policy.get("lanes"), policy.get("distinguished_bits")) != (config["lanes"], config["dp_bits"]):
            issues.append("tuned worker policy differs from its config")
    phases = record.get("online_phase_ns") or {}
    online = float(record.get("online_ms") or 0.0)
    if record and abs(sum(phases.values()) / 1e6 - online) > 1e-3 * max(1.0, online):
        issues.append("rho phases do not cover the online interval")
    outcome = record.get("outcome") or {}
    b_boundary = phases.get("walk_and_collision", 0) / 1e6
    fields = {"online_ms": online, "online_ms_at_A_boundary": online,
              "online_ms_at_B_boundary": b_boundary,
              "setup_ms": (record.get("preparation_ns_excluded") or 0) / 1e6,
              "ops": outcome.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_scalar"),
              "kernel": record.get("arithmetic_kernel")}
    return proc, [record], issues, fields


def rho_rung3(args, point, folder):
    """B's strong rung 3 (koblitz_rho_batch_ks_strong_online), B's exact environment."""
    env = dict(BASE_ENV, KIC_RHO_RUNG="3", KIC_RHO_LANES="32", KIC_RHO_DP_BITS="4",
               KIC_RHO_TARGET_POINT="%d,%d" % (int(point[0]), int(point[1])))
    proc = run([str(args.binary), "83", "1", "signed_frobenius", "1", str(args.seed)], env)
    produced = rows(proc.stdout)
    records = [r for r in produced if r.get("kind") == "rho_ks_batch_fixture"]
    summary = ([r for r in produced if r.get("kind") == "rho_ks_batch_summary"] or [{}])[-1]
    record = records[0] if len(records) == 1 else {}
    issues = []
    if proc.returncode != 0:
        issues.append("rho exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("rho emitted %d fixture records" % len(records))
    if record.get("verified") is not True or not same(record.get("published_q"), point):
        issues.append("rho record not verified on the supplied point")
    if record.get("published_fixture_scalar") is not None or record.get("automorphism_size") != 166:
        issues.append("rho received a known scalar or the wrong quotient")
    if (summary.get("rung"), summary.get("lanes"), summary.get("dp_bits")) != (3, 32, 4):
        issues.append("rung 3 is not at B's configuration")
    online = float(record.get("online_ms") or 0.0)
    if record and abs(record["walk_and_collision_ms"] + record["recovery_check_ms"] - online) > 1e-6 * max(1.0, online):
        issues.append("rho phases do not sum to the online interval")
    fields = {"online_ms": online,
              "online_ms_at_A_boundary": online + float(record.get("target_generation_ms_excluded") or 0.0),
              "online_ms_at_B_boundary": online,
              "setup_ms": record.get("online_start_ns", 0) / 1e6,
              "ops": record.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_fixture_scalar"),
              "kernel": summary.get("rho_field_path")}
    return proc, [record, summary], issues, fields


def ic(args, point, folder):
    """B's online producer (cached or fresh log table) or A's koblitz_orbit_dlp_fast (fresh)."""
    target = write_point(folder, point)
    out = folder / "ic.jsonl"
    env = dict(BASE_ENV, KIC_RANK_THREADS="1", KIC_TARGET_THREADS="1")
    if args.kind == "ic_online_cached":
        env["KIC_LOG_TABLE_IN"] = str(args.log_table)
    if args.kind == "ic_online_fresh" and args.log_table_out:
        env["KIC_LOG_TABLE_OUT"] = str(args.log_table_out)
    if args.rank_threads != 1:
        # Smoke runs only: a parallel rank stage changes setup, not the target scan.
        env["KIC_RANK_THREADS"] = str(args.rank_threads)
    proc = run([str(args.binary), str(args.base), str(target), str(args.rank_seed), str(out)], env)
    records = rows(out.read_text()) if out.exists() else []
    summary = (rows(proc.stdout) or [{}])[-1]
    record = records[0] if len(records) == 1 else {}
    issues = []
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("ic emitted %d target records" % len(records))
    if record.get("group_verified") is not True or not same(record.get("target"), point):
        issues.append("ic record not verified on the supplied point")
    table = summary.get("factor_log_table") or {}
    # A cached arm skips the rank stage (rank 0) and instead verifies all
    # [L_j]G = R_j of the table; a fresh arm must reach full rank in process.
    full_rank = (table.get("verified_columns") == args.columns if args.kind == "ic_online_cached"
                 else summary.get("rank") == args.columns)
    if (summary.get("base_hash") != args.base_hash or summary.get("targets_solved") != 1 or
            summary.get("targets_failed") != 0 or not full_rank):
        issues.append("ic setup is not full rank on the frozen base")
    if args.kind == "ic_online_cached" and (table.get("source") != "verified_cache" or
                                            table.get("verified_columns") != args.columns):
        issues.append("ic did not use the verified factor-log cache")
    if args.kind == "ic_online_fresh" and table.get("source") != "in_process_rank":
        issues.append("ic did not run its rank stage in process")
    if args.kind == "ic_fast" and "factor_log_table" in summary:
        issues.append("A's producer unexpectedly reports a log cache")
    phase_sum = sum(float(record.get(name) or 0.0) for name in PHASES)
    if args.kind == "ic_fast":
        online = float(record.get("target_ms") or 0.0)
        setup_ms = float((summary.get("timing_ms") or {}).get("process_total", 0.0)) - online
        # A's producer leaves a sub-microsecond residual between its five laps
        # and target_ms (A's README: "preserve the residual").
        tolerance = 1e-2 * max(1.0, online)
    else:
        online = float(record.get("online_ms") or 0.0)
        setup_ms = summary.get("setup_complete_ns", 0) / 1e6
        tolerance = 1e-3 * max(1.0, online)
        if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
            issues.append("ic setup did not finish before the online interval")
    if record and abs(phase_sum - online) > tolerance:
        issues.append("ic five phases do not sum to the online interval")
    fields = {"online_ms": online, "online_ms_at_A_boundary": online, "online_ms_at_B_boundary": online,
              "setup_ms": setup_ms, "ops": record.get("probes"), "ops_unit": "root_index_probes",
              "recovered_scalar": record.get("recovered_scalar"),
              "rank_stage_ms": (summary.get("timing_ms") or {}).get("rank_stage")}
    return proc, [record, summary], issues, fields


RUNNERS = {"rho_adapter": rho_strong_g, "rho_tuned": rho_strong_g, "rho_rung3": rho_rung3,
           "ic_online_cached": ic, "ic_online_fresh": ic, "ic_fast": ic}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, help="arm id from protocol.json")
    parser.add_argument("--kind", required=True, choices=sorted(RUNNERS))
    parser.add_argument("--panel", required=True)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", required=True, help="x,y decimal")
    parser.add_argument("--seed", type=int, default=0, help="rho walk seed")
    parser.add_argument("--config", type=Path, help="tuned rho config")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--base-hash")
    parser.add_argument("--log-table", type=Path)
    parser.add_argument("--log-table-out", type=Path)
    parser.add_argument("--rank-seed", type=int, default=7)
    parser.add_argument("--rank-threads", type=int, default=1)
    parser.add_argument("--columns", type=int, default=600)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")]
    with tempfile.TemporaryDirectory(prefix="n83-reconcile-arm-") as folder:
        proc, raw, issues, fields = RUNNERS[args.kind](args, point, Path(folder))
    raw_bytes = json.dumps({"arm": args.arm, "kind": args.kind, "panel": args.panel,
                            "point": [str(v) for v in point], "seed": args.seed,
                            "rank_seed": args.rank_seed, "returncode": proc.returncode,
                            "records": raw, "stderr_tail": proc.stderr[-4000:], "issues": issues},
                           sort_keys=True, separators=(",", ":")).encode()
    print("raw_b64=" + base64.b64encode(raw_bytes).decode())
    verified = not issues and fields["recovered_scalar"] is not None
    line = {
        "online_ms": "%.6f" % fields["online_ms"],
        "verified": "1" if verified else "0",
        "arm": args.arm,
        "panel": args.panel,
        "target_sha256": target_sha256(point),
        "recovered_scalar": str(fields["recovered_scalar"]),
        "online_ms_at_A_boundary": "%.6f" % fields["online_ms_at_A_boundary"],
        "online_ms_at_B_boundary": "%.6f" % fields["online_ms_at_B_boundary"],
        "setup_ms": "%.6f" % fields["setup_ms"],
        "ops": str(fields["ops"]),
        "ops_unit": fields["ops_unit"],
        "raw_result_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "issues": str(len(issues)),
    }
    print(" ".join("%s=%s" % item for item in line.items()))
    for issue in issues:
        print("issue: " + issue, file=sys.stderr)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
