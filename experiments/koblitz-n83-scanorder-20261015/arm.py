#!/usr/bin/env python3
"""Run one frozen arm of the n=83 scan-order experiment.

`run_schedule.py` launches this wrapper pinned to the execution CPU; the
producer inherits the affinity and a clean, whitelisted environment. The
producer's own clock is the metric; the wrapper's start-up, input writing and
checks are outside it. The raw producer output is printed base64-encoded so
the stdout file is the archived receipt; the last line carries `online_ms=`,
`verified=1` and the arm's identity fields.

Adapted from `../koblitz-n83-liftscan-20261015/arm.py` (branch
`claude/n83-liftscan`). Kinds:

* `ic`: the one-target IC online producer (`online/`, B's log-cache producer
  plus the `KIC_SCAN_ORDER` selector) on one public point with the verified
  cached factor-log table. `online_ms` is the producer's own five-phase
  online interval. `--order` picks the state order; `--planted` sets
  `KIC_SCAN_START_OVERRIDE` from `inputs/planted_starts.json` and requires
  the exact predicted probe count and B's relation.
* `ic_multi`: the same producer on a slice of the held-out panel
  (`inputs/heldout_targets.json`), one process, each target with its own
  one-target online interval (secondary panel H). Every target must verify.
* `rho_tuned`: A's configured rho worker (Fold/64/DP6) through the reconcile
  experiment's own runner function, unchanged.
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


def protocol():
    return json.loads((HERE / "protocol.json").read_text())


def check_setup(summary, spec, order, override, targets):
    issues = []
    table = summary.get("factor_log_table") or {}
    if (summary.get("base_hash") != spec["base_hash"] or summary.get("targets_solved") != targets or
            summary.get("targets_failed") != 0 or table.get("source") != "verified_cache" or
            table.get("verified_columns") != spec["orbit_columns"]):
        issues.append("ic setup is not the verified cached table on the frozen base")
    if summary.get("regular_states") != spec["regular_states"]:
        issues.append("ic state count differs from 600*600*83")
    if summary.get("scan_order") != order or summary.get("scan_start_override") != override:
        issues.append("ic ran another scan order or start")
    if (summary.get("scan_order_selftest") or {}).get("bijection") is not True:
        issues.append("feistel bijection self-test missing or failed")
    if summary.get("sparse_canonical_enabled") is not False:
        issues.append("index build did not use the pipeline's full scan")
    return issues


def check_record(record, summary, point, order, override):
    issues = []
    if record.get("group_verified") is not True or not reconcile_arm.same(record.get("target"), point):
        issues.append("ic record not verified on the supplied point")
    if record.get("scan_order") != order or record.get("scan_start_override") != override:
        issues.append("ic record ran another scan order or start")
    online = float(record.get("online_ms") or 0.0)
    phase_sum = sum(float(record.get(name) or 0.0) for name in PHASES)
    if record and abs(phase_sum - online) > 1e-3 * max(1.0, online):
        issues.append("ic five phases do not sum to the online interval")
    if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
        issues.append("ic setup did not finish before the online interval")
    return issues


def run_producer(args, folder, points, order, override):
    target = folder / "points.jsonl"
    target.write_text("".join(json.dumps([str(v) for v in p], separators=(",", ":")) + "\n" for p in points))
    out = folder / "ic.jsonl"
    env = dict(BASE_ENV, KIC_RANK_THREADS="1", KIC_TARGET_THREADS="1",
               KIC_LOG_TABLE_IN=str(args.log_table), KIC_SCAN_ORDER=order)
    if override is not None:
        env["KIC_SCAN_START_OVERRIDE"] = str(override)
    proc = subprocess.run([str(args.binary), str(args.base), str(target), "7", str(out)],
                          env=env, capture_output=True, text=True)
    records = reconcile_arm.rows(out.read_text()) if out.exists() else []
    summary = (reconcile_arm.rows(proc.stdout) or [{}])[-1]
    return proc, records, summary


def ic(args, point, folder):
    spec = protocol()["online"]
    override, planted = None, None
    if args.planted:
        planted = json.loads((HERE / "inputs" / "planted_starts.json").read_text())["points"][args.panel]
        override = planted["start_override"]
    proc, records, summary = run_producer(args, folder, [point], args.order, override)
    record = records[0] if len(records) == 1 else {}
    issues = []
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("ic emitted %d target records" % len(records))
    issues += check_setup(summary, spec, args.order, override, 1)
    issues += check_record(record, summary, point, args.order, override)
    if planted is not None:
        if record.get("probes") != planted["expected_probes"]:
            issues.append("planted probes %r differ from the predicted %r" %
                          (record.get("probes"), planted["expected_probes"]))
        if record.get("point_indices") != planted["relation_point_indices"]:
            issues.append("planted relation differs from B's archived relation")
    fields = {"online_ms": float(record.get("online_ms") or 0.0),
              "pdp_ms": float(record.get("target_pdp_ms") or 0.0),
              "setup_ms": summary.get("setup_complete_ns", 0) / 1e6,
              "ops": record.get("probes"), "ops_unit": "root_index_probes",
              "root_calls": record.get("root_calls"),
              "relation": json.dumps(record.get("point_indices"), separators=(",", ":")),
              "recovered_scalar": record.get("recovered_scalar")}
    return proc, [record, summary], issues, fields


def ic_multi(args, folder):
    spec = protocol()["online"]
    panel = json.loads((HERE / "inputs" / "heldout_targets.json").read_text())["points"]
    lo, hi = (int(v) for v in args.slice.split(":"))
    points = [[int(v) for v in e["point"]] for e in panel[lo:hi]]
    proc, records, summary = run_producer(args, folder, points, args.order, None)
    issues = []
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != len(points):
        issues.append("ic emitted %d target records for %d points" % (len(records), len(points)))
    issues += check_setup(summary, spec, args.order, None, len(points))
    for index, (record, point) in enumerate(zip(records, points)):
        issues += ["target %d: %s" % (lo + index, issue)
                   for issue in check_record(record, summary, point, args.order, None)]
    per_target = [{"seed": lo + i, "online_ms": r.get("online_ms"), "probes": r.get("probes"),
                   "root_calls": r.get("root_calls"), "recovered_scalar": r.get("recovered_scalar"),
                   "relation": r.get("point_indices")} for i, r in enumerate(records)]
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
    parser.add_argument("--kind", required=True, choices=("ic", "ic_multi", "rho_tuned"))
    parser.add_argument("--panel", required=True)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", help="x,y decimal (ic, rho)")
    parser.add_argument("--order", help="ic KIC_SCAN_ORDER")
    parser.add_argument("--planted", action="store_true", help="ic planted start override")
    parser.add_argument("--slice", help="ic_multi held-out index range lo:hi")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--log-table", type=Path)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")] if args.point else None
    with tempfile.TemporaryDirectory(prefix="n83-scanorder-arm-") as folder:
        if args.kind == "ic":
            proc, raw, issues, fields = ic(args, point, Path(folder))
        elif args.kind == "ic_multi":
            proc, raw, issues, fields = ic_multi(args, Path(folder))
        else:
            proc, raw, issues, fields = rho_tuned(args, point, Path(folder))
            fields.setdefault("relation", None)
    raw_bytes = json.dumps({"arm": args.arm, "kind": args.kind, "panel": args.panel,
                            "point": [str(v) for v in point] if point else None,
                            "order": args.order, "planted": args.planted, "slice": args.slice,
                            "seed": args.seed, "returncode": proc.returncode, "records": raw,
                            "stderr_tail": proc.stderr[-4000:], "issues": issues},
                           sort_keys=True, separators=(",", ":")).encode()
    print("raw_b64=" + base64.b64encode(raw_bytes).decode())
    verified = not issues and fields.get("recovered_scalar") is not None
    line = {"online_ms": "%.6f" % fields["online_ms"], "verified": "1" if verified else "0",
            "arm": args.arm, "panel": args.panel,
            "target_sha256": reconcile_arm.target_sha256(point) if point else "heldout_" + str(args.slice),
            "recovered_scalar": str(fields.get("recovered_scalar")),
            "ops": str(fields.get("ops")), "ops_unit": fields.get("ops_unit"),
            "raw_result_sha256": hashlib.sha256(raw_bytes).hexdigest(), "issues": str(len(issues))}
    for key in ("pdp_ms", "setup_ms"):
        if key in fields:
            line[key] = "%.6f" % fields[key]
    for key in ("relation", "root_calls", "targets", "per_target_sha256"):
        if fields.get(key) is not None:
            line[key] = str(fields[key])
    print(" ".join("%s=%s" % item for item in line.items()))
    for issue in issues:
        print("issue: " + issue, file=sys.stderr)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
