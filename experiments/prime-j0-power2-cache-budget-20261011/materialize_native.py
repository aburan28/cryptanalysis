#!/usr/bin/env python3
"""Materialize the source-pinned native three-image evaluator with budgeted assets."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011"
SOURCE = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
OTHER_SOURCE = "src/bin/eisenstein_fixed.rs"
ASSETS = {
    "atlas-r1024-full-cache-budget.bin": "atlas-r1024-full-tau2.bin",
    "atlas-r1024-terminal-cache-budget.bin": "atlas-r1024-terminal-tau2.bin",
    "fresh-inputs.json": "fresh-inputs.json",
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def main():
    assert len(sys.argv) == 2, "usage: materialize_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(PARENT / "materialize_native.py"), str(output)],
                   check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_bytes())
    assert parent["timing_class"] == "correctness_only"
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected

    group_path = HERE / "group-check.json"
    group = json.loads(group_path.read_bytes())
    assert group["status"] == "passed"
    panel = group["results"]["budgeted"]
    assert panel["cases"] == 4096
    assert group["results"]["minimum"]["output_sha256"] == panel["output_sha256"]
    for source_name, destination_name in ASSETS.items():
        source = HERE / source_name
        if source_name.startswith("atlas-"):
            kind = "full" if "full" in source_name else "terminal"
            assert digest(source) == group["atlas_sha256"]["budgeted"][kind]
        else:
            assert digest(source) == group["input_sha256"]
        shutil.copyfile(source, output / destination_name)
        assert digest(source) == digest(output / destination_name)

    path = output / SOURCE
    source = path.read_text()
    source = replace_once(source, "assert_eq!(seed_count, 73_417);",
                          "assert_eq!(seed_count, 77_513);")
    source = replace_once(source, "assert_eq!(entries, 890_292);",
                          "assert_eq!(entries, 939_444);")
    source = replace_once(source,
                          "assert!(retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES < 63_000_000);",
                          "assert!(retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES < 67_108_864);")
    expected_operations = (panel["mixed_additions"], panel["gauge_rotations"])
    source = replace_once(source,
                          "assert_eq!((additions, gauge_products), (49_151, 18_186));",
                          "assert_eq!((additions, gauge_products), "
                          f"({expected_operations[0]:_}, {expected_operations[1]:_}));")
    path.write_text(source)
    receipt = {"schema": 1, "timing_class": "correctness_only",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization": parent,
               "group_receipt_sha256": digest(group_path),
               "assets_sha256": {destination: digest(output / destination)
                                 for destination in ASSETS.values()},
               "generated_sha256": {name: digest(output / name)
                                    for name in (OTHER_SOURCE, SOURCE)}}
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
