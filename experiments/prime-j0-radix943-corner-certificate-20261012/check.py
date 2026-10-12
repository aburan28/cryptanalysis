#!/usr/bin/env python3
"""Build and audit the pinned reciprocal-corner Lean proof."""

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
    ("CornerCertificate", Path("experiments/prime-j0-radix943-corner-certificate-20261012/CornerCertificate.lean")),
)
NATIVE_SOURCES = (
    Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs"),
    Path("experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"),
)
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
AXIOM_OUTPUT = re.compile(
    r"'PrimeJ0Radix943CornerCertificate\.(\w+)' "
    r"(does not depend on any axioms|depends on axioms: \[([^\]]+)\])",
    re.DOTALL,
)


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
        contents = (ROOT / source).read_bytes()
        if source.name == "CornerCertificate.lean":
            if re.search(rb"\b(sorry|admit|sorryAx)\b", contents):
                raise RuntimeError("proof contains an unchecked placeholder")
            if re.search(rb"(?m)^\s*(axiom|constant)\b", contents):
                raise RuntimeError("proof declares a custom axiom or constant")
        records.append(f"sha256 {source}: {hashlib.sha256(contents).hexdigest()}")
    for source in NATIVE_SOURCES:
        records.append(f"sha256 {source}: {hashlib.sha256((ROOT / source).read_bytes()).hexdigest()}")
    expected = re.findall(r"^#print axioms (\w+)$",
                          (HERE / "CornerCertificate.lean").read_text(), re.MULTILINE)
    with tempfile.TemporaryDirectory(prefix="radix943-corner-lean-") as work:
        env["LEAN_PATH"] = work
        for module, source in SOURCES:
            result = subprocess.run(
                ["lean", "-o", str(Path(work) / f"{module}.olean"), str(source)],
                env=env, cwd=ROOT, capture_output=True, text=True,
            )
            if result.returncode or result.stderr or "error:" in result.stdout:
                raise RuntimeError(f"{source} failed:\n{result.stdout}{result.stderr}")
            records.append(f"built {source}")
            if module == "CornerCertificate":
                found = AXIOM_OUTPUT.findall(result.stdout)
                if [name for name, _, _ in found] != expected:
                    raise RuntimeError("#print axioms output does not match every declared audit")
                for name, status, raw in found:
                    axioms = set(raw.replace("\n", " ").split(", ")) if raw else set()
                    axioms = {value.strip() for value in axioms}
                    if axioms - ALLOWED_AXIOMS:
                        raise RuntimeError(f"unexpected axiom in {name}: {axioms}")
                    if not raw and status != "does not depend on any axioms":
                        raise RuntimeError(f"missing axiom status for {name}")
                    records.append(f"{name}: {','.join(sorted(axioms)) or 'none'}")
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
        print("reciprocal-corner Lean build and axiom receipt verified")


if __name__ == "__main__":
    main()
