#!/usr/bin/env python3
"""Replay one frozen scalar panel through the budgeted and minimum atlases."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011/verify_group.py"
SPEC = importlib.util.spec_from_file_location("three_image_group", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    path = HERE / "fresh-inputs.json"
    input_check = json.loads((HERE / "input-check.json").read_bytes())
    assert input_check["status"] == "passed"
    assert digest(path.read_bytes()) == input_check["input_sha256"]

    variants = {
        "minimum": {
            "full": parent.FullAtlas(PARENT.parent / "atlas-r1024-full-tau2.bin"),
            "terminal": parent.TerminalAtlas(
                PARENT.parent / "atlas-r1024-terminal-tau2.bin"),
        },
        "budgeted": {
            "full": parent.FullAtlas(HERE / "atlas-r1024-full-cache-budget.bin"),
            "terminal": parent.TerminalAtlas(
                HERE / "atlas-r1024-terminal-cache-budget.bin"),
        },
    }
    results = {name: parent.check_panel(path, 4096, atlases)
               for name, atlases in variants.items()}
    a, b = results["minimum"], results["budgeted"]
    assert a["cases"] == b["cases"] == 4096
    assert a["output_sha256"] == b["output_sha256"]
    assert a["mixed_additions"] == b["mixed_additions"]
    receipt = {"schema": 1, "status": "passed", "source_sha256":
               digest(Path(__file__).read_bytes()),
               "parent_verifier_sha256": digest(PARENT.read_bytes()),
               "input_sha256": input_check["input_sha256"],
               "atlas_sha256": {
                   name: {kind: atlas.digest for kind, atlas in atlases.items()}
                   for name, atlases in variants.items()},
               "results": results}
    output = HERE / "group-check.json"
    if output.exists():
        assert json.loads(output.read_text()) == receipt
    else:
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
