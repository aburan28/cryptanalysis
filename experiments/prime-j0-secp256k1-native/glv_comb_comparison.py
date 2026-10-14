#!/usr/bin/env python3
"""Pair fixed-base GLV comb and compact tau-six comb on the same scalars."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

import lazy_tau_screen as curve
from check_eisenstein_scalar_fixed import (
    LAMBDA_TAU, affine_from_native, scalar_text,
)


HERE = Path(__file__).resolve().parent
GLV_ROWS = (4, 8, 9, 10, 11)
TAU_ROWS = (4, 8, 12)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = (-U[1], 303414439467246543595250775667605759171)
K1_BOUND = (abs(U[0] + U[1]) + abs(V[0] + V[1]) + 1) // 2
K2_BOUND = (abs(U[1]) + abs(V[1]) + 1) // 2


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def glv_count(a, b, rows):
    components = (a + b, -b)
    assert abs(components[0]) <= K1_BOUND < 1 << 128
    assert abs(components[1]) <= K2_BOUND < 1 << 128
    width = (128 + rows - 1) // rows
    terms = 0
    active = []
    masks = []
    for column in range(width):
        pair = tuple(sum(((abs(component) >> (row * width + column)) & 1) << row
                         for row in range(rows))
                     for component in components)
        masks.append(pair)
        terms += int(pair[0] != 0) + int(pair[1] != 0)
        if pair != (0, 0):
            active.append(column)
    for component, index in zip(components, (0, 1)):
        rebuilt = sum(sum(((mask[index] >> row) & 1) << (row * width + column)
                          for row in range(rows))
                      for column, mask in enumerate(masks))
        assert rebuilt == abs(component)
    doublings = max(active, default=0)
    additions = max(terms - 1, 0)
    return {"rows": rows, "column_width": width,
            "stored_table_entries": 1 << rows,
            "nonidentity_subset_points": (1 << rows) - 1,
            "shifted_base_doubling_setup_steps": (rows - 1) * width,
            "subset_setup_addition_calls": (1 << rows) - 1 - rows,
            "batch_inversions": 2,
            "doublings": doublings, "mixed_additions": additions,
            "field_product_proxy": 7 * doublings + 11 * additions}


def native_rows(binary, mode, scalars):
    request = "".join(scalar_text(scalar) + "\n" for scalar in scalars)
    process = subprocess.run([str(binary), mode], input=request,
                             text=True, capture_output=True, check=True,
                             timeout=120)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def check_random(binary, count):
    rng = random.Random(20261009)
    order = curve.ORDER
    scalars = [0, 1, -1, order - 1, order, order + 1,
               2 * order - 1, 2 * order + 1, (1 << 256) - 1]
    scalars.extend(rng.randrange(-2 * order, 2 * order) for _ in range(count))
    reference = [curve.point_multiply(scalar % order) for scalar in scalars]
    for mode in ("--scalar-glv-comb8-fixed", "--scalar-glv-comb10-fixed",
                 "--scalar-w6-comb4-fixed", "--scalar-w6-comb8-fixed",
                 "--scalar-w6-comb12-fixed"):
        rows = native_rows(binary, mode, scalars)
        for index, (row, point) in enumerate(zip(rows, reference)):
            assert affine_from_native(row["point"]) == point, (mode, index)
    print(json.dumps({"schema": 1, "status": "passed", "seed": 20261009,
                      "random_scalars": count, "scalar_cases_per_mode": len(scalars),
                      "native_modes": ["glv8", "glv10", "tau4", "tau8", "tau12"],
                      "binary_sha256": sha(binary),
                      "source_sha256": sha(Path(__file__))}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=HERE / "tau6-comb-result.json")
    parser.add_argument("--binary", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    parser.add_argument("--output", type=Path,
                        default=HERE / "glv-comb-comparison.json")
    parser.add_argument("--random-check", type=int, default=0)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    if args.random_check:
        if args.random_check < 0:
            parser.error("random-check must be nonnegative")
        check_random(binary, args.random_check)
        return
    input_path = args.input.resolve(strict=True)
    source = json.loads(input_path.read_text())
    assert source["schema"] == 1 and source["status"] == "passed"
    assert len(source["cases"]) == 214
    scalars = [int(case["scalar_hex"], 16) for case in source["cases"]]
    references = [curve.point_multiply(scalar % curve.ORDER)
                  for scalar in scalars]
    modes = {f"glv{rows}": native_rows(binary,
                                       f"--scalar-glv-comb{rows}-fixed", scalars)
             for rows in (8, 10)}
    modes.update({f"tau{rows}": native_rows(binary,
                                            f"--scalar-w6-comb{rows}-fixed", scalars)
                  for rows in TAU_ROWS})
    totals = {}
    for panel in ("frozen_edges", "frozen_random", "holdout_random"):
        totals[panel] = {f"glv{rows}": Counter() for rows in GLV_ROWS}
        totals[panel].update({f"tau{rows}": Counter() for rows in TAU_ROWS})
    cases = []
    for offset, (case, scalar, reference) in enumerate(zip(source["cases"],
                                                            scalars, references)):
        a, b = case["representative"]
        components = [a + b, -b]
        assert (a + b * LAMBDA_TAU - scalar) % curve.ORDER == 0
        assert (components[0] + components[1] * (1 - LAMBDA_TAU)
                - scalar) % curve.ORDER == 0
        glv = {str(rows): glv_count(a, b, rows) for rows in GLV_ROWS}
        tau = {str(rows): case["comb"][str(rows)] for rows in TAU_ROWS}
        for rows in (8, 10):
            actual = modes[f"glv{rows}"][offset]
            expected = glv[str(rows)]
            assert actual["radix"] == f"glv-comb{rows}-fixed"
            assert list(map(int, actual["representative"])) == [a, b]
            assert list(map(int, actual["glv_components"])) == components
            assert actual["doublings"] == expected["doublings"], offset
            assert actual["nonzero_digits"] == expected["mixed_additions"], offset
            assert affine_from_native(actual["point"]) == reference, (rows, offset)
        for rows in TAU_ROWS:
            actual = modes[f"tau{rows}"][offset]
            expected = tau[str(rows)]
            assert actual["radix"] == f"orbit-w6-comb{rows}-fixed"
            assert actual["tau_steps"] == expected["tau_steps"], offset
            assert actual["nonzero_digits"] == expected["mixed_additions"], offset
            assert affine_from_native(actual["point"]) == reference, (rows, offset)
        for rows, record in glv.items():
            totals[case["panel"]][f"glv{rows}"].update(
                {key: record[key] for key in ("doublings", "mixed_additions",
                                               "field_product_proxy")})
        for rows, record in tau.items():
            totals[case["panel"]][f"tau{rows}"].update(
                {key: record[key] for key in ("tau_steps", "mixed_additions",
                                               "field_product_proxy")})
        cases.append({"index": case["index"], "panel": case["panel"],
                      "scalar_hex": case["scalar_hex"],
                      "representative": [a, b],
                      "glv_components": components,
                      "glv": glv,
                      "tau": {rows: {key: value[key] for key in
                                      ("tau_steps", "mixed_additions",
                                       "field_product_proxy")}
                              for rows, value in tau.items()}})
    output = {"schema": 1, "status": "passed", "curve": "secp256k1",
              "base": "standard-generator", "algorithm": "paired-glv-tau-comb",
              "glv_rows": GLV_ROWS, "tau_rows": TAU_ROWS,
              "glv_component_bounds": [str(K1_BOUND), str(K2_BOUND)],
              "proxy_costs": {"doubling": 7, "tau": 5, "mixed_addition": 11},
              "native_verified_modes": ["glv8", "glv10", "tau4", "tau8", "tau12"],
              "totals": {panel: {mode: dict(counts) for mode, counts in values.items()}
                         for panel, values in totals.items()},
              "cases": cases,
              "input_sha256": sha(input_path),
              "source_sha256": sha(Path(__file__)),
              "binary_sha256": sha(binary),
              "native_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py")}
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "cases": len(cases),
                      "totals": output["totals"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
