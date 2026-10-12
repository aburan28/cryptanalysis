#!/usr/bin/env python3
"""Swap only the atlas and fresh panel in the exact rho0 native code."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "priority_native_parent", HERE / "materialize_native.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
ATLAS = HERE / "atlas-r1024-full-dual-priority.bin"
PANEL = HERE / "priority-fresh-inputs.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert len(sys.argv) == 2, "usage: materialize_priority_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    receipt = json.loads((HERE / "priority-native-atlas-check.json").read_bytes())
    assert receipt["status"] == "passed"
    assert receipt["atlas_sha256"] == digest(ATLAS)
    panel_check = json.loads((HERE / "priority-input-check.json").read_bytes())
    assert panel_check["status"] == "passed"
    assert panel_check["input_sha256"] == digest(PANEL)
    subprocess.run([sys.executable, str(HERE / "materialize_native.py"),
                    str(output)], check=True, capture_output=True)
    parent_raw = (output / "materialization.json").read_bytes()
    parent = json.loads(parent_raw)
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected
    shutil.copyfile(ATLAS, output / prior.ATLAS)
    shutil.copyfile(PANEL, output / prior.PANEL)
    final = {"schema": 1, "timing_class": "correctness_only",
             "purpose": "priority_assignment_same_code",
             "materializer_sha256": digest(Path(__file__)),
             "parent_materialization_sha256": sha256(parent_raw).hexdigest(),
             "generated_sha256": parent["generated_sha256"],
             "included_assets_sha256": parent["parent_materialization"].get(
                 "included_assets_sha256", {}),
             "assets_sha256": {prior.ATLAS: digest(output / prior.ATLAS),
                               prior.PANEL: digest(output / prior.PANEL)},
             "priority_atlas_receipt_sha256": digest(
                 HERE / "priority-native-atlas-check.json"),
             "priority_input_receipt_sha256": digest(
                 HERE / "priority-input-check.json")}
    (output / "materialization.json").write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"generated_sha256": final["generated_sha256"],
                      "assets_sha256": final["assets_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
