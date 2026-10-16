#!/usr/bin/env python3
"""Run one frozen arm of the n=83 combined (lift_scan x Feistel order) experiment.

`run_schedule.py` launches this wrapper pinned to the execution CPU; the
producer inherits the affinity and a clean, whitelisted environment. The
producer's own clock is the metric; the wrapper's start-up, input writing and
checks are outside it. The raw producer output is printed base64-encoded so
the stdout file is the archived receipt; the last line carries `online_ms=`,
`verified=1` and the arm's identity fields.

Adapted from `claude/n83-scan-order`'s `arm.py` (itself `claude/n83-liftscan`'s).
Kinds:

* `ic_multi`: the combined IC online producer (`online/`, B's log-cache
  producer plus the `KIC_TARGET_CANON` and `KIC_SCAN_ORDER` selectors) on a
  slice of one panel, one process, with the verified cached factor-log
  table. Every target has its own one-target online interval (the
  producer's five phases, query hash to recovery check); no target-dependent
  work is shared between targets. `--canon` and `--order` pick the arm.
  Every target must verify.
* `rho_tuned`: A's configured rho worker (Fold/64/DP6) through the reconcile
  experiment's own runner function, unchanged, on one point.

Panels (`--panel-file`): `primary` (`inputs/primary_targets.json`),
`old_heldout` (`inputs/old_heldout_targets.json`), and `old17` (Q0 then B's
16 fresh points w00..w15, from B's `inputs/targets.json`).
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
from panels import panel_points  # noqa: E402  (this directory, sys.path[1])

PHASES = ("target_query_ms", "target_pdp_ms", "target_relation_check_ms",
          "target_descent_ms", "target_recovery_check_ms")
BASE_ENV = dict(reconcile_arm.BASE_ENV)


def protocol():
    return json.loads((HERE / "protocol.json").read_text())


def check_setup(summary, spec, canon, order, targets):
    issues = []
    table = summary.get("factor_log_table") or {}
    if (summary.get("base_hash") != spec["base_hash"] or summary.get("targets_solved") != targets or
            summary.get("targets_failed") != 0 or table.get("source") != "verified_cache" or
            table.get("verified_columns") != spec["orbit_columns"]):
        issues.append("ic setup is not the verified cached table on the frozen base")
    if summary.get("regular_states") != spec["regular_states"]:
        issues.append("ic state count differs from 600*600*83")
    if summary.get("target_canonicalizer") != canon:
        issues.append("ic ran another target canonicalizer")
    if summary.get("scan_order") != order or summary.get("scan_start_override") is not None:
        issues.append("ic ran another scan order or start")
    if (summary.get("scan_order_selftest") or {}).get("bijection") is not True:
        issues.append("feistel bijection self-test missing or failed")
    if summary.get("sparse_canonical_enabled") is not False:
        issues.append("index build did not use the pipeline's full scan")
    return issues


def check_record(record, summary, point, canon, order):
    issues = []
    if record.get("group_verified") is not True or not reconcile_arm.same(record.get("target"), point):
        issues.append("ic record not verified on the supplied point")
    if record.get("target_canonicalizer") != canon:
        issues.append("ic record ran another target canonicalizer")
    if record.get("scan_order") != order or record.get("scan_start_override") is not None:
        issues.append("ic record ran another scan order or start")
    online = float(record.get("online_ms") or 0.0)
    phase_sum = sum(float(record.get(name) or 0.0) for name in PHASES)
    if record and abs(phase_sum - online) > 1e-3 * max(1.0, online):
        issues.append("ic five phases do not sum to the online interval")
    if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
        issues.append("ic setup did not finish before the online interval")
    return issues


def ic_multi(args, folder):
    spec = protocol()["online"]
    lo, hi = (int(v) for v in args.slice.split(":"))
    units = panel_points(args.panel_file)[lo:hi]
    points = [p for _, p in units]
    target = folder / "points.jsonl"
    target.write_text("".join(json.dumps([str(v) for v in p], separators=(",", ":")) + "\n" for p in points))
    out = folder / "ic.jsonl"
    env = dict(BASE_ENV, KIC_RANK_THREADS="1", KIC_TARGET_THREADS="1",
               KIC_LOG_TABLE_IN=str(args.log_table), KIC_TARGET_CANON=args.canon, KIC_SCAN_ORDER=args.order)
    proc = subprocess.run([str(args.binary), str(args.base), str(target), "7", str(out)],
                          env=env, capture_output=True, text=True)
    records = reconcile_arm.rows(out.read_text()) if out.exists() else []
    summary = (reconcile_arm.rows(proc.stdout) or [{}])[-1]
    issues = []
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != len(points):
        issues.append("ic emitted %d target records for %d points" % (len(records), len(points)))
    issues += check_setup(summary, spec, args.canon, args.order, len(points))
    for (unit, point), record in zip(units, records):
        issues += ["target %s: %s" % (unit, issue)
                   for issue in check_record(record, summary, point, args.canon, args.order)]
    per_target = [{"unit": unit, "online_ms": r.get("online_ms"), "probes": r.get("probes"),
                   "root_calls": r.get("root_calls"), "recovered_scalar": r.get("recovered_scalar"),
                   "relation": r.get("point_indices")} for (unit, _), r in zip(units, records)]
    fields = {"online_ms": sum(float(r.get("online_ms") or 0.0) for r in records),
              "setup_ms": summary.get("setup_complete_ns", 0) / 1e6,
              "ops": sum(int(r.get("probes") or 0) for r in records), "ops_unit": "root_index_probes_sum",
              "recovered_scalar": "per_target", "targets": len(records),
              "per_target_sha256": hashlib.sha256(json.dumps(per_target, sort_keys=True).encode()).hexdigest()}
    return proc, records + [summary], issues, fields


def rho_tuned(args, point, folder):
    """A's configured worker through the reconcile experiment's own runner."""
    args.kind = "rho_tuned"
    return reconcile_arm.rho_strong_g(args, point, folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--kind", required=True, choices=("ic_multi", "rho_tuned"))
    parser.add_argument("--panel", required=True, help="unit id (rho) or segment slice id (ic_multi)")
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", help="x,y decimal (rho)")
    parser.add_argument("--panel-file", choices=("primary", "old_heldout", "old17"), help="ic_multi panel")
    parser.add_argument("--slice", help="ic_multi index range lo:hi within the panel")
    parser.add_argument("--canon", help="ic KIC_TARGET_CANON")
    parser.add_argument("--order", help="ic KIC_SCAN_ORDER")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--log-table", type=Path)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")] if args.point else None
    with tempfile.TemporaryDirectory(prefix="n83-combined-arm-") as folder:
        if args.kind == "ic_multi":
            proc, raw, issues, fields = ic_multi(args, Path(folder))
        else:
            proc, raw, issues, fields = rho_tuned(args, point, Path(folder))
            fields.setdefault("relation", None)
    raw_bytes = json.dumps({"arm": args.arm, "kind": args.kind, "panel": args.panel,
                            "point": [str(v) for v in point] if point else None,
                            "panel_file": args.panel_file, "slice": args.slice,
                            "canon": args.canon, "order": args.order,
                            "seed": args.seed, "returncode": proc.returncode, "records": raw,
                            "stderr_tail": proc.stderr[-4000:], "issues": issues},
                           sort_keys=True, separators=(",", ":")).encode()
    print("raw_b64=" + base64.b64encode(raw_bytes).decode())
    verified = not issues and fields.get("recovered_scalar") is not None
    line = {"online_ms": "%.6f" % fields["online_ms"], "verified": "1" if verified else "0",
            "arm": args.arm, "panel": args.panel,
            "target_sha256": (reconcile_arm.target_sha256(point) if point
                              else "%s_%s" % (args.panel_file, args.slice)),
            "recovered_scalar": str(fields.get("recovered_scalar")),
            "ops": str(fields.get("ops")), "ops_unit": fields.get("ops_unit"),
            "raw_result_sha256": hashlib.sha256(raw_bytes).hexdigest(), "issues": str(len(issues))}
    if "setup_ms" in fields:
        line["setup_ms"] = "%.6f" % fields["setup_ms"]
    for key in ("targets", "per_target_sha256"):
        if fields.get(key) is not None:
            line[key] = str(fields[key])
    print(" ".join("%s=%s" % item for item in line.items()))
    for issue in issues:
        print("issue: " + issue, file=sys.stderr)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
