#!/usr/bin/env python3
"""Run one frozen arm of the n=83 stacked experiment (one process, one point).

`run_schedule.py` launches this wrapper pinned to the execution CPU; the
producer inherits the affinity and a clean, whitelisted environment. The
producer's own clocks are the metrics; the wrapper's start-up, input writing
and checks are outside them. The raw producer output is printed
base64-encoded so the stdout file is the archived receipt; the last line
carries `online_ms=`, `verified=1` and the arm's fields.

Adapted from `koblitz-n83-state-fold-20261015`'s `arm.py`. Every IC arm runs
the stacked producer (`online/`) with lift_scan (`KIC_TARGET_CANON=lift`),
the Feistel order (`KIC_SCAN_ORDER=feistel`) and the prefetch pipeline
(`KIC_PROBE_PIPELINE=prefetch`); the arm's `table`, `fold`, `plant` and
`index_canon` set `KIC_ROOT_TABLE`, `KIC_STATE_FOLD`, `KIC_FOLD_PLANT` and
`KIC_INDEX_CANON`. `KIC_INDEX_DIGEST=1` adds the index digests after the
target, outside every timed interval. Kinds:

* `ic_cold`: ONE public point in a fresh process with the verified cached
  factor-log table: cold = setup (process start to setup complete: base,
  normal basis, root index, log-table load and verification, Feistel
  self-tests) + the one-target online interval.
* `ic_rank`: the same producer with NO cached table: the rank stage runs in
  process (`KIC_RANK_CANON`, `KIC_RANK_ORDER`, `KIC_RANK_PROBE`, rank seed =
  the run seed), writes its factor-log table (`KIC_LOG_TABLE_OUT`), which
  must equal B's archived table log for log, then solves one public point.
  Its cold = setup + rank stage + linear algebra + the one-target online
  interval, all in this one process.
* `rho_tuned`: A's configured rho worker (Fold/64/DP6) through the reconcile
  experiment's own runner function, unchanged, on one point.
"""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECONCILE = HERE.parent / "koblitz-n83-reconcile-20261014"
sys.path.insert(0, str(RECONCILE))
import arm as reconcile_arm  # noqa: E402  (the reconcile experiment's arm.py)

PHASES = ("target_query_ms", "target_pdp_ms", "target_relation_check_ms",
          "target_descent_ms", "target_recovery_check_ms")
BASE_ENV = dict(reconcile_arm.BASE_ENV)
STORED_FOLDED = 14_940_300
SLOTS = {False: 1 << 27, True: 1 << 26}  # (2 * 2 * stored states).next_power_of_two()


def protocol():
    return json.loads((HERE / "protocol.json").read_text())


def check(summary, record, spec, arm, point, rank):
    issues = []
    table = summary.get("factor_log_table") or {}
    want_source = "in_process_rank" if rank else "verified_cache"
    if (summary.get("base_hash") != spec["base_hash"] or summary.get("targets_solved") != 1 or
            summary.get("targets_failed") != 0 or table.get("source") != want_source or
            table.get("verified_columns") != spec["orbit_columns"]):
        issues.append("ic setup is not the expected factor-log source on the frozen base")
    if summary.get("regular_states") != spec["regular_states"]:
        issues.append("logical state count differs from 600*600*83")
    stored = STORED_FOLDED if arm["fold"] else spec["regular_states"]
    if summary.get("stored_states") != stored or summary.get("state_fold") is not arm["fold"]:
        issues.append("stored state count or fold flag differs from the arm")
    if summary.get("fold_plant") is not arm.get("plant", False):
        issues.append("planted flag differs from the arm")
    if summary.get("index_canonicalizer") != arm.get("index_canon", "selected"):
        issues.append("index canonicalizer differs from the arm")
    if summary.get("root_table") != arm["table"] or summary.get("root_table_slots") != SLOTS[arm["fold"]]:
        issues.append("root-table layout or slot count differs from the arm")
    if arm["table"] == "filter" and summary.get("root_filter_log2_bits") != spec["root_filter_log2_bits"]:
        issues.append("filter size differs from the protocol")
    if summary.get("root_bloom_enabled") is not False:
        issues.append("KIC_ROOT_BLOOM was on")
    if summary.get("root_table_entries") != spec["root_table_entries"]:
        issues.append("root table entries differ from B's index")
    digest = summary.get("index_digest") or {}
    for key in ("logical_states_blake3", "table_map_sum64", "table_map_xor64", "table_entries"):
        if digest.get(key) != spec["index_digest"][key]:
            issues.append("index digest %s differs from B's index" % key)
    if (summary.get("target_canonicalizer"), summary.get("scan_order"), summary.get("probe_pipeline")) != \
            ("lift", "feistel", "prefetch"):
        issues.append("ic ran another target canonicalizer, order or probe pipeline")
    if summary.get("scan_start_override") is not None:
        issues.append("ic ran a start override")
    if (summary.get("scan_order_selftest") or {}).get("bijection") is not True:
        issues.append("feistel self-test missing or failed")
    if summary.get("sparse_canonical_enabled") is not False:
        issues.append("index build did not use the pipeline's full scan")
    if rank:
        if summary.get("rank") != spec["orbit_columns"]:
            issues.append("rank stage did not reach full rank")
        if (summary.get("rank_canonicalizer"), summary.get("rank_order"), summary.get("rank_probe")) != \
                (arm["rank_canon"], arm["rank_order"], arm["rank_probe"]):
            issues.append("rank stage ran another canonicalizer, order or probe loop")
        if len(summary.get("rank_attempt_ns") or []) != summary.get("rank_attempts"):
            issues.append("rank attempt records incomplete")
    if record.get("group_verified") is not True or not reconcile_arm.same(record.get("target"), point):
        issues.append("ic record not verified on the supplied point")
    if record.get("root_table") != arm["table"] or record.get("probe_pipeline") != "prefetch":
        issues.append("target record ran another layout or pipeline")
    online = float(record.get("online_ms") or 0.0)
    phase_sum = sum(float(record.get(name) or 0.0) for name in PHASES)
    if record and abs(phase_sum - online) > 1e-3 * max(1.0, online):
        issues.append("ic five phases do not sum to the online interval")
    if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
        issues.append("ic setup did not finish before the online interval")
    if not arm["fold"] and record.get("skipped_symmetric_states") != 0:
        issues.append("unfolded arm skipped states")
    if not arm.get("plant") and record.get("fold_audit_probes") != 0:
        issues.append("audit probes outside the planted arm")
    if record.get("planted_rejected_found") not in (0, None):
        issues.append("a filter-rejected key was found")
    return issues


def ic(args, point, folder, rank):
    spec = protocol()["online"]
    arm = protocol()["arms"][args.arm]
    target = folder / "points.jsonl"
    target.write_text(json.dumps([str(v) for v in point], separators=(",", ":")) + "\n")
    out = folder / "ic.jsonl"
    env = dict(BASE_ENV, KIC_RANK_THREADS="1", KIC_TARGET_THREADS="1", KIC_INDEX_DIGEST="1",
               KIC_ROOT_TABLE=arm["table"],
               KIC_STATE_FOLD="1" if arm["fold"] else "0", KIC_FOLD_PLANT="1" if arm.get("plant") else "0",
               KIC_INDEX_CANON=arm.get("index_canon", "selected"),
               KIC_TARGET_CANON="lift", KIC_SCAN_ORDER="feistel", KIC_PROBE_PIPELINE="prefetch")
    logs_out = folder / "factor_logs.json"
    if rank:
        env.update(KIC_LOG_TABLE_OUT=str(logs_out), KIC_RANK_CANON=arm["rank_canon"],
                   KIC_RANK_ORDER=arm["rank_order"], KIC_RANK_PROBE=arm["rank_probe"])
    else:
        env["KIC_LOG_TABLE_IN"] = str(args.log_table)
    proc = subprocess.run([str(args.binary), str(args.base), str(target), str(args.seed), str(out)],
                          env=env, capture_output=True, text=True)
    records = reconcile_arm.rows(out.read_text()) if out.exists() else []
    summary = (reconcile_arm.rows(proc.stdout) or [{}])[-1]
    record = records[0] if records else {}
    issues = []
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("ic emitted %d target records for one point" % len(records))
    issues += check(summary, record, spec, arm, point, rank)
    logs_equal = None
    if rank:
        archived = json.loads(Path(args.log_table).read_text())["logs"]
        produced = json.loads(logs_out.read_text())["logs"] if logs_out.exists() else None
        logs_equal = produced == archived
        if not logs_equal:
            issues.append("rank-stage factor logs differ from B's archived table")
    timing = summary.get("timing_ms") or {}
    fields = {"online_ms": float(record.get("online_ms") or 0.0),
              "setup_ms": summary.get("setup_complete_ns", 0) / 1e6,
              "cold_ms": summary.get("cold_in_process_ms"),
              "rank_stage_ms": timing.get("rank_stage"),
              "index_ms": timing.get("index_build"),
              "filter_build_ms": summary.get("root_filter_build_ms"),
              "peak_rss_bytes": summary.get("peak_rss_bytes"),
              "ops": record.get("probes"), "ops_unit": "root_index_probes",
              "recovered_scalar": record.get("recovered_scalar"),
              "relation": record.get("point_indices"),
              "skipped_states": record.get("skipped_symmetric_states"),
              "audit_probes": record.get("fold_audit_probes"),
              "filter_passes": record.get("filter_passes"),
              "rank_relations_blake3": summary.get("rank_relations_blake3") if rank else None,
              "logs_equal_archived": logs_equal}
    raw = records + [summary]
    if rank and logs_out.exists():
        raw.append({"factor_log_table_written_sha256": hashlib.sha256(logs_out.read_bytes()).hexdigest()})
    return proc, raw, issues, fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--kind", required=True, choices=("ic_cold", "ic_rank", "rho_tuned"))
    parser.add_argument("--panel", required=True, help="unit id")
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", required=True, help="x,y decimal")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--log-table", type=Path)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")]
    with tempfile.TemporaryDirectory(prefix="n83-stacked-arm-") as folder:
        if args.kind == "rho_tuned":
            proc, raw, issues, fields = reconcile_arm.rho_strong_g(args, point, Path(folder))
            fields.setdefault("relation", None)
        else:
            proc, raw, issues, fields = ic(args, point, Path(folder), args.kind == "ic_rank")
    raw_bytes = json.dumps({"arm": args.arm, "kind": args.kind, "panel": args.panel,
                            "point": [str(v) for v in point], "seed": args.seed,
                            "returncode": proc.returncode, "records": raw,
                            "stderr_tail": proc.stderr[-4000:], "issues": issues, "fields": fields},
                           sort_keys=True, separators=(",", ":")).encode()
    print("raw_b64=" + base64.b64encode(raw_bytes).decode())
    verified = not issues and fields.get("recovered_scalar") is not None
    line = {"online_ms": "%.6f" % fields["online_ms"], "verified": "1" if verified else "0",
            "arm": args.arm, "panel": args.panel, "target_sha256": reconcile_arm.target_sha256(point),
            "recovered_scalar": str(fields.get("recovered_scalar")),
            "ops": str(fields.get("ops")), "ops_unit": fields.get("ops_unit"),
            "setup_ms": "%.6f" % float(fields.get("setup_ms") or 0.0),
            "raw_result_sha256": hashlib.sha256(raw_bytes).hexdigest(), "issues": str(len(issues))}
    print(" ".join("%s=%s" % item for item in line.items()))
    for issue in issues:
        print("issue: " + issue, file=sys.stderr)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
