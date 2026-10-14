#!/usr/bin/env python3
"""Materialize the source-pinned mixed-640 crate, then add a pre-tau tree."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PRIOR = HERE.parent / "prime-j0-mixed-radix640-20261010"
CRATE = "experiments/prime-j0-secp256k1-native"
FREEZE = "0c346ac93a7d87f757f7f9917f2bc95213a2c614"


def old_file(relative):
    return subprocess.run(["git", "show", f"{FREEZE}:{CRATE}/{relative}"],
                          cwd=ROOT, check=True, capture_output=True).stdout


def replace_once(body, old, new):
    assert body.count(old) == 1, old[:100]
    return body.replace(old, new, 1)


def prepare(target):
    target = Path(target).resolve()
    assert not target.exists()
    source = target.with_name(target.name + "-source")
    assert not source.exists()
    source.mkdir(parents=True)
    current = ROOT / CRATE
    shutil.copytree(current / "src", source / "src")
    for name in ("tau6-comb13-bench-fixture.json", "width6-tau-result.json"):
        shutil.copyfile(current / name, source / name)
    for name in ("Cargo.toml", "Cargo.lock", "src/bin/eisenstein_fixed.rs",
                 "src/bin/eisenstein_fixed/unit_orbit_windows.rs"):
        dest = source / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(old_file(name))
    spec = importlib.util.spec_from_file_location("mixed640_materializer", PRIOR / "materialize_native.py")
    materializer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(materializer)
    materializer.SOURCE = source
    argv = sys.argv
    try:
        sys.argv = [str(PRIOR / "materialize_native.py"), str(target)]
        materializer.main()
    finally:
        sys.argv = argv

    module = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    body = module.read_text()
    addition = (HERE / "native_variant.rs").read_text().replace(
        "__MIXED640_PANEL__", str(PRIOR / "fresh-inputs.json"))
    body = replace_once(body, "#[cfg(test)]\nmod tests {", addition + "\n#[cfg(test)]\nmod tests {")
    module.write_text(body)

    receipt = {"schema": 1, "source_commit": FREEZE,
               "variant_sha256": sha256((HERE / "native_variant.rs").read_bytes()).hexdigest(),
               "generated_sha256": sha256(module.read_bytes()).hexdigest(),
               "base_patch_sha256": sha256((PRIOR / "native-candidate.patch").read_bytes()).hexdigest()}
    (target / "native-overlay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    assert len(sys.argv) == 2, "usage: native_overlay.py OUTPUT_DIRECTORY"
    print(json.dumps(prepare(sys.argv[1]), sort_keys=True))
