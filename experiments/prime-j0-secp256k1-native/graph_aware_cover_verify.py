#!/usr/bin/env python3
"""Replay the graph-aware native selector against frozen panels and points."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
from graph_aware_cover_screen import COUNT, SEEDS, representatives, sha
import lazy_tau_screen as curve
from screen_coset_representatives import N
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent


def run(binary, mode, scalars):
    process = subprocess.run(
        [str(binary), f"--scalar-w6-comb13-hex9-{mode}-fixed"],
        input="".join(scalar_text(scalar) + "\n" for scalar in scalars),
        text=True, capture_output=True, check=True, timeout=1200)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    base_binary = args.baseline.resolve(strict=True)
    new_binary = args.candidate.resolve(strict=True)
    for panel in SEEDS:
        receipt = json.loads((HERE / f"graph-aware-cover-{panel}.json").read_text())
        assert receipt["status"] == "screen_passed" and receipt["count"] == COUNT
        assert receipt["protocol_sha256"] == sha(HERE / "GRAPH_AWARE_COVER_PROTOCOL.md")
        assert receipt["screen_sha256"] == sha(HERE / "graph_aware_cover_screen.py")
    assert sha(base_binary) == json.loads(
        (HERE / "graph-aware-cover-holdout.json").read_text())["baseline_binary_sha256"]

    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    frozen = json.loads((HERE / "hex9-cover-result.json").read_text())
    assert frozen["status"] == "passed" and len(frozen["frozen"]["rows"]) == 214
    scalars = [0, 1, N - 1, N, N + 1]
    ranges = {"boundary": (0, len(scalars))}
    start = len(scalars)
    scalars.extend(int(row["scalar_hex"], 16) for row in frozen["frozen"]["rows"])
    ranges["frozen"] = (start, len(scalars))
    start = len(scalars)
    scalars.extend(int(row["scalar_hex"], 16) for row in fixture["cases"])
    ranges["fixture"] = (start, len(scalars))
    for panel, seed in SEEDS.items():
        start = len(scalars)
        rng = random.Random(seed)
        scalars.extend(rng.randrange(N) for _ in range(COUNT))
        ranges[panel] = (start, len(scalars))
    assert len(scalars) == 4444

    old_rows = run(base_binary, "graph33", scalars)
    new_rows = run(new_binary, "graphaware33", scalars)
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected = set(SPARSE_TOP_ORBITS)
    totals = {name: Counter() for name in ranges}
    fingerprints = {name: hashlib.sha256() for name in ranges}
    independent_points = 0
    for index, (scalar, old, new) in enumerate(zip(scalars, old_rows, new_rows)):
        panel = next(name for name, (lo, hi) in ranges.items() if lo <= index < hi)
        baseline, candidate, valid = representatives(scalar % N, table, selected)
        for row, expected in ((old, baseline), (new, candidate)):
            assert list(map(int, row["representative"])) == expected["representative"], index
            assert row["tau_steps"] == expected["tau_steps"], index
            assert row["nonzero_digits"] == expected["mixed_additions"] - expected["fusions"], index
            work = row["recoding_work"]
            assert work["top_repaired"] == expected["top_repaired"], index
            assert work["pair_fusions"] == expected["fusions"], index
            assert work["coset_rank"] == expected["rank"], index
            assert work["valid_representatives"] == valid, index
            assert work["attempted_representatives"] == 9, index
        point = affine_from_native(new["point"])
        assert point == affine_from_native(old["point"]), index
        if panel == "fixture":
            fixture_row = fixture["cases"][index - ranges["fixture"][0]]
            expected_point = (int(fixture_row["expected_x_hex"], 16),
                              int(fixture_row["expected_y_hex"], 16))
            assert point == expected_point, index
        if panel == "boundary" or (panel == "holdout" and
                                   index < ranges["holdout"][0] + 256):
            assert point == curve.point_multiply(scalar % N), index
            independent_points += 1
        totals[panel].update({"cases": 1,
                              "baseline_proxy": baseline["matched_proxy"],
                              "candidate_proxy": candidate["matched_proxy"],
                              "baseline_fusions": baseline["fusions"],
                              "candidate_fusions": candidate["fusions"],
                              "baseline_mixed_additions": old["nonzero_digits"],
                              "candidate_mixed_additions": new["nonzero_digits"],
                              "baseline_tau_steps": old["tau_steps"],
                              "candidate_tau_steps": new["tau_steps"]})
        fingerprints[panel].update(
            f"{baseline['rank']},{candidate['rank']},{baseline['matched_proxy']},{candidate['matched_proxy']}\n".encode())
    for panel in SEEDS:
        screen = json.loads((HERE / f"graph-aware-cover-{panel}.json").read_text())
        for key, value in totals[panel].items():
            assert screen["totals"][key] == value, (panel, key)
    result = {"schema": 1, "status": "passed", "cases": len(scalars),
              "independent_points": independent_points,
              "fixture_expected_points": len(fixture["cases"]),
              "ranges": ranges, "totals": {name: dict(value) for name, value in totals.items()},
              "per_panel_sha256": {name: digest.hexdigest() for name, digest in fingerprints.items()},
              "baseline_binary_sha256": sha(base_binary), "candidate_binary_sha256": sha(new_binary),
              "candidate_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "verifier_sha256": sha(Path(__file__)), "fixture_sha256": sha(fixture_path),
              "screen_sha256": {name: sha(HERE / f"graph-aware-cover-{name}.json") for name in SEEDS}}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "independent_points": independent_points,
                      "holdout_totals": dict(totals["holdout"]),
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
