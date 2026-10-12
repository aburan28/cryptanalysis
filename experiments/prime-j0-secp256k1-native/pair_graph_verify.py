#!/usr/bin/env python3
"""Check the adaptive pair path against the compact six-edge implementation."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from pair_graph_screen import COUNT, EVEN_EDGES, SEEDS, fusions, path_fusions
from screen_coset_representatives import N
from tau6_comb_screen import digit_stream
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
EXPECTED_REFERENCE_SHA256 = "2b2def850cc37cb06815590e1b7921fb3d7debe5453d64287c84341e76fcb18b"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, mode, scalars):
    process = subprocess.run(
        [str(binary), f"--scalar-w6-comb13-hex9-{mode}-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        text=True, capture_output=True, check=True, timeout=600,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def predicted(digits):
    fixed = adaptive = 0
    for column in range(13):
        mask = sum(1 << row for row in range(12)
                   if row * 13 + column < len(digits)
                   and digits[row * 13 + column] is not None)
        fixed += fusions(mask, EVEN_EDGES)
        adaptive += path_fusions(mask)
    return fixed, adaptive


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
    assert sha(reference) == EXPECTED_REFERENCE_SHA256
    frozen = json.loads((HERE / "hex9-cover-result.json").read_text())
    assert frozen["status"] == "passed" and len(frozen["frozen"]["rows"]) == 214
    fixture = json.loads((HERE / "tau6-comb13-bench-fixture.json").read_text())
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
    old_rows = run(reference, "paired", scalars)
    new_rows = run(candidate, "path", scalars)
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    totals = {name: Counter() for name in ranges}
    independently_checked = 0
    for index, (scalar, old, new) in enumerate(zip(scalars, old_rows, new_rows)):
        name = next(name for name, (lo, hi) in ranges.items() if lo <= index < hi)
        assert old["representative"] == new["representative"], index
        assert old["tau_steps"] == new["tau_steps"], index
        assert affine_from_native(old["point"]) == affine_from_native(new["point"]), index
        for key in ("top_repaired", "coset_rank", "valid_representatives",
                    "attempted_representatives"):
            assert old["recoding_work"][key] == new["recoding_work"][key], (index, key)
        digits = digit_stream(tuple(map(int, new["representative"])), table, 162)
        fixed, adaptive = predicted(digits)
        assert old["recoding_work"]["pair_fusions"] == fixed, index
        assert new["recoding_work"]["pair_fusions"] == adaptive, index
        assert adaptive >= fixed, index
        assert old["nonzero_digits"] == new["nonzero_digits"] + adaptive - fixed, index
        if name == "fixture":
            row = fixture["cases"][index - ranges["fixture"][0]]
            expected = (int(row["expected_x_hex"], 16), int(row["expected_y_hex"], 16))
            assert affine_from_native(new["point"]) == expected, index
        if name == "edge" or name == "holdout" and index < ranges["holdout"][0] + 256:
            assert affine_from_native(new["point"]) == curve.point_multiply(scalar % N), index
            independently_checked += 1
        totals[name].update({"cases": 1, "fixed_fusions": fixed,
                             "path_fusions": adaptive,
                             "fixed_adds": old["nonzero_digits"],
                             "path_adds": new["nonzero_digits"],
                             "tau_steps": new["tau_steps"]})
    result = {"schema": 1, "status": "passed", "cases": len(scalars),
              "independent_points": independently_checked,
              "fixture_expected_points": len(fixture["cases"]),
              "ranges": ranges, "totals": {name: dict(row) for name, row in totals.items()},
              "reference_binary_sha256": sha(reference), "candidate_binary_sha256": sha(candidate),
              "candidate_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "verifier_sha256": sha(Path(__file__)),
              "fixture_sha256": sha(HERE / "tau6-comb13-bench-fixture.json")}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "independent_points": independently_checked, "totals": result["totals"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
