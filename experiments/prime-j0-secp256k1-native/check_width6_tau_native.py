#!/usr/bin/env python3
"""Replay the frozen width-six tau panel against the native point path."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import lazy_tau_screen as curve
from check_eisenstein_scalar_fixed import LAMBDA_TAU, affine_from_native, scalar_text


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path,
                        default=directory / "target/release/eisenstein_fixed")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    frozen = directory / "width6-tau-result.json"
    cases = json.loads(frozen.read_text())["cases"]
    scalars = [int(case["scalar_hex"], 16) for case in cases]
    request = "".join(scalar_text(scalar) + "\n" for scalar in scalars)
    process = subprocess.run([str(binary), "--scalar-w6-fixed"], input=request,
                             text=True, capture_output=True, check=True,
                             timeout=max(120, 10 * len(cases)))
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(cases), (len(rows), len(cases))

    panels = {}
    for case, scalar, row in zip(cases, scalars, rows):
        index = case["index"]
        expected = case["methods"]["width_six"]
        assert row["radix"] == "orbit-w6-fixed", index
        representative = tuple(map(int, row["representative"]))
        assert list(representative) == case["representative"], index
        assert (representative[0] + representative[1] * LAMBDA_TAU - scalar) % curve.ORDER == 0, index
        steps = row["tau_steps"]
        additions = row["nonzero_digits"]
        counts = row["orbit_counts"]
        assert steps == expected["tau_steps"], index
        assert additions == expected["additions"], index
        assert len(counts) == 81 and sum(counts) == additions, index
        assert 5 * steps + 11 * additions == expected["field_product_proxy"], index
        actual_point = affine_from_native(row["point"])
        reference_point = curve.point_multiply(scalar % curve.ORDER)
        assert actual_point == reference_point, (index, scalar)
        panel = panels.setdefault(case["panel"], {"cases": 0, "tau_steps": 0,
                                                  "mixed_additions": 0,
                                                  "field_product_proxy": 0})
        panel["cases"] += 1
        panel["tau_steps"] += steps
        panel["mixed_additions"] += additions
        panel["field_product_proxy"] += expected["field_product_proxy"]

    print(json.dumps({
        "schema": 1, "status": "passed", "scalar_cases": len(cases),
        "digit_orbits": 81, "panels": panels,
        "binary_sha256": digest(binary),
        "native_source_sha256": digest(directory / "src/bin/eisenstein_fixed.rs"),
        "verifier_sha256": digest(Path(__file__)),
        "frozen_result_sha256": digest(frozen),
        "curve_reference_sha256": digest(directory / "lazy_tau_screen.py"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
