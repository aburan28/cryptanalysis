#!/usr/bin/env python3
"""A deliberately loose whole-campaign CPU-capacity ceiling for n=83.

This is a resource envelope, not an instruction counter or a calibrated
field-operation total. The assumptions are emitted with the result.
"""

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = HERE / "runs"
ACCOUNTING = HERE / "n83_verified_solve_accounting.json"
SCREEN = HERE / "n83_full_spill_screen.json"
LOCAL_HOST = RUNS / "n83_local_resource_host_audit_20261001.json"
CI_INVENTORY = RUNS / "n83_ci_workflow_run_inventory_20261001.json"
OUTPUT = HERE / "n83_verified_solve_resource_envelope.json"
UTC = dt.timezone.utc
WINDOW_START = dt.datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
WINDOW_END = dt.datetime(2026, 10, 1, 15, 30, tzinfo=UTC)
CORES_PER_RECORD = 16
EXTRA_LANES = 8
CLOCK_HZ_CEILING = 7_000_000_000
POOL_RUNS_CEILING = 32
POOL_JOBS_PER_RUN_CEILING = 8
POOL_VCPU_PER_JOB = 4
POOL_CLOCK_HZ_CEILING = 8_000_000_000


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
    host = json.loads(LOCAL_HOST.read_text())
    assert host["architecture"] == "arm64"
    assert host["chip_type"] == "Apple M4 Pro"
    assert host["physical_core_count"] == 14
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

    archived_ci_run_ids = sorted({
        found for path in RUNS.rglob("*")
        for found in re.findall(r"ci_(\d{10,})", str(path))})
    assert len(archived_ci_run_ids) == 16
    assert "36817149475" in archived_ci_run_ids
    workflow_files = sorted((REPO / ".github/workflows").glob("*n83*"))
    assert len(workflow_files) == 14
    workflow_sources = []
    for path in workflow_files:
        source = path.read_text()
        parallel = [int(value) for value in re.findall(
            r"max-parallel:\s*(\d+)", source)]
        labels = re.findall(r"runs-on:\s*([^\s#]+)", source)
        assert all(0 < value <= POOL_JOBS_PER_RUN_CEILING
                   for value in parallel)
        assert "matrix:" not in source or parallel
        assert all(label == "ubuntu-24.04" for label in labels)
        assert labels or (
            "uses: ./.github/workflows/n83-portable-quotient-segment.yml"
            in source)
        workflow_sources.append({"path": repo_path(path),
                                 "sha256": sha(path),
                                 "max_parallel": max(parallel, default=1),
                                 "runner_labels": labels})

    inventory = json.loads(CI_INVENTORY.read_text())
    assert inventory["repository"] == "aburan28/cryptanalysis"
    assert inventory["branch"] == "codex/koblitz-pair-claw-toy"
    assert inventory["per_workflow_limit"] == 500
    assert set(inventory["workflow_row_counts"]) == {
        path.name for path in workflow_files}
    assert max(inventory["workflow_row_counts"].values()) < 500
    assert len(inventory["rows"]) == 918
    assert len({row["databaseId"] for row in inventory["rows"]}) == 918
    events = []
    runs_intersecting_window = 0
    for row in inventory["rows"]:
        start, end = utc(row["createdAt"]), utc(row["updatedAt"])
        assert start <= end
        if start >= WINDOW_END or end <= WINDOW_START:
            continue
        assert row["status"] == "completed", row["databaseId"]
        runs_intersecting_window += 1
        events.extend(((max(start, WINDOW_START), 1),
                       (min(end, WINDOW_END), -1)))
    concurrent_runs = 0
    observed_run_overlap_max = 0
    for _, delta in sorted(events, key=lambda pair: (pair[0], pair[1])):
        concurrent_runs += delta
        observed_run_overlap_max = max(observed_run_overlap_max,
                                       concurrent_runs)
    assert concurrent_runs == 0
    assert runs_intersecting_window == 892
    assert observed_run_overlap_max == 15
    assert observed_run_overlap_max < POOL_RUNS_CEILING
    pool_cores = (POOL_RUNS_CEILING * POOL_JOBS_PER_RUN_CEILING *
                  POOL_VCPU_PER_JOB + host["physical_core_count"])
    pool_cycle_capacity = (window_seconds * pool_cores *
                           POOL_CLOCK_HZ_CEILING)
    observed_pool_cores = (
        observed_run_overlap_max * POOL_JOBS_PER_RUN_CEILING *
        POOL_VCPU_PER_JOB + host["physical_core_count"])
    observed_pool_capacity = (window_seconds * observed_pool_cores *
                              POOL_CLOCK_HZ_CEILING)
    assert pool_cycle_capacity < 1 << 61
    assert observed_pool_capacity <= pool_cycle_capacity
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
        "github_runner_vcpu_per_job": POOL_VCPU_PER_JOB,
        "local_host_audit_sha256": sha(LOCAL_HOST),
        "ci_workflow_run_inventory_sha256": sha(CI_INVENTORY),
        "direct_charged_host_seconds": direct_seconds,
        "other_charged_host_seconds": other_seconds,
        "reserve_charged_host_seconds": reserve_seconds,
        "total_charged_host_seconds": host_seconds,
        "core_seconds_capacity": core_seconds,
        "core_cycle_capacity_ceiling": str(cycle_capacity),
        "core_cycle_capacity_ceiling_log2": math.log2(cycle_capacity),
        "below_2_61_under_stated_resource_assumptions": True,
        "global_pool_cross_check": {
            "archived_distinct_ci_run_ids": archived_ci_run_ids,
            "archived_distinct_ci_run_count": len(archived_ci_run_ids),
            "github_workflow_run_inventory_count": len(inventory["rows"]),
            "github_workflow_runs_intersecting_window":
                runs_intersecting_window,
            "observed_max_concurrent_workflow_run_intervals":
                observed_run_overlap_max,
            "assumed_max_concurrent_ci_runs":
                POOL_RUNS_CEILING,
            "concurrent_run_headroom_above_observed_intervals":
                POOL_RUNS_CEILING - observed_run_overlap_max,
            "max_jobs_per_ci_run": POOL_JOBS_PER_RUN_CEILING,
            "standard_runner_vcpu_per_job": POOL_VCPU_PER_JOB,
            "local_physical_cpu_cores": host["physical_core_count"],
            "total_simultaneous_core_ceiling": pool_cores,
            "observed_interval_core_capacity_ceiling":
                observed_pool_cores,
            "clock_hz_per_core_ceiling": POOL_CLOCK_HZ_CEILING,
            "full_window_core_cycle_capacity": str(pool_cycle_capacity),
            "full_window_core_cycle_capacity_log2":
                math.log2(pool_cycle_capacity),
            "observed_interval_core_cycle_capacity":
                str(observed_pool_capacity),
            "observed_interval_core_cycle_capacity_log2":
                math.log2(observed_pool_capacity),
            "below_2_61_under_stated_pool_assumptions": True,
            "workflow_sources": workflow_sources,
        },
        "assumptions": [
            "All target-dependent n=83 work for this experiment occurred between the stated UTC boundaries; the window begins over six hours before the first experiment commit and ends after the verified-solve archive commit.",
            "Each direct receipt or start is charged its full wrapper duration; missing terminal times are charged through the window end. Every other JSON record containing the exact public target's x coordinate is charged the entire window, including earlier factor-base variants, nested benchmark controls, summaries, preflights, and duplicates.",
            "Each charged record and each of eight extra reserve lanes occupies at most sixteen simultaneously active CPU cores; the native query plans use at most fourteen worker threads. Nested jobs in one summary must fit that per-record concurrency cap.",
            "Every active core is assigned seven billion cycles per second, a deliberately loose assumed clock ceiling for the archived ARM and x86 hosts. The result counts cycle capacity, including idle and stalled time, rather than retired instructions or field API calls.",
            "The eight extra full-window lanes cover target-dependent activity without a matching receipt, base construction, independent Sage verification, and orchestration. Work on a different target or outside this window is outside this one-target envelope.",
            "The independent global-pool cross-check archives 918 GitHub run intervals across all fourteen n=83 workflows, with at most fifteen overlapping the accounting window. It still charges thirty-two simultaneous standard-runner runs, eight jobs per run, four vCPUs per job, and this fourteen-core local Mac for the entire window at eight GHz. It covers all CPU phases within that host pool even when an individual receipt is missing.",
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
