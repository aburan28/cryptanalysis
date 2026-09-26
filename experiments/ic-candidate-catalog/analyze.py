#!/usr/bin/env python3
"""Validate IC run receipts and make fail-closed paired comparisons."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

import generate


HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "measurement_contract.json").read_text())
ROUTES = generate.validate_routes(json.loads((HERE / "isogeny_routes.json").read_text()))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_run(run: dict) -> dict:
    require(run.get("schema_version") == CONTRACT["schema_version"], "wrong schema version")
    require(run.get("kind") in CONTRACT["run_kinds"], "unknown run kind")
    require(run.get("status") in CONTRACT["run_statuses"], "unknown run status")
    for key in ("run_id", "workload_id", "pair_block_id", "source_curve_ref", "profile_id",
                "isogeny_route_ref"):
        require(isinstance(run.get(key), str) and bool(run[key]), f"missing {key}")
    require(run["isogeny_route_ref"] in ROUTES, "unknown isogeny route reference")
    require("candidate_id" in run and "proposal_id" in run,
            "candidate_id and proposal_id keys are both required")
    require(bool(run.get("candidate_id")) != bool(run.get("proposal_id")),
            "exactly one candidate_id or proposal_id is required")
    if run["candidate_id"] is not None:
        require(isinstance(run["candidate_id"], str)
                and run["candidate_id"].startswith("IC1"), "invalid final candidate ID")
    else:
        require(isinstance(run["proposal_id"], str)
                and re.fullmatch(r"Q[1-9][0-9]*", run["proposal_id"]) is not None,
                "invalid proposal ID")
    for key in CONTRACT["required_provenance"]:
        require(isinstance(run.get("provenance", {}).get(key), str)
                and bool(run["provenance"][key]), f"missing provenance {key}")
    counts = run.get("counts", {})
    for key in CONTRACT["required_counts"]:
        require(type(counts.get(key)) is int and counts[key] >= 0, f"invalid count {key}")
    require(counts["solved_queries"] <= counts["ordinary_queries"],
            "more solved queries than ordinary queries")
    require(counts["solved_queries"] <= counts["verified_decompositions"],
            "more solved queries than verified decompositions")
    require(counts["novel_rows"] <= counts["verified_relations"],
            "more novel rows than verified relations")
    require(counts["final_rank"] <= counts["effective_columns"],
            "rank exceeds effective columns")
    pdp_status_keys = ("pdp_verified", "pdp_proved_unsat", "pdp_timeout",
                       "pdp_budget", "pdp_error", "pdp_lift_rejected")
    require(sum(counts[key] for key in pdp_status_keys) == counts["pdp_attempts"],
            "PDP outcome counts do not sum to attempts")
    require(counts["solved_queries"] <= counts["pdp_verified"],
            "more solved queries than verified PDP attempts")
    phases = run.get("phase_operations", {})
    require(set(phases) == set(CONTRACT["phase_operations"]), "phase list differs from contract")
    for key, value in phases.items():
        require(value is None or (type(value) is int and value >= 0), f"invalid phase {key}")
    phase_wall = run.get("phase_wall_ns", {})
    require(set(phase_wall) == set(CONTRACT["phase_operations"]),
            "wall-time phase list differs from contract")
    for key, value in phase_wall.items():
        require(value is None or (type(value) is int and value >= 0),
                f"invalid wall-time phase {key}")
    require(type(run.get("peak_rss_bytes")) is int and run["peak_rss_bytes"] >= 0,
            "invalid peak RSS")
    require(type(run.get("wall_ns")) is int and run["wall_ns"] >= 0, "invalid wall time")
    require(sum(value for value in phase_wall.values() if value is not None) <= run["wall_ns"],
            "exclusive phase wall time exceeds whole run")
    require(isinstance(run.get("subgroup_order"), str) and run["subgroup_order"].isdigit()
            and int(run["subgroup_order"]) > 1, "invalid subgroup order")
    total = run.get("total_operations")
    all_priced = all(value is not None for value in phases.values())
    if total is not None:
        require(all_priced and type(total) is int and total == sum(phases.values()),
                "total operations must exactly sum exclusive phases")
    if run["kind"] == "full_dlp" and run["status"] == "complete":
        require(run["candidate_id"] is not None, "full DLP requires final candidate ID")
        require(ROUTES[run["isogeny_route_ref"]]["status"] in ("identity", "verified"),
                "full DLP uses unverified isogeny route")
        if "ISO1" in run["candidate_id"]:
            require(ROUTES[run["isogeny_route_ref"]]["status"] == "verified",
                    "ISO1 candidate lacks verified route")
        if "ISO0" in run["candidate_id"]:
            require(run["isogeny_route_ref"] == "none", "ISO0 candidate names a route")
        require(run.get("verified_scalar") is True and run.get("scalar_certificate_ref"),
                "full DLP lacks scalar certificate")
        require(total is not None and run.get("rho_operations") is not None,
                "full DLP lacks complete cost or rho reference")
        require(total > 0, "full DLP total cost must be positive")
        require(all(value is not None for value in phase_wall.values()),
                "full DLP lacks phase wall times")
    else:
        require(total is None, "stage or censored run cannot claim full total")
        require(run.get("verified_scalar") is not True, "stage or censored run claims scalar")
    rho = run.get("rho_operations")
    require(rho is None or (type(rho) is int and rho > 0), "invalid rho cost")
    warm = run.get("warm")
    if warm is not None:
        per_target = warm.get("per_target_operations")
        require(isinstance(per_target, list)
                and all(type(v) is int and v >= 0 for v in per_target),
                "invalid per-target operation ledger")
        require(len(per_target) == counts["targets"],
                "per-target operation ledger length differs from target count")
        require(warm.get("target_operations") == sum(per_target),
                "target operation total differs from per-target ledger")
        shared = warm.get("shared_operations")
        require(shared is None or (type(shared) is int and shared >= 0),
                "invalid shared operation count")
        if total is not None:
            require(shared is not None and shared + sum(per_target) == total,
                    "shared plus target operations must equal total")
        prefixes = warm.get("prefixes")
        require(isinstance(prefixes, list), "invalid amortization prefix list")
        previous = 0
        for prefix in prefixes:
            k = prefix.get("targets")
            require(type(k) is int and previous < k <= len(per_target),
                    "invalid amortization prefix target count")
            previous = k
            if total is not None:
                require(prefix.get("ic_operations") == shared + sum(per_target[:k]),
                        "prefix IC operations do not match shared plus marginal ledger")
                require(prefix.get("independent_rho_operations") == k * rho,
                        "prefix independent-rho operations are inconsistent")
                for key in ("batch_rho_operations", "folded_batch_rho_operations"):
                    require(type(prefix.get(key)) is int and prefix[key] > 0,
                            f"invalid prefix {key}")
        if per_target:
            require(prefixes and prefixes[-1]["targets"] == len(per_target),
                    "amortization prefixes do not include the full batch")
        series = run.get("workload_series_id")
        require(series is None or (isinstance(series, str) and series.startswith("ICBW1h")),
                "invalid workload series ID")

    if run["source_curve_ref"].startswith("EC1P"):
        require(run["candidate_id"] is not None and run["candidate_id"].startswith("IC1P"),
                "prime-field curve must use the IC1P candidate namespace")
        require(run.get("operation_unit") == "prime_group_operation",
                "prime-field normalized receipt has the wrong operation unit")
        require(isinstance(run.get("native_prime_report"), dict)
                and run["native_prime_report"].get("operation") == "prime",
                "prime-field normalized receipt must retain the native ca-ic report")
        require(run["provenance"].get("binary_blake3"),
                "prime-field receipt lacks executable digest")
        batch = run.get("rho_batch") or {}
        require(type(batch.get("shared_dp_expected_operations")) is int
                and batch["shared_dp_expected_operations"] > 0,
                "prime-field receipt lacks batch-rho control")
        require(type(batch.get("folded_shared_dp_expected_operations")) is int
                and batch["folded_shared_dp_expected_operations"] > 0,
                "prime-field receipt lacks folded batch-rho control")

    online = run.get("online")
    if online is not None:
        require(counts["targets"] == 1, "primary online receipt needs exactly one target")
        charged = online.get("phase_wall_ns", {})
        required = {"target_query", "target_pdp", "target_relation_check", "target_descent",
                    "target_recovery_check"}
        require(set(charged) == required and all(type(v) is int and v >= 0 for v in charged.values()),
                "invalid primary online phase accounting")
        ic_ns = online.get("ic_online_ns")
        require(type(ic_ns) is int and ic_ns > 0 and sum(charged.values()) == ic_ns,
                "primary online phases must sum to the target interval")
        measured = run.get("rho_measured") or {}
        rho_ns = measured.get("online_wall_ns")
        require(type(rho_ns) is int and rho_ns > 0 and rho_ns == online.get("rho_online_ns"),
                "missing paired measured rho interval")
        if online.get("speedup") is not None:
            require(run.get("verified_scalar") is True and measured.get("verified") is True,
                    "unverified target claims online speedup")
            require(math.isclose(online["speedup"], rho_ns / ic_ns, rel_tol=1e-12),
                    "incorrect online speedup")
    return run


def wilson95(successes: int, trials: int) -> list[float] | None:
    if trials == 0:
        return None
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def summarize(runs: list[dict]) -> dict:
    by_config: dict[tuple[str, str], list[dict]] = {}
    for run in runs:
        config = run["candidate_id"] or run["proposal_id"]
        by_config.setdefault((config, run["workload_id"]), []).append(run)
    result = {}
    for (config, workload), group in sorted(by_config.items()):
        counts = Counter(run["status"] for run in group)
        ordinary = sum(run["counts"]["ordinary_queries"] for run in group)
        solved = sum(run["counts"]["solved_queries"] for run in group)
        novel = sum(run["counts"]["novel_rows"] for run in group)
        pdp_attempts = sum(run["counts"]["pdp_attempts"] for run in group)
        pdp_outcomes = {key: sum(run["counts"][key] for run in group)
                        for key in ("pdp_verified", "pdp_proved_unsat", "pdp_timeout",
                                    "pdp_budget", "pdp_error", "pdp_lift_rejected")}
        pdp_times = [run["phase_wall_ns"]["pdp"] for run in group
                     if run["phase_wall_ns"]["pdp"] is not None]
        collection_phases = ("setup", "isogeny", "factor_base", "precompute",
                             "queries", "pdp", "relation_check", "matrix_build")
        collection_priced = all(run["phase_operations"][phase] is not None
                                for run in group for phase in collection_phases)
        collection_ops = sum(run["phase_operations"][phase] for run in group
                             for phase in collection_phases) if collection_priced else None
        full = [run for run in group if run["kind"] == "full_dlp" and run["status"] == "complete"]
        result.setdefault(config, {})[workload] = {
            "runs": len(group),
            "statuses": dict(sorted(counts.items())),
            "ordinary_queries": ordinary,
            "solved_queries": solved,
            "novel_rows": novel,
            "pdp_attempts": pdp_attempts,
            "pdp_outcomes": pdp_outcomes,
            "median_charged_pdp_wall_ns": statistics.median(pdp_times) if pdp_times else None,
            "mean_wall_ns_per_pdp_attempt": sum(pdp_times) / pdp_attempts
            if len(pdp_times) == len(group) and pdp_attempts else None,
            "observed_cold_collection_ops_per_novel_row": collection_ops / novel
            if collection_ops is not None and novel else None,
            "observed_decomposition_rate": solved / ordinary if ordinary else None,
            "observed_decomposition_wilson95": wilson95(solved, ordinary),
            "novel_rows_per_ordinary_query": novel / ordinary if ordinary else None,
            "complete_dlp_runs": len(full),
            "median_complete_total_operations": statistics.median(
                run["total_operations"] for run in full) if full else None,
            "median_verified_ic_online_ns": statistics.median(
                run["online"]["ic_online_ns"] for run in full
                if run.get("online") and run["online"].get("speedup") is not None)
            if any(run.get("online") and run["online"].get("speedup") is not None for run in full) else None,
            "median_shared_operations": statistics.median(
                run["warm"]["shared_operations"] for run in full if run.get("warm"))
            if any(run.get("warm") for run in full) else None,
            "median_marginal_target_operations": statistics.median(
                run["warm"]["mean_target_operations"] for run in full if run.get("warm"))
            if any(run.get("warm") for run in full) else None,
            "median_ic_over_folded_batch_rho": statistics.median(
                run["warm"]["ic_over_folded_batch_rho"] for run in full
                if run.get("warm") and run["warm"].get("ic_over_folded_batch_rho") is not None)
            if any(run.get("warm") and run["warm"].get("ic_over_folded_batch_rho") is not None
                   for run in full) else None,
        }
    return result


def paired_compare(runs: list[dict], baseline: str, candidate: str) -> dict:
    require(baseline != candidate, "baseline and candidate must differ")
    selected = {baseline: {}, candidate: {}}
    for run in runs:
        config = run["candidate_id"] or run["proposal_id"]
        if config not in selected:
            continue
        key = (run["workload_id"], run["pair_block_id"])
        require(key not in selected[config], f"duplicate pair block for {config}: {key}")
        selected[config][key] = run
    keys = sorted(set(selected[baseline]) | set(selected[candidate]))
    require(keys, "no runs for requested comparison")
    require(len({key[0] for key in keys}) == 1,
            "compare one frozen workload at a time")
    ratios = []
    incomplete = []
    for key in keys:
        a, b = selected[baseline].get(key), selected[candidate].get(key)
        if a is None or b is None:
            incomplete.append({"block": key, "reason": "missing_arm"})
            continue
        for field in ("source_curve_ref", "subgroup_order"):
            require(a[field] == b[field], f"mismatched {field} in {key}")
        require(a["rho_operations"] == b["rho_operations"],
                f"mismatched rho reference in {key}")
        for field in ("workload_fixture_sha256", "resource_envelope_id", "calibration_id"):
            require(a["provenance"][field] == b["provenance"][field],
                    f"mismatched provenance {field} in {key}")
        require(bool(a.get("online")) == bool(b.get("online")),
                f"mismatched online accounting in {key}")
        if a["kind"] != "full_dlp" or b["kind"] != "full_dlp" or a["status"] != "complete" or b["status"] != "complete":
            incomplete.append({"block": key, "reason": "incomplete_dlp"})
            continue
        if a.get("online") and b.get("online"):
            if a["online"].get("speedup") is None or b["online"].get("speedup") is None:
                incomplete.append({"block": key, "reason": "unverified_online_control"})
                continue
            ratios.append(a["online"]["ic_online_ns"] / b["online"]["ic_online_ns"])
        else:
            ratios.append(a["total_operations"] / b["total_operations"])
    outcome = {"baseline": baseline, "candidate": candidate,
               "paired_blocks": len(keys), "complete_pairs": len(ratios),
               "incomplete_pairs": incomplete, "speedup": None,
               "speedup_ci95": None, "confidence_unit": "independent_pair_block"}
    outcome["metric"] = "one_target_online_wall_ns" if all(
        run.get("online") is not None for pair in selected.values() for run in pair.values()) else "cold_operations"
    if incomplete or not ratios:
        return outcome
    logs = [math.log(ratio) for ratio in ratios]
    outcome["speedup"] = math.exp(statistics.mean(logs))
    if len(logs) >= 3:
        seed = int.from_bytes(hashlib.sha256((baseline + "|" + candidate).encode()).digest()[:8], "big")
        rng = random.Random(seed)
        draws = sorted(math.exp(sum(rng.choices(logs, k=len(logs))) / len(logs)) for _ in range(10000))
        outcome["speedup_ci95"] = [draws[249], draws[9749]]
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, help="one JSON run receipt per line")
    parser.add_argument("--baseline")
    parser.add_argument("--candidate")
    args = parser.parse_args()
    require(bool(args.baseline) == bool(args.candidate), "supply both comparison IDs")
    runs = [validate_run(json.loads(line)) for line in args.runs.read_text().splitlines() if line.strip()]
    ids = [run["run_id"] for run in runs]
    require(len(set(ids)) == len(ids), "duplicate run IDs")
    report = {"run_count": len(runs), "configurations": summarize(runs)}
    if args.baseline:
        report["comparison"] = paired_compare(runs, args.baseline, args.candidate)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
