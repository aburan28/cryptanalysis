#!/usr/bin/env python3
"""Replay unit-orbit native points against the parent and independent arithmetic."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from screen_coset_representatives import N
from unit_orbit_windows_screen import BASELINE_SHA256, sha


HERE = Path(__file__).resolve().parent


def run(binary, mode, scalars):
    process = subprocess.run(
        [str(binary), mode],
        input="".join(scalar_text(scalar) + "\n" for scalar in scalars),
        capture_output=True, text=True, check=True, timeout=1800)
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
    baseline = args.baseline.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    assert sha(baseline) == BASELINE_SHA256
    screens = {panel: json.loads((HERE / f"unit-orbit-windows-{panel}.json").read_text())
               for panel in ("design", "holdout")}
    for panel, screen in screens.items():
        assert screen["panel"] == panel
        assert screen["protocol_sha256"] == sha(HERE / "UNIT_ORBIT_WINDOWS_PROTOCOL.md")
        assert screen["screen_sha256"] == sha(HERE / "unit_orbit_windows_screen.py")
    assert screens["holdout"]["status"] == "screen_passed"

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
    for panel, screen in screens.items():
        start = len(scalars)
        rng = random.Random(screen["seed"])
        generated = [rng.randrange(N) for _ in range(screen["count"])]
        digest = hashlib.sha256(b"".join(s.to_bytes(32, "big") for s in generated)).hexdigest()
        assert digest == screen["scalar_input_sha256"]
        scalars.extend(generated)
        ranges[panel] = (start, len(scalars))
    assert len(scalars) == 6492

    old_rows = run(baseline, "--scalar-w6-comb13-hex9-graphaware33-fixed", scalars)
    new_rows = run(candidate, "--scalar-unit-orbit-windows-fixed", scalars)
    totals = {panel: {"reference_proxy": 0, "candidate_proxy": 0}
              for panel in screens}
    point_digest = hashlib.sha256()
    independent_points = 0
    retained_bytes = new_rows[0]["retained_bytes"]
    assert retained_bytes < 90 * (1 << 20)
    for index, (scalar, old, new) in enumerate(zip(scalars, old_rows, new_rows)):
        point = affine_from_native(new["point"])
        assert point == affine_from_native(old["point"]), index
        if index < 5 or ranges["holdout"][0] <= index < ranges["holdout"][0] + 256:
            assert point == curve.point_multiply(scalar % N), index
            independent_points += 1
        if ranges["fixture"][0] <= index < ranges["fixture"][1]:
            expected = fixture["cases"][index - ranges["fixture"][0]]
            assert point == (int(expected["expected_x_hex"], 16),
                             int(expected["expected_y_hex"], 16)), index
        assert new["retained_bytes"] == retained_bytes, index
        assert new["tau_steps"] == 0 and 0 <= new["nonzero_digits"] <= 13, index
        for panel, (lo, hi) in ranges.items():
            if panel not in screens or not lo <= index < hi:
                continue
            expected = screens[panel]["rows"][index - lo]
            assert list(map(int, new["representative"])) == list(
                map(int, expected["representative"])), index
            assert new["nonzero_digits"] == max(expected["nonidentity_windows"] - 1, 0), index
            reference_proxy = 5 * old["tau_steps"] + 11 * old["nonzero_digits"]
            candidate_proxy = 11 * new["nonzero_digits"]
            assert (reference_proxy, candidate_proxy) == (
                expected["reference_proxy"], expected["candidate_proxy"]), index
            totals[panel]["reference_proxy"] += reference_proxy
            totals[panel]["candidate_proxy"] += candidate_proxy
        point_digest.update(("I" if point is None else
                             hex(point[0]) + ":" + hex(point[1])).encode() + b"\n")
    for panel, values in totals.items():
        assert values["reference_proxy"] == screens[panel]["totals"]["reference_proxy"]
        assert values["candidate_proxy"] == screens[panel]["totals"]["candidate_proxy"]
    result = {"schema": 1, "status": "passed", "cases": len(scalars),
              "independent_points": independent_points,
              "fixture_expected_points": len(fixture["cases"]),
              "ranges": ranges, "totals": totals, "retained_bytes": retained_bytes,
              "point_digest_sha256": point_digest.hexdigest(),
              "baseline_binary_sha256": sha(baseline),
              "candidate_binary_sha256": sha(candidate),
              "candidate_source_sha256": {name: sha(HERE / name) for name in (
                  "src/bin/eisenstein_fixed.rs",
                  "src/bin/eisenstein_fixed/unit_orbit_windows.rs")},
              "verifier_sha256": sha(Path(__file__)),
              "fixture_sha256": sha(fixture_path),
              "screen_receipt_sha256": {panel: sha(HERE / f"unit-orbit-windows-{panel}.json")
                                        for panel in screens}}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "independent_points": independent_points,
                      "fixture_expected_points": len(fixture["cases"]),
                      "retained_bytes": retained_bytes, "totals": totals,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
