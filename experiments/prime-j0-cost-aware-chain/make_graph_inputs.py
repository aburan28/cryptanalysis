#!/usr/bin/env python3
"""Freeze eight public-point cases for the orbit-graph preparation panel."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from check_panel import fields


MULTIPLES = (1, 37, 101, 103)


def make(bench, root):
    parent_path = root / "tapered-inputs.json"
    parent = json.loads(parent_path.read_text())
    old = {(case["curve"]["name"], case["point_index"]): case
           for case in parent["cases"]}
    cases = []
    for curve in ("glv-j0-32", "j0-56"):
        for point_index, multiple in enumerate(MULTIPLES):
            seed_case = old[(curve, point_index % 2)]
            relative = Path("tapered-inputs") / seed_case["scalar_file"]
            scalar_file = root / relative
            if hashlib.sha256(scalar_file.read_bytes()).hexdigest() != seed_case["scalar_file_sha256"]:
                raise ValueError(f"frozen scalar file changed: {scalar_file}")
            run = subprocess.run([str(bench), "reference", curve, str(point_index),
                                  str(scalar_file)], capture_output=True, text=True, check=True)
            got = fields(run.stdout)
            if (got["verified"] != "1" or got["curve"] != curve or
                    got["point_index"] != str(point_index) or
                    got["input_digest"] != seed_case["input_digest"]):
                raise AssertionError((curve, point_index, got))
            if point_index < 2 and got["output_digest"] != seed_case["expected_output_digest"]:
                raise AssertionError("previous generic digest changed")
            cases.append({"id": f"{curve}-point{point_index}",
                          "curve": seed_case["curve"],
                          "point_index": point_index, "multiple": multiple,
                          "scalar_file": str(relative),
                          "scalar_file_sha256": seed_case["scalar_file_sha256"],
                          "scalars": seed_case["scalars"],
                          "base_x": got["base_x"], "base_y": got["base_y"],
                          "input_digest": got["input_digest"],
                          "expected_output_digest": got["output_digest"]})
    fixture = {"schema": 1, "status": "frozen_orbit_graph_preparation_points",
               "point_multiples": MULTIPLES,
               "parent_manifest_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "cases": cases}
    output = root / "orbit-graph-inputs.json"
    data = json.dumps(fixture, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text() != data:
        raise ValueError(f"frozen graph inputs changed: {output}")
    output.write_text(data)
    print(json.dumps({"status": fixture["status"], "cases": len(cases),
                      "outputs_per_case": cases[0]["scalars"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    make(args.bench.resolve(), Path(__file__).resolve().parent)
