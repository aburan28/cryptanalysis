#!/usr/bin/env python3
"""Run one frozen arm of the n=83 BL experiment on one public point.

`run_job.py` launches this wrapper pinned to the execution CPU; the producer
inherits the affinity and a clean, whitelisted environment. The producer's own
online clock is the metric; the wrapper's start-up, input writing and checks
are outside it. The raw producer output is printed base64-encoded so the
stdout file is the archived receipt; the last line carries `online_ms=`,
`verified=1`, the recovered scalar and the work count.

Kinds (the reference kinds and their checks are the reconciliation's
`arm.py`, branch `claude/n83-reconcile`, unchanged in substance):

* `ic_online_cached`: B's IC producer with B's verified factor-log table.
* `rho_rung3`, `rho_adapter`, `rho_tuned`: the three single-target rho step
  implementations (rB770, rA770, rT770), each at its own reference
  configuration and with its own per-seed jump table.
* `bl_rung3`, `bl_sg`: the BL online walk of the chosen step implementation,
  with the precomputed table loaded (BLAKE3-checked) before the target exists.
* `bl_plain_rung3`, `bl_plain_sg`: the BL binary with no table and the
  reference's jumps and DP rule; its walk must equal the reference's step for
  step (the step-identity control).

Every rho-family row is cut at B's boundary (walk start through the verified
collision; `online_ms`) and at A's (membership check + walk + generic replay;
`online_ms_at_A_boundary`) from the producers' own timers.
"""

import argparse
import base64
import hashlib
import json
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
    """A's StrongRhoG<WideGf2,u64> adapter (rA770), or A's configured tuned worker (rT770)."""
    target = write_point(folder, point)
    command = [str(args.binary), str(target), str(args.seed)]
    if args.kind == "rho_tuned":
        command.append(str(args.config))
    proc = run(command, dict(BASE_ENV))
    produced = [r for r in rows(proc.stdout) if str(r.get("schema", "")).startswith("n83-")]
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
    fields = {"online_ms": b_boundary, "online_ms_at_A_boundary": online,
              "setup_ms": (record.get("preparation_ns_excluded") or 0) / 1e6,
              "ops": outcome.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_scalar"),
              "solved_by": "single_target_rho", "table_entries_loaded": 0}
    return proc, [record], issues, fields


def rung3_env(point, lanes, dp_bits):
    return dict(BASE_ENV, KIC_RHO_RUNG="3", KIC_RHO_LANES=str(lanes), KIC_RHO_DP_BITS=str(dp_bits),
                KIC_RHO_TARGET_POINT="%d,%d" % (int(point[0]), int(point[1])))


def rung3_records(args, proc, point, lanes, dp_bits, issues):
    produced = rows(proc.stdout)
    records = [r for r in produced if r.get("kind") == "rho_ks_batch_fixture"]
    summary = ([r for r in produced if r.get("kind") == "rho_ks_batch_summary"] or [{}])[-1]
    record = records[0] if len(records) == 1 else {}
    if proc.returncode != 0:
        issues.append("rho exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("rho emitted %d fixture records" % len(records))
    if record.get("verified") is not True or not same(record.get("published_q"), point):
        issues.append("rho record not verified on the supplied point")
    if record.get("published_fixture_scalar") is not None or record.get("automorphism_size") != 166:
        issues.append("rho received a known scalar or the wrong quotient")
    if (summary.get("rung"), summary.get("lanes"), summary.get("dp_bits")) != (3, lanes, dp_bits):
        issues.append("rung 3 is not at the declared configuration")
    online = float(record.get("online_ms") or 0.0)
    if record and abs(record["walk_and_collision_ms"] + record["recovery_check_ms"] - online) > 1e-6 * max(1.0, online):
        issues.append("rho phases do not sum to the online interval")
    return produced, record, summary, online


def rho_rung3(args, point, folder):
    """B's strong rung 3 (rB770), B's exact environment."""
    proc = run([str(args.binary), "83", "1", "signed_frobenius", "1", str(args.seed)], rung3_env(point, 32, 4))
    issues = []
    produced, record, summary, online = rung3_records(args, proc, point, 32, 4, issues)
    fields = {"online_ms": online,
              "online_ms_at_A_boundary": online + float(record.get("target_generation_ms_excluded") or 0.0),
              "setup_ms": record.get("online_start_ns", 0) / 1e6,
              "ops": record.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_fixture_scalar"),
              "solved_by": "single_target_rho", "table_entries_loaded": 0}
    return proc, [record, summary], issues, fields


def bl_rung3(args, point, folder):
    """BL online on rung 3's walk (table loaded), or the step-identity control (no table)."""
    plain = args.kind == "bl_plain_rung3"
    lanes, dp_bits = (32, 4) if plain else (args.lanes, args.dp_bits)
    env = rung3_env(point, lanes, dp_bits)
    if not plain:
        env.update(KIC_BL_JUMP_SEED=str(args.bl_jump_seed), KIC_BL_TABLE_IN=str(args.table),
                   KIC_BL_TABLE_BLAKE3=args.table_blake3)
    proc = run([str(args.binary), "83", "1", "signed_frobenius", "1", str(args.seed)], env)
    issues = []
    produced, record, summary, online = rung3_records(args, proc, point, lanes, dp_bits, issues)
    bl = ([r for r in produced if r.get("kind") == "bl_online_fixture"] or [{}])[-1]
    if plain and bl.get("table_entries_loaded") != 0:
        issues.append("the plain control loaded a table")
    if not plain and (not bl.get("table_entries_loaded") or bl.get("table_entries_loaded") != args.table_entries):
        issues.append("BL arm did not load the declared table")
    if not plain and bl.get("jump_batch_seed") != args.bl_jump_seed:
        issues.append("BL arm did not use the table's jump seed")
    fields = {"online_ms": online,
              "online_ms_at_A_boundary": online + float(record.get("target_generation_ms_excluded") or 0.0),
              "setup_ms": record.get("online_start_ns", 0) / 1e6,
              "ops": record.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_fixture_scalar"),
              "solved_by": bl.get("solved_by"), "table_entries_loaded": bl.get("table_entries_loaded"),
              "table_load_ms": bl.get("table_load_ms"), "peak_rss_bytes": bl.get("peak_rss_bytes")}
    return proc, [record, bl, summary], issues, fields


def bl_sg(args, point, folder):
    """BL online on the library walk (field wide|fold), or the step-identity control."""
    plain = args.kind == "bl_plain_sg"
    command = [str(args.binary), "online", "--curve", "83,1", "--field", args.field,
               "--lanes", str(args.lanes), "--walk-seed", str(args.seed),
               "--target", "%d,%d" % (int(point[0]), int(point[1]))]
    if plain:
        command += ["--dp-bits", str(args.reference_dp_bits), "--reference-jumps"]
    else:
        command += ["--dp-bits", str(args.dp_bits), "--bl-jump-seed", str(args.bl_jump_seed),
                    "--table", str(args.table), "--table-blake3", args.table_blake3]
    proc = run(command, dict(BASE_ENV))
    record = ([r for r in rows(proc.stdout) if r.get("kind") == "bl_online"] or [{}])[-1]
    issues = []
    if proc.returncode != 0:
        issues.append("bl exit %d" % proc.returncode)
    if record.get("verified") is not True or not same(record.get("published_q"), point):
        issues.append("bl record not verified on the supplied point")
    if record.get("target_source") != "public_point" or (record.get("identity") or {}).get("automorphism_size") != 166:
        issues.append("bl received a known scalar or the wrong quotient")
    loaded = record.get("table_entries_loaded")
    if plain and loaded != 0:
        issues.append("the plain control loaded a table")
    if not plain and (not loaded or loaded != args.table_entries):
        issues.append("BL arm did not load the declared table")
    fields = {"online_ms": float(record.get("online_ms") or 0.0),
              "online_ms_at_A_boundary": float(record.get("online_ms_at_A_boundary") or 0.0),
              "setup_ms": float(record.get("setup_ms_excluded") or 0.0),
              "ops": record.get("walk_steps"), "ops_unit": "walk_steps",
              "recovered_scalar": record.get("recovered_scalar"),
              "solved_by": record.get("solved_by"), "table_entries_loaded": loaded,
              "table_load_ms": ((record.get("table") or {}).get("read_ms") or 0) +
                               ((record.get("table") or {}).get("insert_ms") or 0),
              "peak_rss_bytes": record.get("peak_rss_bytes")}
    return proc, [record], issues, fields


def ic(args, point, folder):
    """B's online producer with B's verified cached factor-log table."""
    target = write_point(folder, point)
    out = folder / "ic.jsonl"
    env = dict(BASE_ENV, KIC_RANK_THREADS="1", KIC_TARGET_THREADS="1", KIC_LOG_TABLE_IN=str(args.log_table))
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
    if (summary.get("base_hash") != args.base_hash or summary.get("targets_solved") != 1 or
            summary.get("targets_failed") != 0 or table.get("verified_columns") != args.columns):
        issues.append("ic setup is not full rank on the frozen base")
    if table.get("source") != "verified_cache":
        issues.append("ic did not use the verified factor-log cache")
    online = float(record.get("online_ms") or 0.0)
    if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
        issues.append("ic setup did not finish before the online interval")
    if record and abs(sum(float(record.get(name) or 0.0) for name in PHASES) - online) > 1e-3 * max(1.0, online):
        issues.append("ic five phases do not sum to the online interval")
    fields = {"online_ms": online, "online_ms_at_A_boundary": online,
              "setup_ms": summary.get("setup_complete_ns", 0) / 1e6, "ops": record.get("probes"),
              "ops_unit": "root_index_probes", "recovered_scalar": record.get("recovered_scalar"),
              "solved_by": "index_calculus", "table_entries_loaded": None}
    return proc, [record, summary], issues, fields


RUNNERS = {"rho_adapter": rho_strong_g, "rho_tuned": rho_strong_g, "rho_rung3": rho_rung3,
           "bl_rung3": bl_rung3, "bl_plain_rung3": bl_rung3, "bl_sg": bl_sg, "bl_plain_sg": bl_sg,
           "ic_online_cached": ic}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, help="arm id from protocol.json")
    parser.add_argument("--kind", required=True, choices=sorted(RUNNERS))
    parser.add_argument("--panel", required=True)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", required=True, help="x,y decimal")
    parser.add_argument("--seed", type=int, default=0, help="walk seed")
    parser.add_argument("--config", type=Path, help="tuned rho config")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--base-hash")
    parser.add_argument("--log-table", type=Path)
    parser.add_argument("--rank-seed", type=int, default=7)
    parser.add_argument("--columns", type=int, default=600)
    parser.add_argument("--field", choices=["wide", "fold"])
    parser.add_argument("--lanes", type=int)
    parser.add_argument("--dp-bits", type=int)
    parser.add_argument("--reference-dp-bits", type=int)
    parser.add_argument("--bl-jump-seed", type=int)
    parser.add_argument("--table", type=Path)
    parser.add_argument("--table-blake3")
    parser.add_argument("--table-entries", type=int)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")]
    with tempfile.TemporaryDirectory(prefix="n83-bl-arm-") as folder:
        proc, raw, issues, fields = RUNNERS[args.kind](args, point, Path(folder))
    raw_bytes = json.dumps({"arm": args.arm, "kind": args.kind, "panel": args.panel,
                            "point": [str(v) for v in point], "seed": args.seed,
                            "returncode": proc.returncode, "records": raw,
                            "stderr_tail": proc.stderr[-4000:], "issues": issues},
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
        "setup_ms": "%.6f" % fields["setup_ms"],
        "ops": str(fields["ops"]),
        "ops_unit": fields["ops_unit"],
        "solved_by": str(fields.get("solved_by")),
        "table_entries_loaded": str(fields.get("table_entries_loaded")),
        "table_load_ms": "%.6f" % float(fields.get("table_load_ms") or 0.0),
        "raw_result_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "issues": str(len(issues)),
    }
    print(" ".join("%s=%s" % item for item in line.items()))
    for issue in issues:
        print("issue: " + issue, file=sys.stderr)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
