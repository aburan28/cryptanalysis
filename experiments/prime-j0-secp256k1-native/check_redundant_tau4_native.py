#!/usr/bin/env python3
"""Replay the native two-orbit tau-four path against the frozen scalar screen."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import lazy_tau_screen as curve
from check_eisenstein_scalar_fixed import LAMBDA_TAU, affine_from_native


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    parser.add_argument("--result", type=Path,
                        default=HERE / "redundant-tau4-result.json")
    parser.add_argument("--mode", choices=("redundant", "coalescent"),
                        default="redundant")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    result_path = args.result.resolve(strict=True)
    result = json.loads(result_path.read_text())
    assert result["schema"] == 1 and result["status"] == "passed"
    assert result["algorithm"] == "dual-orbit-tau4-bounded-rollout"
    cases = result["cases"]
    assert len(cases) == 214
    scalars = [int(row["scalar_hex"], 16) for row in cases]
    request = "".join(f"{scalar:x}\n" for scalar in scalars)
    process = subprocess.run(
        [str(binary), "--scalar-w4-" + args.mode], input=request, text=True,
        capture_output=True, check=True, timeout=120)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(cases), (len(rows), len(cases))
    totals = {panel: {"tau_steps": 0, "mixed_additions": 0,
                      "field_product_proxy": 0} for panel in
              ("frozen_edges", "frozen_random", "holdout_random")}
    recoding_work = {name: 0 for name in
                     ("base_transitions", "look_zero_steps", "look_blocks")}
    for index, (row, expected, scalar) in enumerate(zip(rows, cases, scalars)):
        policy = expected["policies"]["rollout_2"]
        representative = [int(value) for value in row["representative"]]
        assert representative == expected["representative"], index
        assert ((representative[0] + representative[1] * LAMBDA_TAU
                 - scalar) % curve.ORDER == 0), index
        assert row["radix"] == "orbit-w4-" + args.mode, index
        assert row["tau_steps"] == policy["tau_steps"], index
        assert row["nonzero_digits"] == policy["additions"], index
        assert row["alternate_uses"] == policy["alternate_uses"], index
        assert len(row["orbit_counts"]) == 18, index
        assert sum(row["orbit_counts"]) == row["nonzero_digits"], index
        if args.mode == "coalescent":
            for name in recoding_work:
                value = row["recoding_work"][name]
                assert isinstance(value, int) and value >= 0, (index, name)
                recoding_work[name] += value
        else:
            assert row["recoding_work"] is None, index
        cost = 5 * row["tau_steps"] + 11 * row["nonzero_digits"]
        assert cost == policy["field_product_proxy"], index
        assert affine_from_native(row["point"]) == curve.point_multiply(
            scalar % curve.ORDER), index
        total = totals[expected["panel"]]
        total["tau_steps"] += row["tau_steps"]
        total["mixed_additions"] += row["nonzero_digits"]
        total["field_product_proxy"] += cost
    for panel, total in totals.items():
        assert total["field_product_proxy"] == result["totals"][panel]["rollout_2"]
    print(json.dumps({"status": "passed", "mode": args.mode,
                      "verified_cases": len(rows),
                      "totals": totals, "recoding_work": recoding_work,
                      "binary_sha256": digest(binary),
                      "result_sha256": digest(result_path),
                      "checker_sha256": digest(Path(__file__))}, sort_keys=True))


if __name__ == "__main__":
    main()
