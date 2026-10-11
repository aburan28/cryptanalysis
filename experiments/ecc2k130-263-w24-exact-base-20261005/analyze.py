#!/usr/bin/env python3
"""Derive exact W24 source/descendant geometry and counting-only PDP bounds."""

import argparse
import gzip
import hashlib
import json
from decimal import Decimal, localcontext
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/ecc2k130-263-capacity-gate-20261004/result.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_bytes(folder, name):
    raw = folder / name
    if raw.is_file():
        return raw.read_bytes()
    with gzip.open(folder / f"{name}.gz", "rb") as stream:
        return stream.read()


def ratio(numerator, denominator, digits=18):
    with localcontext() as context:
        context.prec = 48
        return format(Decimal(numerator) / Decimal(denominator), f".{digits}g")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-one", type=Path, required=True)
    parser.add_argument("--run-two", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    parent = json.loads(PARENT.read_text())
    route = json.loads(ROUTE.read_text())
    assert parent["status"] == "exact_counting_complete"
    assert parent["route_id"] == route["route_id"]
    assert parent["subgroup_order"] == str(route["curve_nodes"]["source"][
        "subgroup_order"])
    order = int(parent["subgroup_order"])
    runs = [json.loads((folder / "summary.json").read_text())
            for folder in (args.run_one, args.run_two)]
    verifications = [json.loads((folder / "verification.json").read_text())
                     for folder in (args.run_one, args.run_two)]
    assert all(row["verified"] is True for row in verifications)
    assert all(row["status"] == "completed_unverified" for row in runs)
    assert runs[0]["batch_size"] != runs[1]["batch_size"]
    assert runs[0]["dimension"] == runs[1]["dimension"] == 24
    for name in ("source-masks.bin", "descendant-masks.bin", "flags.bin"):
        assert runs[0]["artifacts_sha256"][name] == runs[1][
            "artifacts_sha256"][name]
        assert hashlib.sha256(raw_bytes(args.run_one, name)).hexdigest() == runs[0][
            "artifacts_sha256"][name]
        assert hashlib.sha256(raw_bytes(args.run_two, name)).hexdigest() == runs[1][
            "artifacts_sha256"][name]
    for name in ("source", "descendant"):
        assert runs[0][name] == runs[1][name]
        assert runs[0][name]["two_element_reciprocal_pairs"] == 0
        assert runs[0][name]["fixed_reciprocal_points"] == 0
        assert runs[0][name]["actual_usable_points_B"] == 2 * runs[0][name][
            "rational_w"]
    flags = raw_bytes(args.run_one, "flags.bin")
    assert len(flags) == (1 << 24) - 1
    paired = {"both": 0, "source_only": 0, "descendant_only": 0, "neither": 0}
    for byte in flags:
        assert byte in (0, 5, 80, 85), byte  # no reciprocal partners
        src = bool(byte & 1)
        dst = bool(byte & 16)
        key = ("both" if src and dst else "source_only" if src else
               "descendant_only" if dst else "neither")
        paired[key] += 1
    source_r = paired["both"] + paired["source_only"]
    descendant_r = paired["both"] + paired["descendant_only"]
    assert source_r == runs[0]["source"]["rational_w"]
    assert descendant_r == runs[0]["descendant"]["rational_w"]
    assert sum(paired.values()) == len(flags)
    thresholds = {(row["summands"], row["threshold_numerator"],
                   row["threshold_denominator"]): row
                  for row in parent["rows"]}
    m6_one_percent = thresholds[(6, 1, 100)]["minimum_actual_B"]
    output_rows = {}
    for name in ("source", "descendant"):
        counts = runs[0][name]
        base = counts["actual_usable_points_B"]
        stages = {}
        for summands in (5, 6):
            multiset_count = comb(base + summands - 1, summands)
            stages[str(summands)] = {
                "max_unordered_multisets": str(multiset_count),
                "uniform_nonzero_support_numerator_upper":
                    str(min(multiset_count, order - 1)),
                "uniform_nonzero_support_denominator": str(order - 1),
                "uniform_nonzero_support_upper_decimal":
                    ratio(min(multiset_count, order - 1), order - 1),
                "formal_mean_representations_over_all_targets":
                    ratio(multiset_count, order),
            }
        output_rows[name] = {
            "rational_w": counts["rational_w"],
            "actual_usable_B": base,
            "sign_folded_columns_before_other_reductions": counts[
                "sign_folded_columns"],
            "raw_17_byte_log_vector_bytes_if_all_columns_logged": 17 * counts[
                "sign_folded_columns"],
            "passes_m6_one_percent_necessary_B_threshold": base >= m6_one_percent,
            "counting_only": stages,
        }
    result = {
        "schema": "ecc2k130-263-w24-exact-base-analysis-v1",
        "status": "exact_base_geometry_and_counting_bounds_only",
        "candidate_id": None,
        "route_id": route["route_id"],
        "dimension": 24,
        "nonzero_w_population": len(flags),
        "paired_rationality_census": paired,
        "exact_descendant_minus_source_rational_w": descendant_r - source_r,
        "exact_descendant_minus_source_percentage_points":
            ratio(100 * (descendant_r - source_r), len(flags)),
        "exact_descendant_minus_source_usable_B": output_rows[
            "descendant"]["actual_usable_B"] - output_rows["source"][
                "actual_usable_B"],
        "m6_one_percent_minimum_necessary_B": m6_one_percent,
        "rows": output_rows,
        "verified_repetitions": [
            {"batch_size": run["batch_size"],
             "summary_sha256": sha(folder / "summary.json"),
             "verification_sha256": sha(folder / "verification.json"),
             "archive_sha256": sha(folder / "archive.json")
                 if (folder / "archive.json").is_file() else None,
             "flags_sha256": run["artifacts_sha256"]["flags.bin"]}
            for run, folder in zip(runs, (args.run_one, args.run_two))],
        "inputs_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in (PARENT, ROUTE)},
        "source_sha256": sha(Path(__file__)),
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"source_B": output_rows["source"]["actual_usable_B"],
                      "descendant_B": output_rows["descendant"]["actual_usable_B"],
                      "paired": paired}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python disables required assertions")
    main()
