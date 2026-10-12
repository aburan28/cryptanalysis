#!/usr/bin/env python3
"""Replay the balanced 33-edge evaluator against the frozen radius-two parent."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from radius2_graph_screen import graph, mask_stream, matching_atlas
from radius3_balanced_screen import COUNT, SEEDS
from screen_coset_representatives import N
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
REFERENCE_SHA256 = "b9c194c9105ef41daf95cef229d72434d5421e72ffd714dc32ed8ee7bb41f6ad"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, mode, scalars):
    process = subprocess.run(
        [str(binary), f"--scalar-w6-comb13-hex9-{mode}-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        capture_output=True, text=True, check=True, timeout=1200,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output already exists")
    reference = args.reference.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    assert sha(reference) == REFERENCE_SHA256
    screen = json.loads((HERE / "radius3-balanced-screen-result.json").read_text())
    assert screen["status"] == "screen_passed" and screen["count_per_panel"] == COUNT
    assert screen["protocol_sha256"] == sha(HERE / "RADIUS3_BALANCED_PROTOCOL.md")
    assert screen["checker_sha256"] == sha(HERE / "radius3_balanced_screen.py")
    source_path = HERE / "src/bin/eisenstein_fixed.rs"
    block = re.search(
        r"const GRAPH33_EDGES: \[\(usize, usize\); 33\] = \[(.*?)\];",
        source_path.read_text(), re.S)
    assert block is not None
    native_edges = [(int(left), int(right)) for left, right in
                    re.findall(r"\((\d+),\s*(\d+)\)", block.group(1))]
    assert native_edges == [tuple(edge) for edge in screen["edges"]["g33"]]
    frozen = json.loads((HERE / "hex9-cover-result.json").read_text())
    assert frozen["status"] == "passed" and len(frozen["frozen"]["rows"]) == 214
    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    scalars = [0, 1, N - 1, N, N + 1]
    ranges = {"edge": (0, len(scalars))}
    start = len(scalars)
    scalars.extend(int(row["scalar_hex"], 16) for row in frozen["frozen"]["rows"])
    ranges["frozen"] = (start, len(scalars))
    start = len(scalars)
    scalars.extend(int(row["scalar_hex"], 16) for row in fixture["cases"])
    ranges["fixture"] = (start, len(scalars))
    for name, seed in zip(("design", "holdout"), SEEDS):
        start = len(scalars)
        rng = random.Random(seed)
        scalars.extend(rng.randrange(N) for _ in range(COUNT))
        ranges[name] = (start, len(scalars))
    assert len(scalars) == 8540
    old_rows = run(reference, "radius2", scalars)
    new_rows = run(candidate, "graph33", scalars)
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    atlas2 = matching_atlas(graph(2))
    atlas33 = matching_atlas(native_edges)
    totals = {name: Counter() for name in ranges}
    independent = 0
    for index, (scalar, old, new) in enumerate(zip(scalars, old_rows, new_rows)):
        name = next(name for name, (lo, hi) in ranges.items() if lo <= index < hi)
        assert old["representative"] == new["representative"], index
        assert old["tau_steps"] == new["tau_steps"], index
        assert affine_from_native(old["point"]) == affine_from_native(new["point"]), index
        for key in ("top_repaired", "coset_rank", "valid_representatives",
                    "attempted_representatives"):
            assert old["recoding_work"][key] == new["recoding_work"][key], (index, key)
        masks = mask_stream(new, table)
        count2 = sum(len(atlas2[mask]) for mask in masks)
        count33 = sum(len(atlas33[mask]) for mask in masks)
        assert old["recoding_work"]["pair_fusions"] == count2, index
        assert new["recoding_work"]["pair_fusions"] == count33, index
        assert count33 >= count2, index
        assert old["nonzero_digits"] == new["nonzero_digits"] + count33 - count2, index
        if name == "fixture":
            row = fixture["cases"][index - ranges["fixture"][0]]
            expected = (int(row["expected_x_hex"], 16), int(row["expected_y_hex"], 16))
            assert affine_from_native(new["point"]) == expected, index
        if name == "edge" or (name == "holdout" and
                             index < ranges["holdout"][0] + 256):
            assert affine_from_native(new["point"]) == curve.point_multiply(scalar % N), index
            independent += 1
        totals[name].update({"cases": 1, "radius2_fusions": count2,
                             "graph33_fusions": count33,
                             "radius2_adds": old["nonzero_digits"],
                             "graph33_adds": new["nonzero_digits"],
                             "tau_steps": new["tau_steps"]})
    result = {"schema": 1, "status": "passed", "cases": len(scalars),
              "independent_points": independent,
              "fixture_expected_points": len(fixture["cases"]),
              "ranges": ranges, "totals": {name: dict(row) for name, row in totals.items()},
              "reference_binary_sha256": sha(reference),
              "candidate_binary_sha256": sha(candidate),
              "candidate_source_sha256": sha(source_path),
              "verifier_sha256": sha(Path(__file__)),
              "screen_sha256": sha(HERE / "radius3-balanced-screen-result.json"),
              "fixture_sha256": sha(fixture_path)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "independent_points": independent, "totals": result["totals"],
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
