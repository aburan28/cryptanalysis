#!/usr/bin/env python3
"""Build the source-pinned radix-1024 residual mode in a separate crate."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-asymmetric-r944-20261010"
SOURCE_FILES = (
    "src/bin/eisenstein_fixed.rs",
    "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
)
ASSETS = (
    "atlas-r1024-full.bin",
    "atlas-r1024-terminal.bin",
    "fresh-inputs.json",
)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert len(sys.argv) == 2, "usage: materialize_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(PARENT / "materialize_native.py"), str(output)],
                   check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_text())
    for name in ASSETS:
        shutil.copyfile(HERE / name, output / name)
        assert digest(HERE / name) == digest(output / name)
    patch = HERE / "native-delta.patch"
    subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=output,
                   check=True, capture_output=True)
    receipt = {
        "schema": 1,
        "timing_class": "correctness_only",
        "parent_materialization": parent,
        "native_delta_sha256": digest(patch),
        "assets_sha256": {name: digest(output / name) for name in ASSETS},
        "generated_sha256": {name: digest(output / name) for name in SOURCE_FILES},
    }
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
