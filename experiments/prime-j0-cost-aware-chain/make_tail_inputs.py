#!/usr/bin/env python3
"""Freeze fresh public scalars and generic point digests for the tail oracle."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from make_inputs import COUNT, CURVES, fnv_words, read_fields, splitmix64


SEED = 20280105


def uniform_scalar(state, order):
    limit = (1 << 64) - ((1 << 64) % order)
    while True:
        state, value = splitmix64(state)
        if value < limit:
            return state, value % order


def materialize(bench, root):
    outdir = root / "tail-inputs"
    outdir.mkdir(parents=True, exist_ok=True)
    cases = []
    for curve_index, (name, p, a, b, order) in enumerate(CURVES):
        for point_index in range(4):
            state = SEED ^ (curve_index << 32) ^ point_index
            values = []
            for _ in range(COUNT):
                state, value = uniform_scalar(state, order)
                values.append(value)
            path = outdir / f"{name}-point{point_index}.scalars.bin"
            contents = b"".join(value.to_bytes(8, "little") for value in values)
            if path.exists() and path.read_bytes() != contents:
                raise ValueError(f"frozen scalar file changed: {path}")
            path.write_bytes(contents)
            proc = subprocess.run([str(bench), "reference", name,
                                   str(point_index), str(path)],
                                  text=True, capture_output=True, check=True)
            fields = read_fields(proc.stdout)
            if (fields["verified"] != "1" or fields["input_digest"] != fnv_words(values) or
                    fields["curve"] != name or fields["point_index"] != str(point_index)):
                raise AssertionError((path, fields, proc.stderr))
            cases.append({"id": f"{name}-point{point_index}",
                          "curve": {"name": name, "p": p, "a": a, "b": b, "order": order},
                          "point_index": point_index,
                          "base_x": fields["base_x"], "base_y": fields["base_y"],
                          "scalar_file": str(path.relative_to(root)),
                          "scalar_file_sha256": hashlib.sha256(contents).hexdigest(),
                          "input_digest": fields["input_digest"],
                          "expected_output_digest": fields["output_digest"],
                          "scalars": COUNT})
    result = {"schema": 1, "status": "frozen_tail_oracle_fixture",
              "seed": SEED, "generator_seed": 1,
              "point_multiples": [1, 37, 101, 103],
              "scalar_law": "SplitMix64 with 64-bit rejection sampling",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cases": cases}
    path = root / "tail-inputs.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() != data:
        raise ValueError(f"frozen input manifest changed: {path}")
    path.write_text(data)
    print(json.dumps({"status": result["status"], "cases": len(cases),
                      "scalars_per_case": COUNT, "manifest": str(path)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.bench.resolve(), Path(__file__).resolve().parent)
