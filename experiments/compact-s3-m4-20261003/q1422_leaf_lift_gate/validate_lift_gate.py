#!/usr/bin/env python3
"""Validate the exact nonzero-x curve-lift gate in Sage and native code."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1420_root_theory"
sys.path.insert(0, str(HERE.parent))

from run_probe import field, sha  # noqa: E402
from s3_root_oracle import half_trace  # noqa: E402


def sage_check(onb, coords):
    assert 0 < coords < 1 << onb.m
    x = onb.fromCoords(coords)
    inverse = onb.inv(x)
    chi = onb.trace(onb.add(x, inverse))
    rhs = onb.add(x, onb.sqr(inverse))
    assert onb.trace(rhs) == chi
    if chi == 0:
        z = half_trace(onb, rhs)
        assert onb.add(onb.sqr(z), z) == rhs
        y = onb.mul(x, z)
        lhs = onb.add(onb.sqr(y), onb.mul(x, y))
        curve_rhs = onb.add(onb.mul(onb.sqr(x), x), onb.one())
        assert lhs == curve_rhs
    return chi == 0


def build(n):
    onb = field.Onb(n)
    weight = {53: 3, 83: 5}[n]
    rng = random.Random(1422 * 1000 + n)
    sparse = set()
    while len(sparse) < 64:
        width = rng.randint(1, weight)
        bits = rng.sample(range(n), width)
        sparse.add(sum(1 << bit for bit in bits))
    uniform = set()
    while len(uniform) < 64:
        uniform.add(rng.randrange(1, 1 << n))
    parent = json.loads((PARENT / "runs" / f"n{n}_full_lock" /
                         "receipt.json").read_text())
    witnesses = {int(raw) for raw in parent["model_check"]["raw_leaf_x"]}
    samples = sorted(sparse | uniform | witnesses)
    expected = [sage_check(onb, x) for x in samples]
    assert all(sage_check(onb, x) for x in witnesses)
    cli = HERE / "lift_gate_cli"
    assert cli.is_file()
    process = subprocess.run(
        [str(cli), str(PARENT / f"n{n}_field.txt")],
        input="".join(f"{x:x}\n" for x in samples), text=True,
        capture_output=True, check=True)
    rows = process.stdout.splitlines()
    assert len(rows) == len(samples)
    actual = []
    for x, row in zip(samples, rows):
        encoded, result = row.split()
        assert int(encoded, 16) == x
        actual.append(bool(int(result)))
    assert actual == expected
    return {
        "kind": "q1422_lift_gate_validation",
        "proposal_id": "Q1422", "candidate_id": None,
        "status": "PASS", "degree_n": n,
        "curve_id": parent["curve_id"],
        "sampled_sparse_x": len(sparse),
        "sampled_uniform_x": len(uniform),
        "archived_witness_x": len(witnesses),
        "distinct_checked_x": len(samples),
        "curve_lift_true": sum(expected),
        "curve_lift_false": len(samples) - sum(expected),
        "normal_basis_trace_rule": "parity of ONB coordinates",
        "curve_lift_rule": "Tr(x + x^-1)=0 for nonzero x on y^2+xy=x^3+1",
        "seed": 1422 * 1000 + n,
        "source_sha256": sha(Path(__file__)),
        "lift_gate_header_sha256": sha(HERE / "lift_gate.hpp"),
        "lift_gate_cli_source_sha256": sha(HERE / "lift_gate_cli.cpp"),
        "lift_gate_cli_binary_sha256": sha(cli),
        "field_bridge_sha256": sha(PARENT / f"n{n}_field.txt"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "archived_control_receipt_sha256": sha(
            PARENT / "runs" / f"n{n}_full_lock" / "receipt.json"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = HERE / f"n{args.degree}_lift_validation.json"
    content = json.dumps(build(args.degree), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert output.read_text() == content
    else:
        assert not output.exists()
        output.write_text(content)
    print(output)


if __name__ == "__main__":
    main()
