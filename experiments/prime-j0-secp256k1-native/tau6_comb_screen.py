#!/usr/bin/env python3
"""Certify a bounded-width, fixed-generator tau-six comb on frozen scalars."""

import argparse
from functools import cache
import hashlib
from math import isqrt
import json
from pathlib import Path
import subprocess

from check_eisenstein_scalar_fixed import (
    LAMBDA_TAU, affine_from_native, scalar_text,
)
import lazy_tau_screen as curve
import redundant_tau4_screen as ring
import width6_tau_screen as atlas


HERE = Path(__file__).resolve().parent
ROWS = (1, 2, 3, 4, 6, 8)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = (-U[1], 303414439467246543595250775667605759171)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def universal_span():
    # Center rounding puts one candidate in the closed half-basis square.
    # The Eisenstein norm is convex, so a vertex maximizes it there.
    bound = (max(ring.norm((U[0] + V[0], U[1] + V[1])),
                 ring.norm((U[0] - V[0], U[1] - V[1]))) + 3) // 4

    @cache
    def remaining(n):
        if n <= 1:
            return 0
        # sqrt(n) < isqrt(n)+1 and sqrt(217) < 15. The actual nonzero
        # six-step quotient norm is at most this integer upper bound.
        quotient = ((isqrt(n) + 16) ** 2) // 729
        assert quotient < n
        return max(1 + remaining(n // 3), 6 + remaining(quotient))

    steps = remaining(bound)
    assert steps == 168
    return steps + 1, bound, remaining.cache_info().currsize


def digit_stream(start, table, span):
    terminal = {(0, 0)} | {digit for digit, _ in table.values()}
    z = start
    digits = []
    while z != (0, 0):
        if z in terminal:
            digits.append(z)
            break
        if z[0] % 3 == 0:
            digits.append(None)
            z = ring.zero_quotient(z)
        else:
            digit = table[(z[0] % 27, z[1] % 27)][0]
            digits.append(digit)
            digits.extend([None] * 5)
            z = atlas.quotient_six(z, digit)
        assert len(digits) <= span
    assert len(digits) <= span
    rebuilt = (0, 0)
    for digit in reversed(digits):
        rebuilt = ring.tau(rebuilt)
        if digit is not None:
            rebuilt = (rebuilt[0] + digit[0], rebuilt[1] + digit[1])
    assert rebuilt == start
    return digits


def comb_record(digits, rows, span):
    width = (span + rows - 1) // rows
    assert len(digits) <= rows * width
    active_columns = [index % width for index, digit in enumerate(digits)
                      if digit is not None]
    additions = max(len(active_columns) - 1, 0)
    tau_steps = max(active_columns, default=0)
    return {"rows": rows, "column_width": width,
            "point_orbits": 81 * rows,
            "affine_unit_images_if_materialized": 243 * rows,
            "shifted_base_tau_setup_steps": (rows - 1) * width,
            "seed_graph_setup_additions": 80 * rows,
            "batch_inversions": 1 if rows == 1 else 2,
            "tau_steps": tau_steps, "mixed_additions": additions,
            "field_product_proxy": 5 * tau_steps + 11 * additions}


def check_native(result_path, binary_path):
    result = json.loads(result_path.read_text())
    assert result["schema"] == 1 and result["status"] == "passed"
    cases = result["cases"]
    assert len(cases) == 214
    scalars = [int(case["scalar_hex"], 16) for case in cases]
    reference_points = [curve.point_multiply(scalar % curve.ORDER)
                        for scalar in scalars]
    request = "".join(scalar_text(scalar) + "\n" for scalar in scalars)
    for rows in (4, 8):
        mode = f"orbit-w6-comb{rows}-fixed"
        process = subprocess.run(
            [str(binary_path), f"--scalar-w6-comb{rows}-fixed"],
            input=request, text=True, capture_output=True, check=True,
            timeout=120)
        actual = [json.loads(line) for line in process.stdout.splitlines()]
        assert len(actual) == len(cases)
        for case, point, output in zip(cases, reference_points, actual):
            index = case["index"]
            expected = case["comb"][str(rows)]
            assert output["radix"] == mode, index
            assert list(map(int, output["representative"])) == case["representative"], index
            assert output["tau_steps"] == expected["tau_steps"], index
            assert output["nonzero_digits"] == expected["mixed_additions"], index
            counts = output["orbit_counts"]
            assert len(counts) == 81 and sum(counts) == expected["mixed_additions"], index
            assert affine_from_native(output["point"]) == point, (rows, index)
    print(json.dumps({"schema": 1, "status": "passed",
                      "scalar_cases_per_mode": len(cases),
                      "native_modes": [4, 8],
                      "binary_sha256": sha(binary_path),
                      "native_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
                      "screen_sha256": sha(Path(__file__)),
                      "result_sha256": sha(result_path),
                      "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py")},
                     sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=HERE / "width6-tau-result.json")
    parser.add_argument("--output", type=Path,
                        default=HERE / "tau6-comb-result.json")
    parser.add_argument("--check-native", action="store_true")
    parser.add_argument("--binary", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    args = parser.parse_args()
    if args.check_native:
        check_native(args.output.resolve(strict=True), args.binary.resolve(strict=True))
        return
    input_path = args.input.resolve(strict=True)
    source = json.loads(input_path.read_text())
    assert source["schema"] == 1 and source["status"] == "passed"
    assert len(source["cases"]) == 214
    table, seeds, max_norm = atlas.build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    span, norm_bound, bound_states = universal_span()
    assert span == 169
    panels = ("frozen_edges", "frozen_random", "holdout_random")
    totals = {panel: {str(rows): {"tau_steps": 0, "mixed_additions": 0,
                                "field_product_proxy": 0} for rows in ROWS}
              for panel in panels}
    cases = []
    for case in source["cases"]:
        scalar = int(case["scalar_hex"], 16)
        start = tuple(case["representative"])
        assert (start[0] + start[1] * LAMBDA_TAU - scalar) % curve.ORDER == 0
        digits = digit_stream(start, table, span)
        residue = 0
        power = 1
        for digit in digits:
            if digit is not None:
                residue = (residue +
                           (digit[0] + digit[1] * LAMBDA_TAU) * power) % curve.ORDER
            power = power * LAMBDA_TAU % curve.ORDER
        assert residue == scalar % curve.ORDER
        baseline = case["methods"]["width_six"]
        assert len(digits) == baseline["tau_steps"] + 1 or not digits
        assert max(sum(digit is not None for digit in digits) - 1, 0) == baseline["additions"]
        records = {str(rows): comb_record(digits, rows, span) for rows in ROWS}
        assert records["1"]["field_product_proxy"] == baseline["field_product_proxy"]
        for rows, record in records.items():
            for key in ("tau_steps", "mixed_additions", "field_product_proxy"):
                totals[case["panel"]][rows][key] += record[key]
        cases.append({"index": case["index"], "panel": case["panel"],
                      "scalar_hex": case["scalar_hex"],
                      "representative": case["representative"],
                      "digit_count": len(digits), "comb": records})
    output = {"schema": 1, "status": "passed", "curve": "secp256k1",
              "base": "standard-generator", "algorithm": "tau6-unit-orbit-comb",
              "rows": ROWS, "universal_digit_span": span,
              "short_representative_norm_upper_bound": str(norm_bound),
              "bound_recurrence_states": bound_states,
              "digit_orbits_per_row": 81,
              "totals": totals, "cases": cases,
              "input_sha256": sha(input_path),
              "source_sha256": sha(Path(__file__)),
              "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py")}
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "cases": len(cases),
                      "totals": totals, "result_sha256": sha(args.output)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
