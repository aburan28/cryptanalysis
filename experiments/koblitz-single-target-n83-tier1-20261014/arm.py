#!/usr/bin/env python3
"""Run one frozen arm on one public point and print isolated_bench fields.

`scripts/isolated_bench.py` launches this wrapper pinned to its execution CPU;
the producer inherits that affinity. The producer's own online clock is the
metric: the wrapper's start-up, input writing and checks are outside it. The
raw producer output is printed base64-encoded so the runner's stdout file is
the archived receipt. The last line carries `online_ms=`, `verified=1` and
the pair fields isolated_bench compares across the two arms of a pair.
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

HERE = Path(__file__).resolve().parent
PHASES = ("target_query_ms", "target_pdp_ms", "target_relation_check_ms",
          "target_descent_ms", "target_recovery_check_ms")


def target_sha256(point):
    return hashlib.sha256(("%d,%d" % (int(point[0]), int(point[1]))).encode()).hexdigest()


def same(a, b):
    try:
        return [int(v) for v in a] == [int(v) for v in b]
    except (TypeError, ValueError):
        return False


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]


def run_ic(args, point, folder):
    target = folder / "target.jsonl"
    target.write_text(json.dumps([str(v) for v in point], separators=(",", ":")) + "\n")
    out = folder / "ic.jsonl"
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C", "RAYON_NUM_THREADS": "1",
           "KIC_LOG_TABLE_IN": str(args.log_table)}
    proc = subprocess.run([str(args.binary), str(args.base), str(target), str(args.rank_seed), str(out)],
                          env=env, capture_output=True, text=True)
    records = rows(out.read_text()) if out.exists() else []
    summary = (rows(proc.stdout) or [{}])[-1]
    issues = []
    record = records[0] if len(records) == 1 else {}
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("ic emitted %d target records" % len(records))
    if record.get("group_verified") is not True or not same(record.get("target"), point):
        issues.append("ic record not verified on the supplied point")
    log_table = summary.get("factor_log_table") or {}
    if (log_table.get("source") != "verified_cache" or log_table.get("verified_columns") != args.columns or
            summary.get("base_hash") != args.base_hash or summary.get("targets_solved") != 1 or
            summary.get("targets_failed") != 0):
        issues.append("ic setup is not the verified factor-log cache for this base")
    online = float(record.get("online_ms") or 0.0)
    phase_sum = sum(float(record.get(name) or 0.0) for name in PHASES)
    if record and abs(phase_sum - online) > 1e-3 * max(1.0, online):
        issues.append("ic five phases do not sum to the online interval")
    if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
        issues.append("ic setup did not finish before the online interval")
    fields = {"online_ms": online, "setup_ms": summary.get("setup_complete_ns", 0) / 1e6,
              "ops": record.get("probes"), "ops_unit": "root_index_probes",
              "recovered_scalar": record.get("recovered_scalar")}
    return proc, [record, summary], issues, fields


def run_rho(args, point, folder):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C", "RAYON_NUM_THREADS": "1",
           "KIC_RHO_RUNG": "3", "KIC_RHO_LANES": "32", "KIC_RHO_DP_BITS": "4",
           "KIC_RHO_TARGET_POINT": "%d,%d" % (int(point[0]), int(point[1]))}
    proc = subprocess.run([str(args.binary), str(args.n), str(args.a), "signed_frobenius", "1", str(args.seed)],
                          env=env, capture_output=True, text=True)
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
    if record.get("published_fixture_scalar") not in (None,) or record.get("automorphism_size") != 2 * args.n:
        issues.append("rho received a known scalar or the wrong quotient")
    online = float(record.get("online_ms") or 0.0)
    if record and abs(record["walk_and_collision_ms"] + record["recovery_check_ms"] - online) > 1e-6 * max(1.0, online):
        issues.append("rho phases do not sum to the online interval")
    fields = {"online_ms": online, "setup_ms": record.get("online_start_ns", 0) / 1e6,
              "ops": record.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_fixture_scalar")}
    return proc, [record, summary], issues, fields


def run_rho_legacy(args, point, folder):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C", "RAYON_NUM_THREADS": "1",
           "KIC_RHO_PUBLIC_TARGET_POINT": json.dumps([str(v) for v in point], separators=(",", ":")),
           "KIC_RHO_WALK_SEED": str(args.seed)}
    proc = subprocess.run([str(args.binary), str(args.n), str(args.a), "signed_frobenius", "1", "packed"],
                          env=env, capture_output=True, text=True)
    records = rows(proc.stdout)
    record = records[0] if len(records) == 1 else {}
    issues = []
    if proc.returncode != 0:
        issues.append("packed rho exit %d" % proc.returncode)
    if (record.get("verified") is not True or not same(record.get("published_q"), point) or
            record.get("target_input_kind") != "public_point" or
            float(record.get("target_generation_ms_excluded", 1)) != 0.0):
        issues.append("packed rho record not verified on the supplied public point")
    online = float(record.get("total_ms") or 0.0)
    fields = {"online_ms": online, "setup_ms": 0.0, "ops": record.get("walk_steps"),
              "ops_unit": "walk_steps", "recovered_scalar": record.get("recovered_fixture_scalar"),
              "target_dependent_jump_setup_ms": record.get("setup_ms")}
    return proc, [record], issues, fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=("ic", "rho", "rho_legacy"))
    parser.add_argument("--panel", required=True)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", required=True, help="x,y decimal")
    parser.add_argument("--seed", type=int, default=0, help="rho walk seed")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--base-hash")
    parser.add_argument("--log-table", type=Path)
    parser.add_argument("--rank-seed", type=int, default=7)
    parser.add_argument("--curve-id", default="EC1N83Ce1h35c7ced6b497")
    parser.add_argument("--n", type=int, default=83)
    parser.add_argument("--a", type=int, default=1)
    parser.add_argument("--columns", type=int, default=600)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")]
    with tempfile.TemporaryDirectory(prefix="n83-arm-") as folder:
        runner = {"ic": run_ic, "rho": run_rho, "rho_legacy": run_rho_legacy}[args.arm]
        proc, raw, issues, fields = runner(args, point, Path(folder))
    raw_bytes = json.dumps({"arm": args.arm, "panel": args.panel, "point": [str(v) for v in point],
                            "seed": args.seed, "returncode": proc.returncode, "records": raw,
                            "stderr_tail": proc.stderr[-4000:], "issues": issues},
                           sort_keys=True, separators=(",", ":")).encode()
    print("raw_b64=" + base64.b64encode(raw_bytes).decode())
    verified = not issues and fields["recovered_scalar"] is not None
    line = {
        "online_ms": "%.6f" % fields["online_ms"],
        "verified": "1" if verified else "0",
        "panel": args.panel,
        "target_sha256": target_sha256(point),
        "recovered_scalar": str(fields["recovered_scalar"]),
        "curve_id": args.curve_id,
        "arm_verified": "1" if verified else "0",
        "arm": args.arm,
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
