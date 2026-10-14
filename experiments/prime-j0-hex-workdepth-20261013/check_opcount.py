#!/usr/bin/env python3
"""Check actual Solinas kernel calls against the frozen count-tree model."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

from optimize import finish, load_module

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-tree-20261013"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def panel(name: str, fixture_path: Path, rows_path: Path, screen, old, orbit, codes, digits) -> dict:
    cases = json.loads(fixture_path.read_text())["cases"]
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert len(cases) == len(rows)
    totals = {key: 0 for key in ("modeled_join", "observed_join", "recovery", "total", "prejoin")}
    for case, row in zip(cases, rows):
        expected = ("identity" if case["expected_identity"] else
                    f"{case['expected_x_hex']}:{case['expected_y_hex']}")
        assert row["index"] == case["index"] and row["verified"] is True
        assert row["point"] == expected
        scalar = int(case["scalar_hex"], 16) % screen.lattice.ORDER
        gauges = screen.selected_gauges(scalar, old, orbit, codes, digits)
        plan = finish(tuple(gauges.count(g) for g in range(3)))
        assert row["additions"] == max(0, len(gauges) - 1)
        assert row["rotations"] == plan.rotations
        assert row["solinas_join"] == plan.work, case["index"]
        assert row["solinas_recovery"] == (0 if expected == "identity" else 4)
        assert row["solinas_total"] == row["solinas_join"] + row["solinas_recovery"]
        totals["modeled_join"] += plan.work
        totals["observed_join"] += row["solinas_join"]
        totals["recovery"] += row["solinas_recovery"]
        totals["total"] += row["solinas_total"]
        totals["prejoin"] += row["solinas_total"] - row["solinas_join"] - row["solinas_recovery"]
    return {"name": name, "cases": len(cases), "verified": len(cases),
            "fixture_sha256": digest(fixture_path), "rows_sha256": digest(rows_path), **totals}


def run() -> dict:
    screen = load_module("opcount_checker_screen", PRIOR / "screen.py")
    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("opcount_checker_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("opcount_checker_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    binary = Path("/Volumes/SSD990/llm/tmp/hex-opcount-build-20261013/"
                  "experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed")
    overlay = Path("/Volumes/SSD990/llm/tmp/hex-opcount-build-20261013/overlay.json")
    holdout = panel("fresh_holdout", HERE / "holdout.json", HERE / "opcount-holdout.jsonl",
                    screen, old, orbit, codes, digits)
    edges = panel("boundary_scalars", PRIOR / "edges.json", HERE / "opcount-edges.jsonl",
                  screen, old, orbit, codes, digits)
    return {"schema": 1, "status": "actual_solinas_calls_match_model",
            "holdout": holdout, "edges": edges,
            "instrument_binary_sha256": digest(binary),
            "instrument_overlay_sha256": digest(overlay),
            "instrument_source_sha256": digest(HERE / "instrument_overlay.py"),
            "checker_sha256": digest(Path(__file__)),
            "plan_sha256": digest(HERE / "plans.bin")}


if __name__ == "__main__":
    result = run()
    output = HERE / "opcount-receipt.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        assert not output.exists()
        output.write_text(data)
    else:
        assert output.read_text() == data
    print(json.dumps({"status": result["status"],
                      "holdout": result["holdout"], "edges": result["edges"]}, sort_keys=True))
