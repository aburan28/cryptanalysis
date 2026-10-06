#!/usr/bin/env python3
"""Freeze fresh generic-output controls for the tapered residue-orbit arm."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from make_inputs import COUNT, CURVES, fnv_words, read_fields
from screen_hot_orbits import uniform_scalar


SEED = 20271217


def materialize(bench, root):
    outdir = root / "tapered-inputs"
    outdir.mkdir(parents=True, exist_ok=True)
    cases = []
    for curve_index, (name, p, a, b, order) in enumerate(CURVES):
        for point_index in range(2):
            state = SEED ^ (curve_index << 32) ^ point_index
            values = []
            for _ in range(COUNT):
                state, scalar = uniform_scalar(state, order)
                values.append(scalar)
            path = outdir / f"{name}-point{point_index}.scalars.bin"
            contents = b"".join(value.to_bytes(8, "little") for value in values)
            if path.exists() and path.read_bytes() != contents:
                raise ValueError(f"frozen scalar file changed: {path}")
            path.write_bytes(contents)
            run = subprocess.run([str(bench), "reference", name,
                                  str(point_index), str(path)],
                                 text=True, capture_output=True, check=True)
            fields = read_fields(run.stdout)
            if (fields["verified"] != "1" or
                fields["input_digest"] != fnv_words(values) or
                fields["curve"] != name or
                fields["point_index"] != str(point_index)):
                raise AssertionError((path, fields, run.stderr))
            cases.append({"id": f"{name}-point{point_index}",
                          "curve": {"name": name, "p": p, "a": a,
                                    "b": b, "order": order},
                          "point_index": point_index,
                          "base_x": fields["base_x"],
                          "base_y": fields["base_y"],
                          "scalar_file": path.name,
                          "scalar_file_sha256": hashlib.sha256(
                              path.read_bytes()).hexdigest(),
                          "input_digest": fields["input_digest"],
                          "expected_output_digest": fields["output_digest"],
                          "scalars": COUNT})
    result = {"schema": 1, "status": "frozen_tapered_residue_fixture",
              "seed": SEED, "generator_seed": 1,
              "second_point_multiple": 37,
              "scalar_law": "SplitMix64 with rejection sampling",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cases": cases}
    output = root / "tapered-inputs.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text() != data:
        raise ValueError(f"frozen input manifest changed: {output}")
    output.write_text(data)
    print(json.dumps({"status": result["status"], "cases": len(cases),
                      "scalars_per_case": COUNT, "manifest": str(output)},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.bench.resolve(), Path(__file__).resolve().parent)
