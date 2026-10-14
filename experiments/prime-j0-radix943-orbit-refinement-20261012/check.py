#!/usr/bin/env python3
"""Build the pinned Lean proof and verify its source and axiom receipt."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCES = (
    ("Termination", Path("experiments/prime-j0-radix943-termination-20261012/Termination.lean")),
    ("DigitCover", Path("experiments/prime-j0-radix943-digit-cover-20261012/DigitCover.lean")),
    ("OrbitAtlas", Path("experiments/prime-j0-radix943-orbit-refinement-20261012/OrbitAtlas.lean")),
)
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def receipt() -> str:
    toolchain = (HERE / "lean-toolchain").read_text().strip()
    env = os.environ.copy()
    env["ELAN_TOOLCHAIN"] = toolchain
    version = subprocess.run(["lean", "--version"], env=env, cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    if not version.startswith("Lean (version 4.34.1,"):
        raise RuntimeError(f"wrong Lean version: {version.strip()}")
    records = [f"toolchain={toolchain}"]
    for _, source in SOURCES:
        digest = hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
        records.append(f"sha256 {source}: {digest}")
    with tempfile.TemporaryDirectory(prefix="radix943-orbit-lean-") as work:
        env["LEAN_PATH"] = work
        for module, source in SOURCES:
            result = subprocess.run(
                ["lean", "-o", str(Path(work) / f"{module}.olean"), str(source)],
                env=env, cwd=ROOT, capture_output=True, text=True,
            )
            if result.returncode:
                raise RuntimeError(f"{source} failed:\n{result.stdout}{result.stderr}")
            if "error:" in result.stdout + result.stderr:
                raise RuntimeError(f"{source} reported an error")
            records.append(f"built {source}")
            if module == "OrbitAtlas":
                axioms = [line for line in result.stdout.splitlines()
                          if "depends on axioms:" in line or "does not depend on any axioms" in line]
                if len(axioms) != 9:
                    raise RuntimeError(f"expected nine #print axioms lines, got {len(axioms)}")
                for line in axioms:
                    match = re.search(r"depends on axioms: \[(.*)\]$", line)
                    if match and set(match.group(1).split(", ")) - ALLOWED_AXIOMS:
                        raise RuntimeError(f"unexpected axiom: {line}")
                    records.append(line)
    return "\n".join(records) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actual = receipt()
    path = HERE / "lean-build.txt"
    if args.write:
        path.write_text(actual)
        print(f"wrote {path.relative_to(ROOT)}")
    elif path.read_text() != actual:
        raise SystemExit("Lean source or axiom receipt differs; rerun --write after review")
    else:
        print("orbit-atlas Lean build and axiom receipt verified")


if __name__ == "__main__":
    main()
