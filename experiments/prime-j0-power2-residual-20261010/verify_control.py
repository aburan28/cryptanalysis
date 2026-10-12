#!/usr/bin/env python3
"""Replay the frozen radix-944 control on the new scalar panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONTROL = HERE.parent / "prime-j0-asymmetric-r944-20261010"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    source = CONTROL / "verify_group.py"
    spec = importlib.util.spec_from_file_location("r944_group_control", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    atlases = {
        "944": module.Atlas(CONTROL / "atlas-r944-d944.bin", 944, b"T944"),
        "550": module.Atlas(CONTROL / "atlas-r944-d550.bin", 944, b"T944"),
    }
    result = module.check_panel(HERE / "fresh-inputs.json", 4096, atlases)
    candidate = json.loads((HERE / "group-check.json").read_text())["panel"]
    assert result["cases"] == candidate["cases"] == 4096
    assert result["input_sha256"] == candidate["input_sha256"]
    assert result["output_sha256"] == candidate["output_sha256"]
    receipt = {
        "schema": 1,
        "status": "passed",
        "control_source_sha256": digest(source.read_bytes()),
        "control_atlas_sha256": {name: atlas.digest
                                 for name, atlas in atlases.items()},
        "candidate_source_sha256": digest((HERE / "verify_group.py").read_bytes()),
        "control": result,
        "candidate": candidate,
    }
    path = HERE / "control-group.json"
    normalized = json.loads(json.dumps(receipt, sort_keys=True))
    if path.exists():
        assert json.loads(path.read_text()) == normalized
    else:
        path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "cases": 4096,
                      "output_sha256": result["output_sha256"],
                      "candidate_additions": candidate["mixed_additions"],
                      "control_additions": result["mixed_additions"]}, sort_keys=True))


if __name__ == "__main__":
    main()
