#!/usr/bin/env python3
"""A deliberately loose whole-campaign CPU-capacity ceiling for n=83.

This is a resource envelope, not an instruction counter or a calibrated
field-operation total. The assumptions are emitted with the result.
"""

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = HERE / "runs"
ACCOUNTING = HERE / "n83_verified_solve_accounting.json"
SCREEN = HERE / "n83_full_spill_screen.json"
OUTPUT = HERE / "n83_verified_solve_resource_envelope.json"
UTC = dt.timezone.utc
WINDOW_START = dt.datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
WINDOW_END = dt.datetime(2026, 10, 1, 15, 30, tzinfo=UTC)
CORES_PER_RECORD = 16
EXTRA_LANES = 8
CLOCK_HZ_CEILING = 7_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc(iso):
    value = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    assert value.tzinfo is not None
    return value.astimezone(UTC)


def repo_path(path):
    return str(path.relative_to(REPO))


def worker_counts(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "query_workers" and isinstance(child, int):
                yield child
            yield from worker_counts(child)
    elif isinstance(value, list):
        for child in value:
            yield from worker_counts(child)


def main():
    accounting = json.loads(ACCOUNTING.read_text())
    screen = json.loads(SCREEN.read_text())
    assert accounting["curve_id"] == screen["curve_id"]
    assert accounting["one_public_target"] == screen["public_target"]
    assert accounting["isogeny"] == screen["isogeny"] == "none"
    digest = screen["factor_base"]["enumerated_set_sha256"]
    assert accounting["factor_base_enumerated_set_sha256"] == digest
    assert accounting["independent_sage_scalar_replay"]
    assert accounting["natural_four_point_relation_count"] == 1
    window_seconds = math.ceil((WINDOW_END - WINDOW_START).total_seconds())
    assert window_seconds == 228600

    direct_paths = {row["path"] for row in accounting["direct_attempts"]}
    assert len(direct_paths) == len(accounting["direct_attempts"]) == 155
    direct = []
    observed_worker_max = 0
    for listed in accounting["direct_attempts"]:
        path = REPO / listed["path"]
        assert sha(path) == listed["sha256"]
        row = json.loads(path.read_text())
        observed_worker_max = max(observed_worker_max,
                                  *worker_counts(row), 0)
        start = utc(row["started_at_utc"])
        assert WINDOW_START <= start <= WINDOW_END
        finished = row.get("finished_at_utc")
        if finished is None:
            end = WINDOW_END
            end_basis = "campaign_cutoff_for_missing_terminal_time"
        else:
            end = utc(finished)
            assert start <= end <= WINDOW_END
            end_basis = "receipt_finish_time"
        recorded_wall = max(
            float(row.get("wrapper_subprocess_wall_seconds") or 0),
            float(row.get("native_subprocess_wall_seconds") or 0),
            float(row.get("target_online_seconds") or 0),
        )
        charged_seconds = math.ceil(max((end - start).total_seconds(),
                                        recorded_wall))
        assert 0 <= charged_seconds <= window_seconds + 1
        direct.append({
            "path": listed["path"], "sha256": listed["sha256"],
            "charged_host_seconds": charged_seconds,
            "end_basis": end_basis,
        })

    other = []
    target_marker = str(screen["public_target"][0])
    for path in sorted(RUNS.rglob("*.json")):
        try:
            source = path.read_text()
            if target_marker not in source:
                continue
            row = json.loads(source)
        except (UnicodeDecodeError, ValueError):
            continue
        if not isinstance(row, dict):
            continue
        factor_base = row.get("factor_base") or {}
        base_digest = (row.get("factor_base_enumerated_set_sha256") or
                       factor_base.get("enumerated_set_sha256"))
        if repo_path(path) in direct_paths:
            continue
        assert row.get("isogeny") in (None, "none"), path
        observed_worker_max = max(observed_worker_max,
                                  *worker_counts(row), 0)
        other.append({"path": repo_path(path), "sha256": sha(path),
                      "kind": row.get("kind"),
                      "exact_top_level_target_and_base": (
                          row.get("curve_id") == screen["curve_id"] and
                          row.get("public_target") ==
                          screen["public_target"] and base_digest == digest),
                      "charged_host_seconds": window_seconds})
    assert len(other) == 62
    assert sum(row["exact_top_level_target_and_base"] for row in other) == 42
    assert observed_worker_max == 14

    direct_seconds = sum(row["charged_host_seconds"] for row in direct)
    other_seconds = len(other) * window_seconds
    reserve_seconds = EXTRA_LANES * window_seconds
    host_seconds = direct_seconds + other_seconds + reserve_seconds
    core_seconds = CORES_PER_RECORD * host_seconds
    cycle_capacity = core_seconds * CLOCK_HZ_CEILING
    assert cycle_capacity < 1 << 61
    report = {
        "kind": "n83_verified_one_target_conditional_cpu_resource_envelope",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": digest,
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "one_public_target": screen["public_target"],
        "verified_scalar": accounting["recovered_scalar"],
        "window_start_utc": WINDOW_START.isoformat(),
        "window_end_utc": WINDOW_END.isoformat(),
        "window_seconds": window_seconds,
        "direct_receipt_or_start_count": len(direct),
        "other_target_coordinate_record_count": len(other),
        "other_exact_top_level_target_and_base_count": 42,
        "other_earlier_or_nested_target_record_count": 20,
        "additional_unrecorded_reserve_lanes": EXTRA_LANES,
        "cores_per_record_or_lane_ceiling": CORES_PER_RECORD,
        "largest_archived_query_worker_count": observed_worker_max,
        "clock_hz_per_core_ceiling": CLOCK_HZ_CEILING,
        "github_standard_runner_spec_url":
            "https://docs.github.com/en/actions/reference/runners/github-hosted-runners",
        "direct_charged_host_seconds": direct_seconds,
        "other_charged_host_seconds": other_seconds,
        "reserve_charged_host_seconds": reserve_seconds,
        "total_charged_host_seconds": host_seconds,
        "core_seconds_capacity": core_seconds,
        "core_cycle_capacity_ceiling": str(cycle_capacity),
        "core_cycle_capacity_ceiling_log2": math.log2(cycle_capacity),
        "below_2_61_under_stated_resource_assumptions": True,
        "assumptions": [
            "All target-dependent n=83 work for this experiment occurred between the stated UTC boundaries; the window begins over six hours before the first experiment commit and ends after the verified-solve archive commit.",
            "Each direct receipt or start is charged its full wrapper duration; missing terminal times are charged through the window end. Every other JSON record containing the exact public target's x coordinate is charged the entire window, including earlier factor-base variants, nested benchmark controls, summaries, preflights, and duplicates.",
            "Each charged record and each of eight extra reserve lanes occupies at most sixteen simultaneously active CPU cores; the native query plans use at most fourteen worker threads. Nested jobs in one summary must fit that per-record concurrency cap.",
            "Every active core is assigned seven billion cycles per second, a deliberately loose assumed clock ceiling for the archived ARM and x86 hosts. The result counts cycle capacity, including idle and stalled time, rather than retired instructions or field API calls.",
            "The eight extra full-window lanes cover target-dependent activity without a matching receipt, base construction, independent Sage verification, and orchestration. Work on a different target or outside this window is outside this one-target envelope.",
        ],
        "boundary": "conditional whole-experiment CPU core-cycle capacity upper, including setup and failed work; not a pre-registered calibrated IC total_operations measurement or an IC/rho speedup",
        "complete_calibrated_solve_operations": None,
        "online_speedup_vs_paired_rho": None,
        "accounting_sha256": sha(ACCOUNTING),
        "screen_sha256": sha(SCREEN),
        "direct": direct,
        "other": other,
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "direct_receipt_or_start_count", "other_target_coordinate_record_count",
        "total_charged_host_seconds", "core_cycle_capacity_ceiling_log2")}, indent=2))


if __name__ == "__main__":
    main()
