#!/usr/bin/env python3
"""Replay the frozen two-image radix-1024 control on the new panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONTROL = HERE.parent / "prime-j0-power2-residual-20261010"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    source = CONTROL / "verify_group.py"
    spec = importlib.util.spec_from_file_location("power2_two_image_control", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    atlases = {
        "full": module.FullAtlas(CONTROL / "atlas-r1024-full.bin"),
        "terminal": module.TerminalAtlas(CONTROL / "atlas-r1024-terminal.bin"),
    }
    result = module.check_panel(HERE / "fresh-inputs.json", 4096, atlases)
    candidate = json.loads((HERE / "group-check.json").read_text())["panel"]
    assert result["cases"] == candidate["cases"] == 4096
    assert result["input_sha256"] == candidate["input_sha256"]
    assert result["output_sha256"] == candidate["output_sha256"]
    receipt = {"schema": 1, "status": "passed",
               "control_source_sha256": digest(source.read_bytes()),
               "control_atlas_sha256": {name: atlas.digest
                                        for name, atlas in atlases.items()},
               "candidate_source_sha256": digest((HERE / "verify_group.py").read_bytes()),
               "control": result, "candidate": candidate}
    normalized = json.loads(json.dumps(receipt, sort_keys=True))
    path = HERE / "control-group.json"
    if path.exists():
        assert json.loads(path.read_text()) == normalized
    else:
        path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "cases": 4096,
                      "output_sha256": result["output_sha256"],
                      "candidate_additions": candidate["mixed_additions"],
                      "control_additions": result["mixed_additions"],
                      "candidate_gauge_rotations": candidate["gauge_rotations"],
                      "control_gauge_rotations": result["gauge_rotations"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
