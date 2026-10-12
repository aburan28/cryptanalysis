#!/usr/bin/env python3
"""Run the original rho0 atlas on the priority panel with identical code."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "priority_control_parent", HERE / "materialize_native.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
PANEL = HERE / "priority-fresh-inputs.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert len(sys.argv) == 2, "usage: materialize_priority_control.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    panel_check = json.loads((HERE / "priority-input-check.json").read_bytes())
    assert panel_check["status"] == "passed"
    assert panel_check["input_sha256"] == digest(PANEL)
    subprocess.run([sys.executable, str(HERE / "materialize_native.py"),
                    str(output)], check=True, capture_output=True)
    parent_raw = (output / "materialization.json").read_bytes()
    parent = json.loads(parent_raw)
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected
    shutil.copyfile(PANEL, output / prior.PANEL)
    final = {"schema": 1, "timing_class": "correctness_only",
             "purpose": "original_assignment_same_panel_control",
             "materializer_sha256": digest(Path(__file__)),
             "parent_materialization_sha256": sha256(parent_raw).hexdigest(),
             "generated_sha256": parent["generated_sha256"],
             "assets_sha256": {prior.ATLAS: digest(output / prior.ATLAS),
                               prior.PANEL: digest(output / prior.PANEL)},
             "priority_input_receipt_sha256": digest(
                 HERE / "priority-input-check.json")}
    (output / "materialization.json").write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"generated_sha256": final["generated_sha256"],
                      "assets_sha256": final["assets_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
