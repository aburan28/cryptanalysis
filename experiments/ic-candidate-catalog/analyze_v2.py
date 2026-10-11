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
CONTRACT = json.loads((HERE / "measurement_contract_v2.json").read_text())
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
    peak_rss = run.get("peak_rss_bytes")
    require(peak_rss is None or (type(peak_rss) is int and peak_rss >= 0),
            "invalid peak RSS")
    require(type(run.get("wall_ns")) is int and run["wall_ns"] >= 0, "invalid wall time")
    require(sum(value for value in phase_wall.values() if value is not None) <= run["wall_ns"],
            "exclusive phase wall time exceeds whole run")
    online_phases = run.get("online_phase_wall_ns", {})
    require(set(online_phases) == set(CONTRACT["online_target_phases"]),
            "online phase list differs from contract")
    for key, value in online_phases.items():
        require(value is None or (type(value) is int and value >= 0),
                f"invalid online phase {key}")
    online_wall = run.get("online_wall_ns")
    require(online_wall is None or (type(online_wall) is int and online_wall >= 0
                                   and online_wall <= run["wall_ns"]), "invalid online wall time")
    if online_wall is not None:
        require(sum(value for value in online_phases.values() if value is not None) <= online_wall,
                "online phase wall time exceeds online interval")
    rho_online = run.get("rho_online_wall_ns")
    require(rho_online is None or (type(rho_online) is int and rho_online > 0),
            "invalid rho online wall time")
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
        require(run.get("target_count") == 1 and run.get("precomputation_ready") is True,
                "complete DLP requires one unseen target after reusable precomputation")
        require(isinstance(run.get("target_point_sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", run["target_point_sha256"]) is not None,
                "complete DLP lacks exact target digest")
        require(run.get("rho_verified") is True and rho_online is not None,
                "complete DLP lacks verified paired rho online time")
        require(peak_rss is not None, "complete DLP lacks peak RSS")
        require(online_wall is not None and online_wall > 0
                and all(value is not None for value in online_phases.values())
                and sum(online_phases.values()) == online_wall,
                "complete DLP lacks exact exclusive online timing")
        if total is not None:
            require(total > 0, "full DLP total operations must be positive")
    else:
        require(total is None, "stage or censored run cannot claim full total")
        require(run.get("verified_scalar") is not True, "stage or censored run claims scalar")
    rho = run.get("rho_operations")
    require(rho is None or (type(rho) is int and rho > 0), "invalid rho cost")
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
        priced_full = [run["total_operations"] for run in full if run["total_operations"] is not None]
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
            "verified_within_budget_query_rate": solved / ordinary if ordinary else None,
            "verified_within_budget_query_wilson95": wilson95(solved, ordinary),
            "novel_rows_per_ordinary_query": novel / ordinary if ordinary else None,
            "complete_dlp_runs": len(full),
            "median_complete_online_wall_ns": statistics.median(
                run["online_wall_ns"] for run in full) if full else None,
            "median_complete_rho_online_speedup": statistics.median(
                run["rho_online_wall_ns"] / run["online_wall_ns"] for run in full) if full else None,
            "median_complete_total_operations_supplementary": statistics.median(
                priced_full) if priced_full else None,
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
    online_ratios = []
    rho_ratios = []
    cold_ratios = []
    incomplete = []
    for key in keys:
        a, b = selected[baseline].get(key), selected[candidate].get(key)
        if a is None or b is None:
            incomplete.append({"block": key, "reason": "missing_arm"})
            continue
        for field in ("source_curve_ref", "subgroup_order"):
            require(a[field] == b[field], f"mismatched {field} in {key}")
        for field in ("workload_fixture_sha256", "resource_envelope_id", "calibration_id",
                      "host_id"):
            require(a["provenance"][field] == b["provenance"][field],
                    f"mismatched provenance {field} in {key}")
        if a["kind"] != "full_dlp" or b["kind"] != "full_dlp" or a["status"] != "complete" or b["status"] != "complete":
            incomplete.append({"block": key, "reason": "incomplete_dlp"})
            continue
        require(a["target_point_sha256"] == b["target_point_sha256"],
                f"mismatched target point in {key}")
        require(a["rho_online_wall_ns"] == b["rho_online_wall_ns"],
                f"mismatched paired rho online time in {key}")
        online_ratios.append(a["online_wall_ns"] / b["online_wall_ns"])
        rho_ratios.append(b["rho_online_wall_ns"] / b["online_wall_ns"])
        if a["total_operations"] is not None and b["total_operations"] is not None:
            cold_ratios.append(a["total_operations"] / b["total_operations"])
    outcome = {"baseline": baseline, "candidate": candidate,
               "paired_blocks": len(keys), "complete_pairs": len(online_ratios),
               "incomplete_pairs": incomplete, "online_speedup": None,
               "online_speedup_ci95": None, "rho_over_candidate_online_speedup": None,
               "rho_over_candidate_online_speedup_ci95": None,
               "cold_operations_speedup_supplementary": None,
               "cold_operations_priced_pairs": len(cold_ratios),
               "confidence_unit": "independent_pair_block"}
    if incomplete or not online_ratios:
        return outcome
    for field, ratios in (("online_speedup", online_ratios),
                          ("rho_over_candidate_online_speedup", rho_ratios)):
        logs = [math.log(ratio) for ratio in ratios]
        outcome[field] = math.exp(statistics.mean(logs))
        if len(logs) >= 3:
            seed = int.from_bytes(hashlib.sha256((baseline + "|" + candidate + "|" + field).encode()).digest()[:8], "big")
            rng = random.Random(seed)
            draws = sorted(math.exp(sum(rng.choices(logs, k=len(logs))) / len(logs)) for _ in range(10000))
            outcome[field + "_ci95"] = [draws[249], draws[9749]]
    if len(cold_ratios) == len(online_ratios):
        outcome["cold_operations_speedup_supplementary"] = math.exp(
            statistics.mean(math.log(ratio) for ratio in cold_ratios))
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
