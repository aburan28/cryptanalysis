#!/usr/bin/env python3
"""Replay the radius-two matching atlas against the frozen tau path binary."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from radius2_graph_screen import COUNT, SEEDS, graph, mask_stream, matching_atlas
from screen_coset_representatives import N
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
REFERENCE_BINARY_SHA256 = "e8ffd24be7ea2c976b9ab8f31cea7d7d1cda0b6fbeb35b7e5b95ba2e1ae411aa"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, mode, scalars):
    process = subprocess.run(
        [str(binary), f"--scalar-w6-comb13-hex9-{mode}-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        capture_output=True, text=True, check=True, timeout=600,
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
    assert sha(reference) == REFERENCE_BINARY_SHA256
    screen = json.loads((HERE / "radius2-graph-screen-result.json").read_text())
    assert screen["status"] == "screen_passed" and screen["count_per_panel"] == COUNT
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
    old_rows = run(reference, "path", scalars)
    new_rows = run(candidate, "radius2", scalars)
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    atlas1 = matching_atlas(graph(1))
    atlas2 = matching_atlas(graph(2))
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
        count1 = sum(len(atlas1[mask]) for mask in masks)
        count2 = sum(len(atlas2[mask]) for mask in masks)
        assert old["recoding_work"]["pair_fusions"] == count1, index
        assert new["recoding_work"]["pair_fusions"] == count2, index
        assert count2 >= count1, index
        assert old["nonzero_digits"] == new["nonzero_digits"] + count2 - count1, index
        if name == "fixture":
            row = fixture["cases"][index - ranges["fixture"][0]]
            expected = (int(row["expected_x_hex"], 16), int(row["expected_y_hex"], 16))
            assert affine_from_native(new["point"]) == expected, index
        if name == "edge" or (name == "holdout" and
                             index < ranges["holdout"][0] + 256):
            assert affine_from_native(new["point"]) == curve.point_multiply(scalar % N), index
            independent += 1
        totals[name].update({"cases": 1, "path_fusions": count1,
                             "radius2_fusions": count2,
                             "path_adds": old["nonzero_digits"],
                             "radius2_adds": new["nonzero_digits"],
                             "tau_steps": new["tau_steps"]})
    result = {"schema": 1, "status": "passed", "cases": len(scalars),
              "independent_points": independent,
              "fixture_expected_points": len(fixture["cases"]),
              "ranges": ranges, "totals": {name: dict(row) for name, row in totals.items()},
              "reference_binary_sha256": sha(reference),
              "candidate_binary_sha256": sha(candidate),
              "candidate_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "verifier_sha256": sha(Path(__file__)),
              "fixture_sha256": sha(fixture_path)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "independent_points": independent, "totals": result["totals"],
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
