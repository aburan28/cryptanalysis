#!/usr/bin/env python3
"""Run one frozen Q1488 matched-base pair-table ordinary-query cell."""

from __future__ import annotations

import argparse
import json
import random
import resource
import sys
import time
from pathlib import Path

from build_n53_base import HERE, PARENT, ROOT, read_points, sha
from sample_window import WindowOrbitSampler

sys.path.insert(0, str(PARENT / "q1445_matched_pair_table"))
from pair_probe import (IndexedBaseSampler, OrbitKey, curves, field,
                        pair_table, query_table, workload_id)  # noqa: E402

PROTOCOL = HERE / "protocol.json"
RUNS = HERE / "runs"
API_NAMES = ("add", "frob", "neg", "mul", "pointFromX")


class CountedCurve:
    """Count public curve API calls made by a stage, including replay."""

    def __init__(self, curve):
        self.curve = curve
        self.calls = {name: 0 for name in API_NAMES}

    def __getattr__(self, name):
        value = getattr(self.curve, name)
        if name not in self.calls or not callable(value):
            return value

        def counted(*args, **kwargs):
            self.calls[name] += 1
            return value(*args, **kwargs)

        return counted

    def snapshot(self):
        return dict(self.calls)


def delta(after, before):
    return {name: after[name] - before[name] for name in API_NAMES}


def run(degree: int) -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1488"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    case = f"n{degree}_ordinary"
    assert case in protocol["run_order"]
    output = RUNS / f"{case}.json"
    assert not output.exists(), "refuse to overwrite frozen run"
    assert protocol["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert protocol["validation_sha256"] == sha(HERE / "validation.json")
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    cell = protocol["cases"][case]
    assert workload_id(cell["workload"]) == cell["workload_id"]
    onb = field.Onb(degree)
    curve = CountedCurve(curves.Curve(onb))
    orbit = OrbitKey(onb)
    target = tuple(cell["public_target"])
    subgroup_order = cell["subgroup_order"]
    setup_start = time.perf_counter_ns()
    if degree == 53:
        base = read_points()
        assert len(base) == cell["factor_base_actual_B"]
        table_sampler = IndexedBaseSampler(
            base, random.Random(cell["table_seed"]))
        query_sampler = IndexedBaseSampler(
            base, random.Random(cell["query_seed"]))
    else:
        assert degree == 83
        table_sampler = WindowOrbitSampler(
            onb, curve, orbit, cell["cofactor"],
            cell["nominal_window_dimension_d"],
            random.Random(cell["table_seed"]))
        query_sampler = WindowOrbitSampler(
            onb, curve, orbit, cell["cofactor"],
            cell["nominal_window_dimension_d"],
            random.Random(cell["query_seed"]))
    setup_ns = time.perf_counter_ns() - setup_start
    before_table = curve.snapshot()
    table, table_result = pair_table(
        curve, orbit, table_sampler, cell["table_pair_sample_cap"])
    after_table = curve.snapshot()
    table_result["curve_api_calls"] = delta(after_table, before_table)
    result = query_table(
        curve, orbit, query_sampler, table_sampler, table, target,
        subgroup_order, cell["query_pair_sample_cap"],
        int(cell["online_query_wall_cap_seconds"] * 1e9))
    after_query = curve.snapshot()
    result["curve_api_calls"] = delta(after_query, after_table)
    result["online_stage_interval"] = (
        "from target validation after target-independent table ready "
        "through verified relation or declared cap; not an ECDLP solve")
    receipt = {
        "kind": "q1488_matched_window_base_pair_table_stage_run",
        "proposal_id": "Q1488", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4mitm",
        "stage_config_id": cell["stage_config_id"],
        "stage_run_id": cell["stage_run_id"],
        "case": case, "curve_id": cell["curve_id"],
        "degree_n": degree, "workload_id": cell["workload_id"],
        "matched_q1487_workload_id": cell[
            "matched_q1487_workload_id"],
        "target": list(target),
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "factor_base_sampling": cell["factor_base_sampling"],
        "target_independent_base_load_ns": setup_ns,
        "target_independent_table": table_result,
        "ordinary_query": result,
        "verified_relation_count": int(result["relation"] is not None),
        "natural_relation_yield_estimate": None,
        "verified_single_target_dlp": False,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "online_single_target_speedup": None,
        "cpu_isolation_receipt": None,
        "peak_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    RUNS.mkdir(exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case": case, "status": result["status"],
                      "verified": receipt["verified_relation_count"],
                      "table_samples": table_result["samples"],
                      "query_samples": result["samples"]},
                     sort_keys=True), flush=True)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83),
                        required=True)
    args = parser.parse_args()
    run(args.degree)
