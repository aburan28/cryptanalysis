#!/usr/bin/env python3
"""Apply the mode-158 patch in a separate Cargo crate without shared-file edits."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / "experiments/prime-j0-secp256k1-native"
HASHES = {
    "src/bin/eisenstein_fixed.rs":
        "f42a2428926eb018ae6674faf672c3d49c1cd25b8106e8a8fe5365db3fa25f22",
    "src/bin/eisenstein_fixed/unit_orbit_windows.rs":
        "b0b5cf662ac1a1be101fcb673a8ac3b59434559244166ff5e5580525a71155d3",
}


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    assert len(sys.argv) in (2, 3), "usage: materialize_native.py OUTPUT_DIRECTORY [--diagnostic]"
    diagnostic = len(sys.argv) == 3
    assert not diagnostic or sys.argv[2] == "--diagnostic"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    for relative, expected in HASHES.items():
        assert digest((SOURCE / relative).read_bytes()) == expected, relative
    for relative in ("Cargo.toml", "Cargo.lock", *HASHES):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, destination)
    patch = HERE / "native-candidate.patch"
    subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=output,
                   check=True, capture_output=True)
    diagnostic_patch = HERE / "ops-diagnostic.patch"
    if diagnostic:
        subprocess.run(["patch", "-p1", "-i", str(diagnostic_patch)], cwd=output,
                       check=True, capture_output=True)

    main_source = output / "src/bin/eisenstein_fixed.rs"
    module_source = output / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    for path, base, old_relative, crate_relative in (
        (main_source, ROOT, '"../../../../', '"../../'),
        (module_source, ROOT / "experiments", '"../../../../', '"../../../'),
    ):
        raw = path.read_text()
        count = raw.count(old_relative)
        assert count > 0
        raw = raw.replace(old_relative, '"' + str(base) + "/")
        crate_count = raw.count(crate_relative)
        assert crate_count > 0
        raw = raw.replace(crate_relative, '"' + str(SOURCE) + "/")
        path.write_text(raw)

    receipt = {
        "schema": 1,
        "timing_class": "correctness_only",
        "source_sha256": HASHES,
        "patch_sha256": digest(patch.read_bytes()),
        "generated_sha256": {name: digest((output / name).read_bytes()) for name in HASHES},
        "asset_root": str(ROOT),
    }
    if diagnostic:
        receipt["diagnostic_patch_sha256"] = digest(diagnostic_patch.read_bytes())
    (output / "materialization.json").write_text(json.dumps(receipt, indent=2,
                                                          sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
