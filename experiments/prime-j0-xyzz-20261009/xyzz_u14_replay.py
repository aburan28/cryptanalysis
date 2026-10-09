#!/usr/bin/env python3
"""Replay U14 unit-orbit addends through the checked XYZZ accumulator."""

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "prime-j0-secp256k1-native"
sys.path.insert(0, str(NATIVE))
import lazy_tau_screen as curve  # noqa: E402
from radix943_screen import LAMBDA_TAU, ORDER, nearest_representative  # noqa: E402
from unit_orbit_windows_screen import OrbitAtlas, WIDTHS  # noqa: E402
from xyzz_formula_check import affine, check_step  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    fixture_path = NATIVE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    assert sum(WIDTHS) == 129
    atlases = {width: OrbitAtlas(width) for width in set(WIDTHS)}
    scalar_digest = hashlib.sha256()
    point_digest = hashlib.sha256()
    statuses = {}
    total_m = total_s = 0
    per_case = []
    for index, case in enumerate(fixture["cases"]):
        assert case["index"] == index
        scalar = int(case["scalar_hex"], 16)
        scalar_digest.update((scalar % ORDER).to_bytes(32, "big"))
        start = nearest_representative(scalar % ORDER)
        pair = start
        factor = 1
        point = expected_progressive = None
        case_statuses = {}
        for width in WIDTHS:
            atlas = atlases[width]
            digit, _, _ = atlas.digit(pair)
            assert (pair[0] - digit[0]) % atlas.base == 0
            assert (pair[1] - digit[1]) % atlas.base == 0
            pair = ((pair[0] - digit[0]) // atlas.base,
                    (pair[1] - digit[1]) // atlas.base)
            if digit != (0, 0):
                coefficient = (digit[0] + digit[1] * LAMBDA_TAU) * factor % ORDER
                addend = curve.point_multiply(coefficient)
                assert addend is not None
                point, expected_progressive, status, ops = check_step(
                    point, expected_progressive, addend)
                case_statuses[status] = case_statuses.get(status, 0) + 1
                statuses[status] = statuses.get(status, 0) + 1
                total_m += ops.m
                total_s += ops.s
            factor *= atlas.base
        assert pair == (0, 0) and factor == 1 << 129
        assert (start[0] + start[1] * LAMBDA_TAU - scalar) % ORDER == 0
        actual = affine(point)
        independent = curve.point_multiply(scalar % ORDER)
        expected = None if case["expected_identity"] else (
            int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16))
        assert actual == independent == expected, index
        point_digest.update(("identity" if actual is None else
                             f"{actual[0]:064x}:{actual[1]:064x}").encode() + b"\n")
        per_case.append({"index": index, "status": "passed", "additions":
                         case_statuses.get("generic", 0), "first":
                         case_statuses.get("first", 0), "exceptional":
                         case_statuses.get("equal", 0) + case_statuses.get("inverse", 0)})
    assert all(row["status"] == "passed" for row in per_case)
    assert total_m == (8 * statuses.get("generic", 0) +
                       6 * statuses.get("equal", 0))
    assert total_s == (2 * statuses.get("generic", 0) +
                       3 * statuses.get("equal", 0))
    result = {
        "schema": 1,
        "status": "passed",
        "cases": len(per_case),
        "scalar_input_sha256": scalar_digest.hexdigest(),
        "point_digest_sha256": point_digest.hexdigest(),
        "step_statuses": statuses,
        "symbolic_generic_multiplications": total_m,
        "symbolic_generic_squares": total_s,
        "jacobian_product_count_generic_additions": 11 * statuses.get("generic", 0),
        "xyzz_product_count_generic_additions": 10 * statuses.get("generic", 0),
        "per_case": per_case,
        "wall_time_ms": None,
        "source_sha256": {
            "xyzz_formula_check.py": sha(HERE / "xyzz_formula_check.py"),
            "unit_orbit_windows_screen.py": sha(NATIVE / "unit_orbit_windows_screen.py"),
            "radix943_screen.py": sha(NATIVE / "radix943_screen.py"),
            "lazy_tau_screen.py": sha(NATIVE / "lazy_tau_screen.py"),
        },
        "fixture_sha256": sha(fixture_path),
        "protocol_sha256": sha(HERE / "U14_REPLAY_PROTOCOL.md"),
        "checker_sha256": sha(Path(__file__)),
    }
    output = HERE / "xyzz-u14-replay-result.json"
    if output.exists():
        raise SystemExit("result exists; refusing overwrite")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": result["cases"],
                      "step_statuses": statuses}, sort_keys=True))


if __name__ == "__main__":
    main()
