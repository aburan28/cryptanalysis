#!/usr/bin/env python3
"""Run one frozen arm of the n=83 lift_scan experiment.

`run_schedule.py` launches this wrapper pinned to the execution CPU; the
producer inherits the affinity and a clean, whitelisted environment. The
producer's own clock is the metric; the wrapper's start-up, input writing and
checks are outside it. The raw producer output is printed base64-encoded so
the stdout file is the archived receipt; the last line carries `online_ms=`,
`verified=1` and the arm's identity fields.

Kinds:

* `stage`: the E-1 packed-index stage binary (`stage/`), one frozen target,
  2,000,000 pair states. `online_ms` is the stage's bounded target interval
  (`timing_ns.target_pdp_and_native_check`); `canon_ns` is its
  canonicalization phase (`timing_ns.target_cycle_canonical`). Each arm must
  reproduce the frozen E-1 pair certificate and its canonicalizer's frozen
  operation counts.
* `ic`: the one-target IC online producer (`online/`, B's log-cache producer
  plus the `KIC_TARGET_CANON` selector) on one public point with the verified
  cached factor-log table. `online_ms` is the producer's own five-phase
  online interval.
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
EXPERIMENTS = HERE.parent
E1 = EXPERIMENTS / "koblitz-n83-index-design-20260929"
CANONICAL = E1 / "packed_index_e1_canonical_20261009"
INPUTS = E1 / "adaptive_all_orientations_20261004" / "inputs"
ADAPTER = E1 / "packed_index_e1_isolated_replay_20261010"
RECONCILE = EXPERIMENTS / "koblitz-n83-reconcile-20261014"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(RECONCILE))
from benchmark_stage import PAIR_FIELDS, canonical as canonical_json  # noqa: E402
import arm as reconcile_arm  # noqa: E402  (the reconcile experiment's arm.py)

PHASES = ("target_query_ms", "target_pdp_ms", "target_relation_check_ms",
          "target_descent_ms", "target_recovery_check_ms")
BASE_ENV = dict(reconcile_arm.BASE_ENV)
STAGE_CANONICALIZER = {
    "packed_bucket22": "full_scan",
    "packed_bucket22_fastcanon": "zero_gap_variant_b",
    "packed_bucket22_liftcanon": "lift_scan_two_limb",
    "packed_bucket22_fastcanon_x2": "zero_gap_variant_b_plus_planted_second_call",
    "packed_bucket22_verifycanon": "verify_full_vs_gap_vs_lift",
}


def protocol():
    return json.loads((HERE / "protocol.json").read_text())


def stage(args, folder):
    spec = protocol()["stage"]
    out = folder / "stage.json"
    command = [str(args.binary), str(CANONICAL / "stage_manifest.json"),
               str(INPUTS / "n83_onb_poly_bridge.json"), str(INPUTS / "n83_x_representatives.bin"),
               str(spec["pair_state_cap"]), str(spec["peak_rss_cap_mib"]), args.mode, str(out)]
    proc = subprocess.run(command, env=dict(BASE_ENV), capture_output=True, text=True)
    raw = out.read_bytes() if out.exists() else b"{}"
    result = json.loads(raw)
    issues = []
    if proc.returncode != 0:
        issues.append("stage exit %d" % proc.returncode)
    if result.get("status") != "state_cap_no_relation":
        issues.append("unexpected stage status %r" % result.get("status"))
    if result.get("index_mode") != args.mode or result.get("canonicalizer") != STAGE_CANONICALIZER[args.mode]:
        issues.append("stage ran another canonicalizer")
    certificate = None
    if result.get("status"):
        certificate = hashlib.sha256(canonical_json({name: result.get(name) for name in PAIR_FIELDS})).hexdigest()
        if certificate != spec["frozen_pair_certificate"]:
            issues.append("pair certificate differs from the frozen E-1 certificate")
    expected_ops = spec["expected_canonical_rotation_steps"][args.mode]
    ops = result.get("operation_counts") or {}
    got_ops = [(ops.get(phase) or {}).get("canonical_rotation_steps") for phase in ("index_build", "target_pdp_and_native_check")]
    if got_ops != expected_ops:
        issues.append("canonical rotation counts %r differ from frozen %r" % (got_ops, expected_ops))
    if (result.get("native_s3_generator_target_control") or {}).get("status") != "PASS":
        issues.append("native generator/target control failed")
    if int(result.get("peak_rss_bytes") or 0) > spec["peak_rss_cap_mib"] * (1 << 20):
        issues.append("stage exceeded the RSS cap")
    timing = {key: int(value) for key, value in (result.get("timing_ns") or {}).items()}
    if timing:
        if timing["target_query_preparation"] + timing["target_s3_batch"] + timing["target_partner_check"] > timing["target_pdp_and_native_check"]:
            issues.append("stage phase accounting exceeds the target stage")
        if timing["target_cycle_canonical"] + timing["target_exact_lookup"] > timing["target_partner_check"]:
            issues.append("canonical + lookup exceed the partner check")
    else:
        issues.append("missing timing")
    verification = result.get("canonical_verification")
    if args.mode == "packed_bucket22_verifycanon":
        if (not verification or verification.get("words") != spec["verify_words"] or
                verification.get("gap_mismatches_vs_full") != 0 or verification.get("lift_mismatches_vs_full") != 0):
            issues.append("stage canonical verification failed: %r" % (verification,))
    fields = {"online_ms": timing.get("target_pdp_and_native_check", 0) / 1e6,
              "canon_ms": timing.get("target_cycle_canonical", 0) / 1e6,
              "s3_batch_ms": timing.get("target_s3_batch", 0) / 1e6,
              "lookup_ms": timing.get("target_exact_lookup", 0) / 1e6,
              "pair_certificate": certificate, "ops": got_ops[1], "ops_unit": "canonical_rotation_steps",
              "recovered_scalar": "none_bounded_stage", "words_verified": (verification or {}).get("words")}
    return proc, [result], issues, fields


def ic(args, point, folder):
    spec = protocol()["online"]
    target = reconcile_arm.write_point(folder, point)
    out = folder / "ic.jsonl"
    env = dict(BASE_ENV, KIC_RANK_THREADS="1", KIC_TARGET_THREADS="1",
               KIC_LOG_TABLE_IN=str(args.log_table), KIC_TARGET_CANON=args.canon)
    proc = subprocess.run([str(args.binary), str(args.base), str(target), "7", str(out)],
                          env=env, capture_output=True, text=True)
    records = reconcile_arm.rows(out.read_text()) if out.exists() else []
    summary = (reconcile_arm.rows(proc.stdout) or [{}])[-1]
    record = records[0] if len(records) == 1 else {}
    issues = []
    if proc.returncode != 0:
        issues.append("ic exit %d" % proc.returncode)
    if len(records) != 1:
        issues.append("ic emitted %d target records" % len(records))
    if record.get("group_verified") is not True or not reconcile_arm.same(record.get("target"), point):
        issues.append("ic record not verified on the supplied point")
    table = summary.get("factor_log_table") or {}
    if (summary.get("base_hash") != spec["base_hash"] or summary.get("targets_solved") != 1 or
            summary.get("targets_failed") != 0 or table.get("source") != "verified_cache" or
            table.get("verified_columns") != spec["orbit_columns"]):
        issues.append("ic setup is not the verified cached table on the frozen base")
    if record.get("target_canonicalizer") != args.canon or summary.get("target_canonicalizer") != args.canon:
        issues.append("ic ran another target canonicalizer")
    if summary.get("sparse_canonical_enabled") is not False:
        issues.append("index build did not use the pipeline's full scan")
    if args.canon == "verify":
        check = record.get("target_canon_verification") or {}
        if (check.get("words") != record.get("probes") or check.get("gap_mismatches_vs_full") != 0 or
                check.get("lift_mismatches_vs_full") != 0):
            issues.append("online canonical verification failed: %r" % (check,))
    online = float(record.get("online_ms") or 0.0)
    phase_sum = sum(float(record.get(name) or 0.0) for name in PHASES)
    if record and abs(phase_sum - online) > 1e-3 * max(1.0, online):
        issues.append("ic five phases do not sum to the online interval")
    if record and not summary.get("setup_complete_ns", 0) < record.get("online_start_ns", 0):
        issues.append("ic setup did not finish before the online interval")
    fields = {"online_ms": online, "pdp_ms": float(record.get("target_pdp_ms") or 0.0),
              "setup_ms": summary.get("setup_complete_ns", 0) / 1e6,
              "ops": record.get("probes"), "ops_unit": "root_index_probes",
              "relation": json.dumps(record.get("point_indices"), separators=(",", ":")),
              "recovered_scalar": record.get("recovered_scalar"),
              "words_verified": (record.get("target_canon_verification") or {}).get("words")}
    return proc, [record, summary], issues, fields


def rho_tuned(args, point, folder):
    """A's configured worker through the reconcile experiment's own runner."""
    args.kind = "rho_tuned"
    return reconcile_arm.rho_strong_g(args, point, folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--kind", required=True, choices=("stage", "ic", "rho_tuned"))
    parser.add_argument("--panel", required=True)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--point", help="x,y decimal (ic, rho)")
    parser.add_argument("--mode", help="stage index mode")
    parser.add_argument("--canon", help="ic KIC_TARGET_CANON")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--log-table", type=Path)
    args = parser.parse_args()
    point = [int(v) for v in args.point.split(",")] if args.point else None
    with tempfile.TemporaryDirectory(prefix="n83-liftscan-arm-") as folder:
        if args.kind == "stage":
            proc, raw, issues, fields = stage(args, Path(folder))
        elif args.kind == "ic":
            proc, raw, issues, fields = ic(args, point, Path(folder))
        else:
            proc, raw, issues, fields = rho_tuned(args, point, Path(folder))
            fields.setdefault("relation", None)
    raw_bytes = json.dumps({"arm": args.arm, "kind": args.kind, "panel": args.panel,
                            "point": [str(v) for v in point] if point else None,
                            "mode": args.mode, "canon": args.canon, "seed": args.seed,
                            "returncode": proc.returncode, "records": raw,
                            "stderr_tail": proc.stderr[-4000:], "issues": issues},
                           sort_keys=True, separators=(",", ":")).encode()
    print("raw_b64=" + base64.b64encode(raw_bytes).decode())
    verified = not issues and fields.get("recovered_scalar") is not None
    line = {"online_ms": "%.6f" % fields["online_ms"], "verified": "1" if verified else "0",
            "arm": args.arm, "panel": args.panel,
            "target_sha256": reconcile_arm.target_sha256(point) if point else "e1_frozen_target",
            "recovered_scalar": str(fields.get("recovered_scalar")),
            "ops": str(fields.get("ops")), "ops_unit": fields.get("ops_unit"),
            "raw_result_sha256": hashlib.sha256(raw_bytes).hexdigest(), "issues": str(len(issues))}
    for key in ("canon_ms", "s3_batch_ms", "lookup_ms", "pdp_ms", "setup_ms"):
        if key in fields:
            line[key] = "%.6f" % fields[key]
    for key in ("pair_certificate", "relation", "words_verified"):
        if fields.get(key) is not None:
            line[key] = str(fields[key])
    print(" ".join("%s=%s" % item for item in line.items()))
    for issue in issues:
        print("issue: " + issue, file=sys.stderr)
    sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
