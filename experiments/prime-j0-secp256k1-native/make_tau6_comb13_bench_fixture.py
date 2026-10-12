#!/usr/bin/env python3
"""Freeze independent points for the sparse tau13/GLV10 paired holdout."""

import argparse
import hashlib
import json
from pathlib import Path

import lazy_tau_screen as curve


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "tau6-comb13-sparse-result.json"
ORIGINAL = HERE / "tau6-comb-result.json"
DEFAULT_OUTPUT = HERE / "tau6-comb13-bench-fixture.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("fixture exists; refusing overwrite")

    source = json.loads(SOURCE.read_text())
    original = json.loads(ORIGINAL.read_text())
    assert source["schema"] == original["schema"] == 1
    assert source["status"] == original["status"] == "passed"
    assert source["curve"] == original["curve"] == "secp256k1"
    frozen = source["frozen"]["rows"]
    assert len(frozen) == len(original["cases"]) == 214
    assert all((a["index"], a["panel"], a["scalar_hex"]) ==
               (b["index"], b["panel"], b["scalar_hex"])
               for a, b in zip(frozen, original["cases"]))
    holdout = [row for row in frozen if row["panel"] == "holdout_random"]
    assert len(holdout) == 128 and all(not row["fallback"] for row in holdout)
    miss = source["deliberate_fallback"]
    assert miss["verified"] and miss["top_orbit"] not in source["top_row_orbits"]
    inputs = [("holdout_random", row["index"], row["scalar_hex"])
              for row in holdout]
    inputs.append(("deliberate_fallback", None, format(int(miss["scalar_hex"], 16), "x")))
    assert len({scalar for _, _, scalar in inputs}) == len(inputs)

    cases = []
    for index, (panel, source_index, scalar_hex) in enumerate(inputs):
        scalar = int(scalar_hex, 16)
        point = curve.point_multiply(scalar % curve.ORDER)
        assert point is not None and (point[1] ** 2 - point[0] ** 3 - 7) % curve.field.P == 0
        cases.append({
            "index": index,
            "panel": panel,
            "source_index": source_index,
            "base_x_hex": f"{curve.GENERATOR[0]:064x}",
            "base_y_hex": f"{curve.GENERATOR[1]:064x}",
            "scalar_hex": scalar_hex,
            "expected_identity": False,
            "expected_x_hex": f"{point[0]:064x}",
            "expected_y_hex": f"{point[1]:064x}",
        })
    fixture = {
        "schema": 1,
        "kind": "paired-sparse-tau13-glv10-fixed-generator",
        "curve": "secp256k1",
        "input_law": "128 frozen holdout_random scalars in source order, then one omitted-top-orbit fallback",
        "holdout_cases": 128,
        "deliberate_fallback_cases": 1,
        "source_sha256": sha(SOURCE),
        "original_source_sha256": sha(ORIGINAL),
        "reference_sha256": sha(HERE / "lazy_tau_screen.py"),
        "generator_sha256": sha(Path(__file__)),
        "cases": cases,
    }
    args.output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "fixture_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
