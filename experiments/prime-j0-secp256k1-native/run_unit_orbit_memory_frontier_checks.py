#!/usr/bin/env python3
"""Verify three native unit-orbit schedules on one frozen scalar corpus."""

import argparse
import hashlib
import json
from pathlib import Path
import random

from check_eisenstein_scalar_fixed import affine_from_native
import lazy_tau_screen as curve
from run_unit_orbit_native_checks import HERE, run
from screen_coset_representatives import N
from unit_orbit_windows_screen import BASELINE_SHA256, sha


MODES = {
    14: ("--scalar-unit-orbit-windows-fixed", "unit-orbit-windows-fixed"),
    15: ("--scalar-unit-orbit-windows15-fixed", "unit-orbit-windows15-fixed"),
    16: ("--scalar-unit-orbit-windows16-fixed", "unit-orbit-windows16-fixed"),
}
SEED = 20261009515


def corpus():
    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    frozen = json.loads((HERE / "hex9-cover-result.json").read_text())
    screens = [json.loads((HERE / f"unit-orbit-windows-{panel}.json").read_text())
               for panel in ("design", "holdout")]
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    assert frozen["status"] == "passed" and len(frozen["frozen"]["rows"]) == 214
    scalars = [0, 1, N - 1, N, N + 1]
    ranges = {"boundary": (0, len(scalars))}
    start = len(scalars)
    scalars.extend(int(row["scalar_hex"], 16) for row in frozen["frozen"]["rows"])
    ranges["frozen"] = (start, len(scalars))
    start = len(scalars)
    scalars.extend(int(row["scalar_hex"], 16) for row in fixture["cases"])
    ranges["fixture"] = (start, len(scalars))
    for screen in screens:
        panel = screen["panel"]
        start = len(scalars)
        rng = random.Random(screen["seed"])
        generated = [rng.randrange(N) for _ in range(screen["count"])]
        digest = hashlib.sha256(b"".join(s.to_bytes(32, "big") for s in generated)).hexdigest()
        assert digest == screen["scalar_input_sha256"]
        scalars.extend(generated)
        ranges[panel] = (start, len(scalars))
    assert len(scalars) == 6492
    rng = random.Random(SEED)
    fresh = [rng.randrange(N) for _ in range(256)]
    fresh_sha = hashlib.sha256(b"".join(s.to_bytes(32, "big") for s in fresh)).hexdigest()
    ranges["fresh"] = (len(scalars), len(scalars) + len(fresh))
    scalars.extend(fresh)
    return scalars, ranges, fixture, fixture_path, fresh_sha


def point_digest(points):
    digest = hashlib.sha256()
    for point in points:
        digest.update(("I" if point is None else
                       hex(point[0]) + ":" + hex(point[1])).encode() + b"\n")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    baseline = args.baseline.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    assert sha(baseline) == BASELINE_SHA256
    scalars, ranges, fixture, fixture_path, fresh_sha = corpus()
    old = run(baseline, "--scalar-w6-comb13-hex9-graphaware33-fixed", scalars)
    native = {fmt: run(candidate, mode, scalars) for fmt, (mode, _) in MODES.items()}
    retained = {fmt: native[fmt][0]["retained_bytes"] for fmt in MODES}
    assert retained[16] < retained[15] < retained[14] < 90 * (1 << 20)
    assert retained[15] < 36_000_000 and retained[16] < 17_000_000
    additions = {fmt: 0 for fmt in MODES}
    histograms = {fmt: {} for fmt in MODES}
    points = []
    for index, scalar in enumerate(scalars):
        expected = affine_from_native(old[index]["point"])
        points.append(expected)
        first_rep = None
        for fmt, (_, radix) in MODES.items():
            row = native[fmt][index]
            assert affine_from_native(row["point"]) == expected, (fmt, index)
            assert row["radix"] == radix, (fmt, index)
            assert row["tau_steps"] == 0, (fmt, index)
            assert row["retained_bytes"] == retained[fmt], (fmt, index)
            assert 0 <= row["nonzero_digits"] <= fmt - 1, (fmt, index)
            rep = tuple(map(int, row["representative"]))
            if first_rep is None:
                first_rep = rep
            assert rep == first_rep, (fmt, index)
            additions[fmt] += row["nonzero_digits"]
            histogram = histograms[fmt]
            count = row["nonzero_digits"]
            histogram[count] = histogram.get(count, 0) + 1
        if ranges["fixture"][0] <= index < ranges["fixture"][1]:
            case = fixture["cases"][index - ranges["fixture"][0]]
            assert expected == (int(case["expected_x_hex"], 16),
                                int(case["expected_y_hex"], 16)), index
        if ranges["fresh"][0] <= index < ranges["fresh"][1]:
            assert expected == curve.point_multiply(scalar % N), index
    result = {
        "schema": 1,
        "status": "passed",
        "cases": len(scalars),
        "ranges": ranges,
        "fresh_seed": SEED,
        "fresh_scalar_sha256": fresh_sha,
        "fresh_independent_points": 256,
        "fixture_expected_points": len(fixture["cases"]),
        "point_digest_sha256": point_digest(points),
        "retained_bytes": retained,
        "mixed_additions_total": additions,
        "mixed_additions_histogram": histograms,
        "baseline_binary_sha256": sha(baseline),
        "candidate_binary_sha256": sha(candidate),
        "candidate_source_sha256": {name: sha(HERE / name) for name in (
            "src/bin/eisenstein_fixed.rs",
            "src/bin/eisenstein_fixed/unit_orbit_windows.rs")},
        "protocol_sha256": sha(HERE / "UNIT_ORBIT_MEMORY_FRONTIER_PROTOCOL.md"),
        "verifier_sha256": sha(Path(__file__)),
        "fixture_sha256": sha(fixture_path),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "cases", "retained_bytes",
                                                 "mixed_additions_total", "fresh_scalar_sha256")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
