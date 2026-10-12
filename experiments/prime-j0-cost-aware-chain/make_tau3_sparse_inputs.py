#!/usr/bin/env python3
"""Freeze prospective sparse-tau3 scalar inputs disjoint from all earlier fixtures."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from make_tau3_atlas_inputs import PRIOR_FIXTURES as EARLIER_FIXTURES
from make_inputs import COUNT, CURVES, fnv_words, read_fields
from make_tail_gated_inputs import uniform_scalar


ROOT = Path(__file__).resolve().parent
SEED = 0x5A31E0C4D9B8276F
PRIOR_FIXTURES = EARLIER_FIXTURES + (
    "tau3-fused-inputs.json", "tau3-atlas-inputs.json")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def exclusions(curve_name):
    values = set()
    manifests = []
    for name in PRIOR_FIXTURES:
        path = ROOT / name
        manifests.append({"name": name, "sha256": sha256(path.read_bytes())})
        manifest = json.loads(path.read_text())
        for case in manifest["cases"]:
            if case["curve"]["name"] != curve_name:
                continue
            scalar_path = ROOT / case["scalar_file"]
            raw = scalar_path.read_bytes()
            if sha256(raw) != case["scalar_file_sha256"] or len(raw) % 8:
                raise ValueError(f"changed prior scalar file: {scalar_path}")
            values.update(struct.unpack(f"<{len(raw)//8}Q", raw))
    return values, manifests


def materialize(bench):
    outdir = ROOT / "tau3-sparse-inputs"
    outdir.mkdir(exist_ok=True)
    cases = []
    pinned = None
    for curve_index, (name, p, a, b, order) in enumerate(CURVES):
        excluded, manifests = exclusions(name)
        if pinned is None:
            pinned = manifests
        elif pinned != manifests:
            raise AssertionError("prior manifest list differs by curve")
        accepted = set()
        for point_index in range(4):
            state = SEED ^ (curve_index << 32) ^ point_index
            values = []
            while len(values) < COUNT:
                state, scalar = uniform_scalar(state, order)
                if not 0 < scalar < order:
                    raise AssertionError("rejection sampler left subgroup range")
                if scalar in excluded or scalar in accepted:
                    continue
                accepted.add(scalar)
                values.append(scalar)
            path = outdir / f"{name}-point{point_index}.scalars.bin"
            raw = b"".join(scalar.to_bytes(8, "little") for scalar in values)
            if path.exists() and path.read_bytes() != raw:
                raise ValueError(f"changed frozen input: {path}")
            path.write_bytes(raw)
            command = [str(bench), "reference", name, str(point_index), str(path)]
            process = subprocess.run(command, text=True, capture_output=True,
                                     timeout=120, check=False)
            if process.returncode:
                raise RuntimeError((command, process.returncode, process.stderr))
            fields = read_fields(process.stdout)
            if (fields["verified"] != "1" or fields["input_digest"] != fnv_words(values)
                    or fields["curve"] != name or fields["point_index"] != str(point_index)):
                raise AssertionError((name, point_index, fields))
            cases.append({"id": f"{name}-point{point_index}",
                          "curve": {"name": name, "p": p, "a": a, "b": b, "order": order},
                          "point_index": point_index,
                          "base_x": fields["base_x"], "base_y": fields["base_y"],
                          "scalar_file": str(path.relative_to(ROOT)),
                          "scalar_file_sha256": sha256(raw),
                          "input_digest": fields["input_digest"],
                          "expected_output_digest": fields["output_digest"],
                          "reference_stdout": process.stdout,
                          "reference_stderr": process.stderr,
                          "reference_status": process.returncode,
                          "excluded_scalar_count": len(excluded), "scalars": COUNT})
    manifest = {"schema": 1, "status": "frozen_tau3_sparse_disjoint_fixture",
                "seed": SEED, "point_multiples": [1, 37, 101, 103],
                "scalar_law": "SplitMix64 64-bit rejection; exclude all prior and same-curve accepted scalars",
                "excluded_prior_manifests": pinned,
                "source_sha256": sha256(Path(__file__).read_bytes()),
                "reference_binary_sha256": sha256(bench.read_bytes()),
                "reference_bench_source_sha256": sha256((ROOT / "bench.c").read_bytes()),
                "cases": cases}
    path = ROOT / "tau3-sparse-inputs.json"
    content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() != content:
        raise ValueError(f"changed frozen manifest: {path}")
    path.write_text(content)
    print(json.dumps({"status": manifest["status"], "cases": len(cases),
                      "scalars_per_case": COUNT, "manifest": str(path)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.bench.resolve())
