#!/usr/bin/env python3
"""Check fresh native Solinas calls with the absolute-gauge plan model."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

from check import HERE, absolute_tree, check, digest

EXP = HERE.parent
sys.path.insert(0, str(EXP / "prime-j0-hex-workdepth-20261013"))
from dag_depth import load_module  # noqa: E402


def run() -> dict:
    fixture = HERE / "holdout.json"
    rows_path = HERE / "opcount-holdout.jsonl"
    point_receipt = check(fixture, rows_path)
    cases = json.loads(fixture.read_text())["cases"]
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    screen = load_module("orbit_opcount_screen", EXP / "prime-j0-hex-tree-20261013/screen.py")
    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("orbit_opcount_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("orbit_opcount_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    plans = (HERE / "plans.bin").read_bytes()
    join = recovery = total = 0
    for case, row in zip(cases, rows):
        gauges = screen.selected_gauges(int(case["scalar_hex"], 16),
                                        old, orbit, codes, digits)
        modeled = absolute_tree(tuple(gauges.count(g) for g in range(3)), plans).work
        assert row["solinas_join"] == modeled, case["index"]
        recovered = 0 if case["expected_identity"] else 4
        assert row["solinas_recovery"] == recovered
        assert row["solinas_total"] == modeled + recovered
        join += row["solinas_join"]
        recovery += row["solinas_recovery"]
        total += row["solinas_total"]
    assert join == point_receipt["new_work"]
    build = Path("/Volumes/SSD990/llm/tmp/hex-orbit-materialized-opcount-20261013-r1")
    binary = build / "experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed"
    return {"schema": 1, "status": "fresh_native_solinas_calls_match_absolute_gauge_plan",
            "cases": len(cases), "join_calls": join, "recovery_calls": recovery,
            "total_calls": total, "point_check": point_receipt,
            "fixture_sha256": digest(fixture), "rows_sha256": digest(rows_path),
            "plan_sha256": digest(HERE / "plans.bin"),
            "instrument_binary_sha256": digest(binary),
            "instrument_overlay_sha256": digest(build / "overlay.json"),
            "checker_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    result = run()
    output = HERE / "opcount-receipt.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        assert not output.exists()
        output.write_text(data)
    else:
        assert output.read_text() == data
    print(json.dumps({k: result[k] for k in
                      ("status", "cases", "join_calls", "recovery_calls", "total_calls")},
                     sort_keys=True))
