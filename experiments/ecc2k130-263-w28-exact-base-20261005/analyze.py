#!/usr/bin/env python3
"""Derive exact W28 source/descendant geometry and counting-only PDP bounds."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal, localcontext
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
CAPACITY = ROOT / "experiments/ecc2k130-263-capacity-gate-20261004/result.json"
W24 = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/analysis.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
CELL_NAMES = ("neither", "source_only", "descendant_only", "both")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_bytes(folder):
    raw = folder / "membership.bin"
    if raw.is_file():
        return raw.read_bytes()
    with gzip.open(folder / "membership.bin.gz", "rb") as stream:
        return stream.read()


def ratio(numerator, denominator, digits=18):
    with localcontext() as context:
        context.prec = 48
        return format(Decimal(numerator) / Decimal(denominator), f".{digits}g")


def paired_count(data, mask_count):
    assert len(data) == (mask_count + 3) // 4
    padding = 4 * len(data) - mask_count
    assert data[-1] >> (2 * (4 - padding)) == 0
    byte_counts = Counter(data)
    cells = [0, 0, 0, 0]
    for byte, frequency in byte_counts.items():
        for slot in range(4):
            cells[(byte >> (2 * slot)) & 3] += frequency
    cells[0] -= padding
    assert min(cells) >= 0 and sum(cells) == mask_count
    return dict(zip(CELL_NAMES, cells))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-one", type=Path, required=True)
    parser.add_argument("--run-two", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    config = json.loads(CONFIG.read_text())
    capacity = json.loads(CAPACITY.read_text())
    w24 = json.loads(W24.read_text())
    route = json.loads(ROUTE.read_text())
    assert sha(ROUTE) == config["route_manifest_sha256"]
    assert sha(W24) == config["parent_w24_analysis_sha256"]
    assert capacity["route_id"] == w24["route_id"] == route["route_id"]
    order = int(capacity["subgroup_order"])
    folders = (args.run_one, args.run_two)
    runs = [json.loads((folder / "summary.json").read_text()) for folder in folders]
    checks = [json.loads((folder / "verification.json").read_text())
              for folder in folders]
    assert all(check["verified"] is True for check in checks)
    assert all(run["status"] == "completed_unverified" for run in runs)
    assert sorted(run["batch_size"] for run in runs) == sorted(config[
        "repetitions_batch_sizes"])
    assert all(run["dimension"] == config["dimension"] for run in runs)
    assert runs[0]["artifacts_sha256"]["membership.bin"] == runs[1][
        "artifacts_sha256"]["membership.bin"]
    first_data = raw_bytes(args.run_one)
    second_data = raw_bytes(args.run_two)
    assert first_data == second_data
    assert hashlib.sha256(first_data).hexdigest() == runs[0][
        "artifacts_sha256"]["membership.bin"]
    mask_count = (1 << config["dimension"]) - 1
    assert len(first_data) == config["raw_membership_bytes"]
    paired = paired_count(first_data, mask_count)
    assert paired == runs[0]["paired_rationality"] == runs[1][
        "paired_rationality"]
    assert all(check["independent_paired_rationality"] == paired
               for check in checks)
    thresholds = {(row["summands"], row["threshold_numerator"],
                   row["threshold_denominator"]): row
                  for row in capacity["rows"]}
    m5_one_percent = thresholds[(5, 1, 100)]["minimum_actual_B"]
    m4_one_percent = thresholds[(4, 1, 100)]["minimum_actual_B"]
    output_rows = {}
    for name in ("source", "descendant"):
        assert runs[0][name] == runs[1][name]
        count = paired["both"] + paired[
            "source_only" if name == "source" else "descendant_only"]
        base = 2 * count
        assert runs[0][name]["actual_usable_points_B"] == base
        assert runs[0][name]["sign_folded_columns"] == count
        stages = {}
        for summands in (4, 5):
            multisets = comb(base + summands - 1, summands)
            stages[str(summands)] = {
                "max_unordered_multisets": str(multisets),
                "uniform_nonzero_support_numerator_upper":
                    str(min(multisets, order - 1)),
                "uniform_nonzero_support_denominator": str(order - 1),
                "uniform_nonzero_support_upper_decimal":
                    ratio(min(multisets, order - 1), order - 1),
                "formal_mean_representations_over_all_targets":
                    ratio(multisets, order),
            }
        output_rows[name] = {
            "rational_w": count,
            "actual_usable_B": base,
            "sign_folded_columns_before_other_reductions": count,
            "raw_17_byte_log_vector_bytes_if_all_columns_logged": 17 * count,
            "passes_m5_one_percent_necessary_B_threshold": base >= m5_one_percent,
            "passes_m4_one_percent_necessary_B_threshold": base >= m4_one_percent,
            "actual_B_minus_corresponding_W24_B": base - w24["rows"][name][
                "actual_usable_B"],
            "counting_only": stages,
            "frobenius_closed_column_count": None,
        }
    difference = output_rows["descendant"]["rational_w"] - output_rows[
        "source"]["rational_w"]
    difference_pp = ratio(100 * difference, mask_count)
    result = {
        "schema": "ecc2k130-263-w28-exact-base-analysis-v1",
        "status": "exact_base_geometry_and_counting_bounds_only",
        "candidate_id": None,
        "route_id": route["route_id"],
        "dimension": config["dimension"],
        "nonzero_w_population": mask_count,
        "paired_rationality_census": paired,
        "exact_descendant_minus_source_rational_w": difference,
        "exact_descendant_minus_source_percentage_points": difference_pp,
        "exact_descendant_minus_source_usable_B": 2 * difference,
        "predeclared_material_descendant_gain_percentage_points": config[
            "predeclared_material_descendant_gain_percentage_points"],
        "material_descendant_geometry_gain": Decimal(difference_pp) >= Decimal(
            config["predeclared_material_descendant_gain_percentage_points"]),
        "m5_one_percent_minimum_necessary_B": m5_one_percent,
        "m4_one_percent_minimum_necessary_B": m4_one_percent,
        "rows": output_rows,
        "verified_repetitions": [
            {"batch_size": run["batch_size"],
             "summary_sha256": sha(folder / "summary.json"),
             "verification_sha256": sha(folder / "verification.json"),
             "archive_sha256": sha(folder / "archive.json")
                 if (folder / "archive.json").is_file() else None,
             "membership_sha256": run["artifacts_sha256"]["membership.bin"]}
            for run, folder in zip(runs, folders)],
        "inputs_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in (CAPACITY, W24, ROUTE, CONFIG)},
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
