#!/usr/bin/env python3
"""Freeze disjoint inputs for the single-pass first-word pair gate."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from make_inputs import COUNT, CURVES, fnv_words, read_fields
from make_periodic_int64_inputs import PRIOR_FIXTURES as EARLIER_FIXTURES
from make_tail_gated_inputs import uniform_scalar


SEED = 0x4A71D5E2C3908B6F
PRIOR_FIXTURES = EARLIER_FIXTURES + ("periodic-pair-int64-inputs.json",)


def prior_values(root, curve_name):
    values = set()
    manifests = []
    for name in PRIOR_FIXTURES:
        path = root / name
        contents = path.read_bytes()
        fixture = json.loads(contents)
        manifests.append({"name": name, "sha256": hashlib.sha256(contents).hexdigest()})
        for case in fixture["cases"]:
            if case["curve"]["name"] != curve_name:
                continue
            scalar_path = root / case["scalar_file"]
            raw = scalar_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != case["scalar_file_sha256"] or len(raw) % 8:
                raise ValueError(f"prior scalar file changed: {scalar_path}")
            values.update(struct.unpack(f"<{len(raw)//8}Q", raw))
    return values, manifests


def materialize(bench, root):
    outdir = root / "firstword-pair-inputs"
    outdir.mkdir(parents=True, exist_ok=True)
    cases = []
    manifest_hashes = None
    for curve_index, (name, p, a, b, order) in enumerate(CURVES):
        excluded, manifests = prior_values(root, name)
        if manifest_hashes is None:
            manifest_hashes = manifests
        elif manifests != manifest_hashes:
            raise AssertionError("prior manifest list changed across curves")
        accepted = set()
        for point_index in range(4):
            state = SEED ^ (curve_index << 32) ^ point_index
            values = []
            while len(values) < COUNT:
                state, value = uniform_scalar(state, order)
                if not 0 < value < order:
                    raise AssertionError("scalar rejection law left the subgroup range")
                if value in excluded or value in accepted:
                    continue
                accepted.add(value)
                values.append(value)
            path = outdir / f"{name}-point{point_index}.scalars.bin"
            contents = b"".join(value.to_bytes(8, "little") for value in values)
            if path.exists() and path.read_bytes() != contents:
                raise ValueError(f"frozen scalar file changed: {path}")
            path.write_bytes(contents)
            command = [str(bench), "reference", name, str(point_index), str(path)]
            process = subprocess.run(command, text=True, capture_output=True)
            if process.returncode:
                raise RuntimeError((command, process.returncode,
                                    process.stdout, process.stderr))
            fields = read_fields(process.stdout)
            if (fields["verified"] != "1" or fields["input_digest"] != fnv_words(values) or
                    fields["curve"] != name or fields["point_index"] != str(point_index)):
                raise AssertionError((path, fields, process.stderr))
            cases.append({"id": f"{name}-point{point_index}",
                          "curve": {"name": name, "p": p, "a": a, "b": b, "order": order},
                          "point_index": point_index,
                          "base_x": fields["base_x"], "base_y": fields["base_y"],
                          "scalar_file": str(path.relative_to(root)),
                          "scalar_file_sha256": hashlib.sha256(contents).hexdigest(),
                          "input_digest": fields["input_digest"],
                          "expected_output_digest": fields["output_digest"],
                          "reference_command": command,
                          "reference_stdout": process.stdout,
                          "reference_stderr": process.stderr,
                          "reference_status": process.returncode,
                          "excluded_scalar_count": len(excluded), "scalars": COUNT})
    result = {"schema": 1, "status": "frozen_firstword_pair_disjoint_fixture",
              "seed": SEED, "generator_seed": 1,
              "point_multiples": [1, 37, 101, 103],
              "scalar_law": "SplitMix64 with 64-bit rejection sampling; reject every prior scalar or earlier accepted scalar on the same curve",
              "excluded_prior_manifests": manifest_hashes,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "reference_binary_sha256": hashlib.sha256(bench.read_bytes()).hexdigest(),
              "reference_bench_source_sha256": hashlib.sha256((root / "bench.c").read_bytes()).hexdigest(),
              "cases": cases}
    path = root / "firstword-pair-inputs.json"
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
