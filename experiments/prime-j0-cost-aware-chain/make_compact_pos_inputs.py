#!/usr/bin/env python3
"""Freeze scalar inputs disjoint from every earlier prepared-point fixture."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from make_inputs import COUNT, CURVES, fnv_words, read_fields
from make_mixed_full_inputs import PRIOR_FIXTURES as EARLIER_FIXTURES
from make_tail_gated_inputs import uniform_scalar


ROOT = Path(__file__).resolve().parent
SEED = 0x9CB865CD8130F257
PRIOR_FIXTURES = EARLIER_FIXTURES + ("mixed-full-inputs.json",)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excluded_values(curve):
    values = set()
    manifests = []
    for name in PRIOR_FIXTURES:
        manifest_path = ROOT / name
        manifest = json.loads(manifest_path.read_text())
        manifests.append({"name": name, "sha256": sha256(manifest_path)})
        for case in manifest["cases"]:
            if case["curve"]["name"] != curve:
                continue
            path = ROOT / case["scalar_file"]
            raw = path.read_bytes()
            if sha256(path) != case["scalar_file_sha256"] or len(raw) % 8:
                raise ValueError(f"changed prior scalar file: {path}")
            values.update(struct.unpack(f"<{len(raw)//8}Q", raw))
    return values, manifests


def materialize(bench):
    output_dir = ROOT / "compact-pos-inputs"
    output_dir.mkdir(exist_ok=True)
    cases = []
    pinned = None
    for curve_index, (name, p, a, b, order) in enumerate(CURVES):
        excluded, manifests = excluded_values(name)
        if pinned is None:
            pinned = manifests
        elif pinned != manifests:
            raise AssertionError("prior manifests differ by curve")
        accepted = set()
        for point_index in range(4):
            state = SEED ^ (curve_index << 32) ^ point_index
            values = []
            while len(values) < COUNT:
                state, value = uniform_scalar(state, order)
                if not 0 < value < order:
                    raise AssertionError("rejection sampler returned invalid scalar")
                if value in excluded or value in accepted:
                    continue
                accepted.add(value)
                values.append(value)
            path = output_dir / f"{name}-point{point_index}.scalars.bin"
            raw = b"".join(value.to_bytes(8, "little") for value in values)
            if path.exists() and path.read_bytes() != raw:
                raise ValueError(f"changed frozen input: {path}")
            path.write_bytes(raw)
            command = [str(bench), "reference", name, str(point_index), str(path)]
            process = subprocess.run(command, text=True, capture_output=True, timeout=120)
            if process.returncode:
                raise RuntimeError((command, process.returncode, process.stderr))
            fields = read_fields(process.stdout)
            if (fields["verified"] != "1" or fields["input_digest"] != fnv_words(values)
                    or fields["curve"] != name or fields["point_index"] != str(point_index)):
                raise AssertionError((command, fields))
            cases.append({"id": f"{name}-point{point_index}",
                          "curve": {"name": name, "p": p, "a": a, "b": b, "order": order},
                          "point_index": point_index,
                          "base_x": fields["base_x"], "base_y": fields["base_y"],
                          "scalar_file": str(path.relative_to(ROOT)),
                          "scalar_file_sha256": hashlib.sha256(raw).hexdigest(),
                          "input_digest": fields["input_digest"],
                          "expected_output_digest": fields["output_digest"],
                          "reference_stdout": process.stdout,
                          "reference_stderr": process.stderr,
                          "reference_status": process.returncode,
                          "excluded_scalar_count": len(excluded), "scalars": COUNT})
    result = {"schema": 1, "status": "frozen_compact_pos_disjoint_fixture",
              "seed": SEED, "point_multiples": [1, 37, 101, 103],
              "scalar_law": "SplitMix64 64-bit rejection; exclude all prior and same-curve accepted scalars",
              "excluded_prior_manifests": pinned,
              "source_sha256": sha256(Path(__file__)),
              "reference_binary_sha256": sha256(bench),
              "reference_bench_source_sha256": sha256(ROOT / "bench.c"),
              "cases": cases}
    manifest_path = ROOT / "compact-pos-inputs.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text() != data:
        raise ValueError(f"changed frozen manifest: {manifest_path}")
    manifest_path.write_text(data)
    print(json.dumps({"cases": len(cases), "scalars_per_case": COUNT,
                      "manifest": str(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.bench.resolve())
