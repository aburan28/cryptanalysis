#!/usr/bin/env python3
"""Paired n53/n83 x-only quotient queries with affine and batch inversion."""

import argparse
import collections
import json
import platform
import resource
import statistics
from pathlib import Path

import curves
from batch_x_only import query_prefix_batch
from compare_x_only import build_index, query_prefix
from perf_probe import COFACTOR, base_prefix, sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSALS = {53: "Q1011", 83: "Q1012"}


class CountingField:
    """Count public field API operations; xors inside the batch remain separate."""

    def __init__(self, field):
        self.field = field
        self.counts = collections.Counter()

    def __getattr__(self, name):
        return getattr(self.field, name)

    def add(self, a, b):
        self.counts["add"] += 1
        return self.field.add(a, b)

    def mul(self, a, b):
        self.counts["mul"] += 1
        return self.field.mul(a, b)

    def sqr(self, a):
        self.counts["sqr"] += 1
        return self.field.sqr(a)

    def inv(self, a):
        self.counts["inv"] += 1
        return self.field.inv(a)

    def frob(self, a, k):
        self.counts["frob"] += 1
        return self.field.frob(a, k)


def measured_query(onb, index, target, degree, canonicalize, lookups, variant):
    counted_field = CountingField(onb)
    curve = curves.Curve(counted_field)
    query = query_prefix if variant == "affine" else query_prefix_batch
    result = query(curve, index, target, degree, canonicalize, lookups)
    result["field_api_operations"] = dict(counted_field.counts)
    result["field_api_operation_boundary"] = (
        "public Curve/Field calls during the target prefix; batch formula xors and "
        "internal work of one field inversion or multiplication are not decomposed")
    return result


def run(degree, blocks, repetitions, lookups):
    reference_path = HERE / "runs" / f"n{degree}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    previous_path = HERE / "runs" / f"n{degree}_x_only_comparison.json"
    previous = json.loads(previous_path.read_text())
    order = int(reference["subgroup_order"])
    assert curves.curveOrder(degree) == COFACTOR[degree] * order
    onb, curve, base, reps, base_info = base_prefix(
        degree, COFACTOR[degree], order, 2)
    assert base_info["base_sha256"] == reference["base"]["base_sha256"]
    canonicalize = XOnlyCycle(onb)
    index, build = build_index(curve, base, reps, degree, canonicalize)
    assert build["index_sha256"] == previous["index_builds"]["xonly"]["index_sha256"]
    target = tuple(reference["workload"]["target"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    assert curve.mul(generator, reference["target_fixture_scalar"]) == target
    samples = []
    for block in range(1, blocks + 1):
        for variant in (("affine", "batch") if block % 2 else ("batch", "affine")):
            measured = [measured_query(onb, index, target, degree,
                                       canonicalize, lookups, variant)
                        for _ in range(repetitions)]
            assert len({tuple(row["verified_hit_positions"]) for row in measured}) == 1
            samples.append({"variant": variant,
                            "proposal_id": PROPOSALS[degree] if variant == "batch" else
                                ("Q1009" if degree == 53 else "Q1010"),
                            "run_id": f"{PROPOSALS[degree] if variant == 'batch' else ('Q1009' if degree == 53 else 'Q1010')}W{reference['workload_id']}R{block}",
                            "block": block, "repetitions": measured,
                            "median_wall_ns": int(statistics.median(
                                row["wall_ns"] for row in measured))})
        assert [row["verified_hit_positions"] for row in samples[-1]["repetitions"]] == [
            row["verified_hit_positions"] for row in samples[-2]["repetitions"]]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak *= 1024
    return {"kind": "paired_bounded_x_only_batch_inversion_stage",
            "candidate_id": None,
            "claim_boundary": "small selected-base bounded query prefixes only; no ordinary relation yield, full DLP, or calibrated field-equivalent solve work",
            "proposal_id": PROPOSALS[degree], "curve_id": reference["curve_id"],
            "curve_identity_record": reference["curve_identity_record"],
            "workload_id": "W" + reference["workload_id"],
            "target": target, "target_fixture_scalar_replay_verified": True,
            "isogeny": "none", "endomorphism_order_conductor": None,
            "factor_base": {"nominal_normal_x_weight": 2,
                            "selected_rational_x_orbits": 2,
                            "geometric_points_before_projection": 4 * degree,
                            "actual_usable_points_B_before_folding": len(base),
                            "effective_columns_after_sign_frobenius_folding": len(reps),
                            "base_sha256": base_info["base_sha256"]},
            "index_build": build,
            "lookup_budget_per_repetition": lookups,
            "paired_blocks": blocks, "repetitions_per_block": repetitions,
            "samples": samples, "peak_process_rss_bytes": peak,
            "python": platform.python_version(), "machine": platform.machine(),
            "source_sha256": sha(Path(__file__)),
            "dependency_sha256": {name: sha(HERE / name) for name in (
                "batch_x_only.py", "compare_x_only.py", "x_only_cycle.py",
                "cycle_canonical.py", "perf_probe.py", "quotient_pair_probe.py",
                "curves.py", "field.py")},
            "frozen_reference_sha256": sha(reference_path),
            "prior_x_only_receipt_sha256": sha(previous_path),
            "verified_single_target_dlp": False,
            "verified_full_dlp_work_log2": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--blocks", type=int, default=6)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--lookups", type=int, default=2048)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.blocks, args.repetitions, args.lookups) < 1:
        parser.error("blocks, repetitions, and lookups must be positive")
    report = run(args.degree, args.blocks, args.repetitions, args.lookups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    medians = {variant: statistics.median(row["median_wall_ns"] for row in
             report["samples"] if row["variant"] == variant)
             for variant in ("affine", "batch")}
    print(json.dumps({"curve_id": report["curve_id"],
                      "factor_base_B": report["factor_base"][
                          "actual_usable_points_B_before_folding"],
                      "median_wall_ns": medians,
                      "affine_over_batch": medians["affine"] / medians["batch"]}))


if __name__ == "__main__":
    main()
