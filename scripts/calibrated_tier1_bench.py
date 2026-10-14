#!/usr/bin/env python3
"""Run the serial benchmark service with mandatory Tier 1 A/A calibration.

This wrapper extends isolated_bench.py without changing its reserved Tier 0
implementation. It uses the same queue and host-wide worker lock.
"""

import json
import math
import os
from pathlib import Path
import time

import isolated_bench as base


_require_manifest = base.require_manifest
_one_run = base.one_run
_execute = base.execute
_active = None


def require_manifest(manifest):
    resources = _require_manifest(manifest)
    if base.tier(manifest) != "tier1":
        return resources
    spec = manifest.get("calibration")
    if not isinstance(spec, dict):
        raise ValueError("tier1 requires an A/A calibration specification")
    argv = spec.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        raise ValueError("calibration argv must be a nonempty string array")
    executable = Path(argv[0])
    if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("calibration argv must begin with an executable absolute file")
    if str(executable) not in manifest["artifacts"]:
        raise ValueError("calibration executable must be a frozen artifact")
    if str(Path(__file__).resolve()) not in manifest["artifacts"]:
        raise ValueError("calibrated runner wrapper must be a frozen artifact")
    expected = spec.get("expected_fields")
    if not isinstance(expected, dict) or not expected or any(
        not isinstance(key, str) or not key or not isinstance(value, str) or not value
        for key, value in expected.items()
    ):
        raise ValueError("calibration expected_fields must bind a deterministic output")
    spread = spec.get("max_spread_bps")
    if not isinstance(spread, int) or isinstance(spread, bool) or not 1 <= spread <= 2000:
        raise ValueError("calibration max_spread_bps must be an integer in [1, 2000]")
    timeout = spec.get("timeout_s")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 0 < timeout <= manifest["timeout_s"]:
        raise ValueError("calibration timeout_s must be within the benchmark cap")
    return resources


def calibration_issues(rows, spec):
    """Check two A/A runs before and two after one candidate/reference pair."""
    if len(rows) != 4:
        return ["A/A calibration requires four runs"], None
    issues = []
    for row in rows:
        if row.get("status") != "valid":
            issues.append("A/A calibration process invalid")
        fields = row.get("fields") or {}
        if any(fields.get(key) != value for key, value in spec["expected_fields"].items()):
            issues.append("A/A calibration output mismatch")
    times = [row.get("online_ms") for row in rows]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
           for value in times):
        issues.append("A/A calibration duration missing")
        return sorted(set(issues)), None
    spread = max(times) / min(times)
    if spread > 1 + spec["max_spread_bps"] / 10_000:
        issues.append("A/A calibration spread exceeds frozen limit")
    return sorted(set(issues)), spread


def timed_run(argv, manifest, cpus, nodes, cgroup, folder, serial):
    start_utc = time.time_ns()
    start_mono = time.monotonic_ns()
    row = _one_run(argv, manifest, cpus, nodes, cgroup, folder, serial)
    stop_mono = time.monotonic_ns()
    stop_utc = time.time_ns()
    row.update({"attempt_start_utc_ns": start_utc,
                "attempt_stop_utc_ns": stop_utc,
                "attempt_start_monotonic_ns": start_mono,
                "attempt_stop_monotonic_ns": stop_mono,
                "attempt_elapsed_ms": (stop_mono - start_mono) / 1_000_000})
    return row


def append_jsonl(path, value):
    with path.open("a") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def calibration_pair(manifest, cpus, nodes, cgroup, folder, phase):
    state = _active
    spec = manifest["calibration"]
    folder = folder / "calibration"
    folder.mkdir(exist_ok=True)
    cal_manifest = dict(manifest, metric_field="online_ms", timeout_s=spec["timeout_s"])
    rows = []
    for _ in range(2):
        state["calibration_serial"] += 1
        row = timed_run(spec["argv"], cal_manifest, cpus, nodes, cgroup,
                        folder, state["calibration_serial"])
        row.update({"phase": phase, "pair_index": state["pair_index"]})
        append_jsonl(folder.parent / "calibrations.jsonl", row)
        rows.append(row)
    return rows


def finish_calibration(manifest, folder, before, after):
    state = _active
    rows = before + after
    issues, spread = calibration_issues(rows, manifest["calibration"])
    record = {"pair_index": state["pair_index"],
              "calibration_serials": [row["serial"] for row in rows],
              "online_ms": [row.get("online_ms") for row in rows],
              "max_over_min": spread,
              "max_spread_bps": manifest["calibration"]["max_spread_bps"],
              "status": "valid" if not issues else "invalid", "issues": issues}
    append_jsonl(folder / "calibration_pairs.jsonl", record)
    state["pairs"].append(record)
    state["first"] = None
    state["pair_index"] += 1
    return issues


def one_run(argv, manifest, cpus, nodes, cgroup, folder, serial):
    if _active is None or base.tier(manifest) != "tier1":
        return timed_run(argv, manifest, cpus, nodes, cgroup, folder, serial)
    state = _active
    if state["first"] is None:
        before = calibration_pair(manifest, cpus, nodes, cgroup, folder, "before")
        row = timed_run(argv, manifest, cpus, nodes, cgroup, folder, serial)
        state["first"] = before
        if row["status"] != "valid":
            after = calibration_pair(manifest, cpus, nodes, cgroup, folder, "after")
            issues = finish_calibration(manifest, folder, before, after)
            row["issues"] = row.get("issues", []) + issues
        return row
    before = state["first"]
    row = timed_run(argv, manifest, cpus, nodes, cgroup, folder, serial)
    after = calibration_pair(manifest, cpus, nodes, cgroup, folder, "after")
    issues = finish_calibration(manifest, folder, before, after)
    if issues:
        row["status"] = "invalid"
        row["issues"] = row.get("issues", []) + issues
    return row


def execute(manifest, output):
    global _active
    if base.tier(manifest) != "tier1":
        return _execute(manifest, output)
    if _active is not None:
        raise RuntimeError("calibrated runner is already executing a job")
    _active = {"first": None, "pair_index": 0, "calibration_serial": 0, "pairs": []}
    try:
        summary = _execute(manifest, output)
        ledger = output / "calibrations.jsonl"
        summary["calibration_pairs"] = len(_active["pairs"])
        summary["calibration_passed_pairs"] = sum(
            record["status"] == "valid" for record in _active["pairs"])
        summary["calibration_receipt_sha256"] = base.sha256(ledger) if ledger.exists() else None
        summary["calibrated_runner_sha256"] = base.sha256(Path(__file__))
        summary["qualification_scope"] = "one_case_stage"
        # A single frozen case cannot satisfy the five-distinct-target gate.
        summary["speedup_qualified"] = False
        summary["paired_speedup"] = None
        base.json_write(output / "summary.json", summary)
        return summary
    finally:
        _active = None


base.require_manifest = require_manifest
base.one_run = one_run
base.execute = execute


if __name__ == "__main__":
    base.main()
