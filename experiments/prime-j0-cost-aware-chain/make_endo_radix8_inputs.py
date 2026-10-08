#!/usr/bin/env python3
"""Freeze disjoint public scalars after the signed-radix design is fixed."""

import hashlib
import json
from pathlib import Path
import random
import struct
import sys


SEED = 202610062132
COUNT = 4096
PRIOR = (
    "compact-pos-inputs.json",
    "tau3-fused-inputs.json",
    "tau3-sparse-inputs.json",
    "tau3-radix27-inputs.json",
    "tau3-scatter-inputs/inputs.json",
    "tau3-scatter-direct-inputs/inputs.json",
    "tau3-scatter-atlas-inputs/inputs.json",
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make(repo, design_path, output_dir):
    design_blob = design_path.read_bytes()
    design = json.loads(design_blob)
    if design.get("status") != "frozen_retrospective_design":
        raise ValueError("radix design is not frozen")
    excluded = {"glv-j0-32": set(), "j0-56": set()}
    prior_hashes = {}
    for name in PRIOR:
        manifest_path = repo / name
        manifest_blob = manifest_path.read_bytes()
        prior_hashes[name] = sha256(manifest_blob)
        for case in json.loads(manifest_blob)["cases"]:
            scalar_blob = (manifest_path.parent / case["scalar_file"]).read_bytes()
            if sha256(scalar_blob) != case["scalar_file_sha256"]:
                raise ValueError("prior scalar file changed: " + name)
            excluded[case["curve"]["name"]].update(
                value for (value,) in struct.iter_unpack("<Q", scalar_blob))

    source = json.loads((repo / "compact-pos-inputs.json").read_text())
    rng = random.Random(SEED)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for case in source["cases"]:
        curve = case["curve"]["name"]
        order = case["curve"]["order"]
        values = []
        while len(values) < COUNT:
            value = rng.randrange(order)
            if value not in excluded[curve]:
                excluded[curve].add(value)
                values.append(value)
        blob = b"".join(struct.pack("<Q", value) for value in values)
        name = case["id"] + ".scalars.bin"
        scalar_path = output_dir / name
        if scalar_path.exists() and scalar_path.read_bytes() != blob:
            raise ValueError("frozen scalar file changed: " + name)
        scalar_path.write_bytes(blob)
        cases.append({"id": case["id"], "curve": case["curve"],
                      "base_x": case["base_x"], "base_y": case["base_y"],
                      "count": COUNT, "scalar_file": name,
                      "scalar_file_sha256": sha256(blob)})

    manifest = {"schema": 1, "status": "fresh_disjoint_fixture",
                "design_sha256": sha256(design_blob), "seed": SEED,
                "selection_law": "Python Random.randrange(order); reject every value in seven prior fixtures and earlier new cases on the same curve",
                "prior_manifest_sha256": prior_hashes,
                "source_sha256": sha256(Path(__file__).read_bytes()),
                "cases": cases}
    content = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    manifest_path = output_dir / "inputs.json"
    if manifest_path.exists() and manifest_path.read_bytes() != content:
        raise ValueError("frozen input manifest changed")
    manifest_path.write_bytes(content)
    return {"manifest_sha256": sha256(content), "cases": len(cases),
            "scalars": COUNT * len(cases)}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: make_endo_radix8_inputs.py REPO DESIGN OUTPUT_DIR")
    print(json.dumps(make(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])), sort_keys=True))
