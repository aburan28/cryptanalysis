#!/usr/bin/env python3
"""Build the Voronoi terminal theorem and its pinned scalar dependencies."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / "experiments"
MODULES = (
    EXP / "prime-j0-radix919-terminal-unit-20261012/TerminalUnit.lean",
    EXP / "prime-j0-radix919-terminal-unit-20261012/DigitCover.lean",
    EXP / "prime-j0-power2-direct-terminal-20261012/TopBound.lean",
    HERE / "VoronoiTerminal.lean",
)
NATIVE_SOURCE = EXP / "prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs"
OUTPUTS = ("TerminalUnit", "LegacyDigitCover", "TopBound", "VoronoiTerminal")
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
AXIOM_LINE = re.compile(
    r"'([^']+)' (?:depends on axioms: \[([^\]]*)\]|does not depend on any axioms)",
    re.MULTILINE,
)


def check_native_reciprocals() -> str:
    """Bind the Lean literal words to the two arrays executed by Rust."""
    native = NATIVE_SOURCE.read_text()
    lean = MODULES[-1].read_text()
    names = (("RECIP_V1", "nativeRecipV1", "nativeRecipV1Words"),
             ("RECIP_MINUS_W1", "nativeRecipMinusW1", "nativeRecipMinusW1Words"))
    for rust_name, lean_name, list_name in names:
        rust_match = re.search(
            rf"const {rust_name}: \[u64; 7\] = \[(.*?)\];", native, re.DOTALL)
        lean_match = re.search(
            rf"def {lean_name} : Int :=(.*?)(?=\ndef |\ntheorem )", lean, re.DOTALL)
        if rust_match is None or lean_match is None:
            raise RuntimeError(f"missing reciprocal source for {rust_name}")
        rust_words = [int(word, 0) for word in re.findall(
            r"0x[0-9a-fA-F]+|\b[0-9]+\b", rust_match.group(1))]
        lean_words = [int(word, 0) for word in re.findall(
            r"0x[0-9a-fA-F]+", lean_match.group(1))]
        if len(rust_words) != 7 or rust_words != lean_words:
            raise RuntimeError(f"native/Lean reciprocal mismatch: {rust_name}")
        list_match = re.search(
            rf"def {list_name}\s*:\s*List Int :=\s*\[(.*?)\]", lean, re.DOTALL)
        if list_match is None:
            raise RuntimeError(f"missing modeled reciprocal words: {list_name}")
        list_words = [int(word, 0) for word in re.findall(
            r"0x[0-9a-fA-F]+", list_match.group(1))]
        if list_words != rust_words:
            raise RuntimeError(f"native/Lean word-list mismatch: {rust_name}")
    return sha256(NATIVE_SOURCE.read_bytes()).hexdigest()


def build_receipt() -> str:
    native_sha = check_native_reciprocals()
    toolchain = (HERE / "lean-toolchain").read_text().strip()
    env = os.environ.copy()
    env["ELAN_TOOLCHAIN"] = toolchain
    version = subprocess.run(["lean", "--version"], cwd=ROOT, env=env,
                             check=True, capture_output=True, text=True).stdout.strip()
    if not version.startswith("Lean (version 4.34.1,"):
        raise RuntimeError(f"wrong Lean version: {version}")
    records = [f"toolchain={toolchain}", "lean_release=4.34.1",
               f"sha256 {NATIVE_SOURCE.relative_to(ROOT)}: {native_sha}"]
    with tempfile.TemporaryDirectory(prefix="hex-terminal-lean-") as work:
        env["LEAN_PATH"] = work
        for source, name in zip(MODULES, OUTPUTS, strict=True):
            body = source.read_text()
            if re.search(r"\b(?:sorry|admit|sorryAx|axiom)\b", body):
                raise RuntimeError(f"unverified proof token in {source}")
            expected = len(re.findall(r"^#print axioms ", body, re.MULTILINE))
            records.append(f"sha256 {source.relative_to(ROOT)}: {sha256(source.read_bytes()).hexdigest()}")
            result = subprocess.run(
                ["lean", "-o", str(Path(work) / f"{name}.olean"), str(source)],
                cwd=ROOT, env=env, capture_output=True, text=True,
            )
            if result.returncode or "error:" in result.stdout + result.stderr:
                raise RuntimeError(f"{name} failed:\n{result.stdout}{result.stderr}")
            matches = list(AXIOM_LINE.finditer(result.stdout))
            if len(matches) != expected:
                raise RuntimeError(f"{name}: {len(matches)} axiom audits, expected {expected}")
            for match in matches:
                axioms = set(match.group(2).replace("\n", " ").replace(",", " ").split()) if match.group(2) else set()
                if axioms - ALLOWED_AXIOMS:
                    raise RuntimeError(f"{name}: unexpected axioms {axioms - ALLOWED_AXIOMS}")
                records.append(f"{match.group(1)}: {','.join(sorted(axioms)) or 'none'}")
            records.append(f"built={name}")
    return "\n".join(records) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actual = build_receipt()
    path = HERE / "lean-build.txt"
    if args.write:
        path.write_text(actual)
        print(f"wrote {path}")
    elif path.read_text() != actual:
        raise SystemExit("Lean receipt differs from pinned sources")
    else:
        print("Lean build and axiom audit verified")


if __name__ == "__main__":
    main()
