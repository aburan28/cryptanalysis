#!/usr/bin/env python3
"""Exact N41 two-free-pair occupancy and public-target prefix census.

The quadratic suffix index is a diagnostic oracle. It measures the amount
of target-dependent pruning a compact two-free-pair propagator must supply.
"""

from __future__ import annotations

import hashlib
import json
import math
import resource
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from arithmetic_snapshot import Curve, Field  # noqa: E402

GEOMETRY = HERE / "geometry_snapshot.json"
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"
STARTED = HERE / "started.json"
RUNTIME = HERE / "sage_runtime_info.json"
FIELD_BITS = 41


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_once(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def encode(point: tuple[int, int] | None) -> int:
    return -1 if point is None else point[0] | (point[1] << FIELD_BITS)


def pair_states(curve: Curve, source: list) -> list[tuple[tuple[int, int], int, int, int]]:
    states = []
    for i in range(len(source)):
        for j in range(i + 1, len(source)):
            if source[i][2] == source[j][2]:
                continue
            total = curve.add(tuple(source[i][:2]), tuple(source[j][:2]))
            if total is None:
                raise ValueError("distinct-column pair unexpectedly sums to identity")
            states.append((total, (1 << source[i][2]) | (1 << source[j][2]), i, j))
    if len(states) != 1956:
        raise ValueError("frozen N41 pair-domain size changed")
    return states


def n131_bound(record: dict) -> dict:
    n131 = record["n131"]
    b = n131["per_slot_usable_points_B"]
    r = int(n131["subgroup_order"])
    pair_state_upper = math.comb(b, 2)
    suffix_assignment_upper = pair_state_upper**2
    # A fixed, target-independent two-pair prefix leaves two free pair domains.
    # Every valid suffix assignment yields at most one subgroup point.
    probes_for_half_by_union_bound = ((r - 1) + 2 * suffix_assignment_upper - 1) // (2 * suffix_assignment_upper)
    return {
        "curve_id": n131["curve_id"],
        "subgroup_order": str(r),
        "per_slot_usable_points_B": b,
        "pair_state_upper_without_column_filter": pair_state_upper,
        "two_free_pair_assignment_upper": suffix_assignment_upper,
        "uniform_nonidentity_target_hit_probability_upper": {
            "numerator": suffix_assignment_upper,
            "denominator": r - 1,
        },
        "fixed_prefix_probes_for_half_success_lower_by_union_bound": probes_for_half_by_union_bound,
        "required_fixed_prefix_probes_per_second_at_600s_lower": {
            "numerator": probes_for_half_by_union_bound,
            "denominator": 600,
        },
        "scope": "uniform independent target and target-independent fixed-prefix probes; adaptive target-conditioned search is outside this bound",
    }


def main() -> None:
    if RESULT.exists() or STARTED.exists() or RUNTIME.exists():
        raise FileExistsError("preserve the first frozen occupancy execution")
    protocol = json.loads(PROTOCOL.read_text())
    if (protocol["geometry_sha256"] != sha(GEOMETRY) or
            protocol["arithmetic_sha256"] != sha(HERE / "arithmetic_snapshot.py") or
            protocol["run_source_sha256"] != sha(Path(__file__)) or
            protocol["audit_source_sha256"] != sha(HERE / "audit.py")):
        raise ValueError("frozen source or geometry changed")
    record = json.loads(GEOMETRY.read_text())
    n41 = record["n41"]
    if (n41["curve_id"] != protocol["curve_id"] or
            n41["slot_rotations"] != [0, 0, 10, 10, 20, 20, 30, 30] or
            n41["public_target_q"] != protocol["public_target_q"] or
            int(n41["subgroup_order"]) != protocol["subgroup_order"] or
            record["n131"]["curve_id"] != protocol["n131_curve_id"]):
        raise ValueError("frozen curve, pair policy, or public target changed")
    runtime = subprocess.run([str(ROOT / "sage"), "--runtime-info"],
                             cwd=ROOT, capture_output=True, text=True, check=True)
    RUNTIME.write_text(runtime.stdout)
    write_once(STARTED, {"status": "RUNNING", "protocol_sha256": sha(PROTOCOL),
                         "geometry_sha256": sha(GEOMETRY),
                         "runtime_sha256": sha(RUNTIME),
                         "started_utc_epoch": time.time()})

    field = Field(FIELD_BITS, [0, 3])
    curve = Curve(field, 0)
    process = psutil.Process()
    cap_ns = int(protocol["total_wall_cap_seconds"] * 1_000_000_000)
    cap_rss = protocol["process_rss_cap_bytes"]
    start_ns = time.monotonic_ns()
    deadline_ns = start_ns + cap_ns
    peak_rss = 0
    counts = {"suffix_valid_assignments": 0, "suffix_distinct_group_sums": 0,
              "suffix_duplicate_assignments": 0, "prefix_valid_assignments": 0,
              "prefix_residual_support_hits": 0, "prefixes_with_valid_completions": 0,
              "eight_column_relations": 0}
    witnesses = []
    status = "producer_failure"
    error = None
    setup_ns = query_ns = 0
    query_start_ns = None
    try:
        sources = [n41["point_rows_by_unique_rotation"][str(r)]
                   for r in protocol["pair_rotations"]]
        if any(len(source) != 64 for source in sources):
            raise ValueError("frozen N41 point-domain size changed")
        for source in sources:
            for point in source:
                if not curve.on_curve(tuple(point[:2])):
                    raise ValueError("factor-base point is off curve")
        domains = [pair_states(curve, source) for source in sources]
        suffix: dict[int, int | list[int]] = {}
        for i, left in enumerate(domains[2]):
            for j, right in enumerate(domains[3]):
                if left[1] & right[1]:
                    continue
                key = encode(curve.add(left[0], right[0]))
                packed = i | (j << 11)
                prior = suffix.get(key)
                if prior is None:
                    suffix[key] = packed
                elif isinstance(prior, int):
                    suffix[key] = [prior, packed]
                    counts["suffix_duplicate_assignments"] += 1
                else:
                    prior.append(packed)
                    counts["suffix_duplicate_assignments"] += 1
                counts["suffix_valid_assignments"] += 1
            if i % 16 == 0:
                peak_rss = max(peak_rss, process.memory_info().rss)
                if peak_rss > cap_rss:
                    raise MemoryError("frozen process RSS cap reached in suffix setup")
                if time.monotonic_ns() >= deadline_ns:
                    raise TimeoutError("frozen total wall cap reached in suffix setup")
        counts["suffix_distinct_group_sums"] = len(suffix)
        setup_ns = time.monotonic_ns() - start_ns

        query_start_ns = time.monotonic_ns()
        target = tuple(protocol["public_target_q"])
        if not curve.on_curve(target) or curve.mul(protocol["subgroup_order"], target) is not None:
            raise ValueError("public N41 target is not in the declared subgroup")
        for i, left in enumerate(domains[0]):
            for j, right in enumerate(domains[1]):
                if left[1] & right[1]:
                    continue
                counts["prefix_valid_assignments"] += 1
                prefix_mask = left[1] | right[1]
                prefix_sum = curve.add(left[0], right[0])
                residual = curve.add(target, curve.neg(prefix_sum))
                found = suffix.get(encode(residual))
                if found is None:
                    continue
                counts["prefix_residual_support_hits"] += 1
                valid_for_prefix = False
                options = [found] if isinstance(found, int) else found
                for packed in options:
                    k, l = packed & 2047, packed >> 11
                    if prefix_mask & (domains[2][k][1] | domains[3][l][1]):
                        continue
                    valid_for_prefix = True
                    counts["eight_column_relations"] += 1
                    if len(witnesses) < protocol["max_saved_witnesses"]:
                        states = [left, right, domains[2][k], domains[3][l]]
                        witnesses.append({
                            "pair_state_indices": [i, j, k, l],
                            "point_indices": [[state[2], state[3]] for state in states],
                            "columns": [[sources[d][state[2]][2], sources[d][state[3]][2]]
                                        for d, state in enumerate(states)],
                            "pair_sums": [list(state[0]) for state in states],
                        })
                if valid_for_prefix:
                    counts["prefixes_with_valid_completions"] += 1
            if i % 16 == 0:
                peak_rss = max(peak_rss, process.memory_info().rss)
                if peak_rss > cap_rss:
                    raise MemoryError("frozen process RSS cap reached in target scan")
                if time.monotonic_ns() >= deadline_ns:
                    raise TimeoutError("frozen total wall cap reached in target scan")
        query_ns = time.monotonic_ns() - query_start_ns
        status = "COMPLETE_EXACT_OCCUPANCY_AND_TARGET_CENSUS"
    except Exception as failure:
        if isinstance(failure, MemoryError):
            status = "OOM"
        elif isinstance(failure, TimeoutError):
            status = "TIMEOUT"
        error = {"type": type(failure).__name__, "message": str(failure)}
    elapsed_ns = time.monotonic_ns() - start_ns
    if query_start_ns is not None and not query_ns:
        query_ns = time.monotonic_ns() - query_start_ns
    elif not setup_ns:
        setup_ns = elapsed_ns
    rss_max = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss_max *= 1024
    peak_rss = max(peak_rss, rss_max, process.memory_info().rss)
    result = {"kind": protocol["kind"], "status": status, "error": error,
              "curve_id": n41["curve_id"], "n131_curve_id": record["n131"]["curve_id"],
              "candidate_id": None, "run_id": None,
              "public_target_q": protocol["public_target_q"],
              "pair_rotations": protocol["pair_rotations"],
              "pair_domain_sizes": [len(domain) for domain in domains] if "domains" in locals() else None,
              "counts": counts, "saved_witnesses": witnesses,
              "target_independent_setup_wall_ns": setup_ns,
              "target_dependent_query_wall_ns": query_ns,
              "total_experiment_wall_ns": elapsed_ns,
              "process_peak_rss_bytes": peak_rss,
              "n131_fixed_prefix_bound": n131_bound(record),
              "input_sha256": {"protocol": sha(PROTOCOL), "geometry": sha(GEOMETRY),
                               "arithmetic": sha(HERE / "arithmetic_snapshot.py"),
                               "runner": sha(Path(__file__)), "runtime": sha(RUNTIME)},
              "claim_boundary": "exact N41 occupancy diagnostic and uniform-target N131 fixed-prefix bound; no public N131 query or IC online speed comparison"}
    write_once(RESULT, result)
    print(json.dumps({"status": status, "counts": counts,
                      "peak_rss_bytes": peak_rss, "error": error}, sort_keys=True))


if __name__ == "__main__":
    main()
