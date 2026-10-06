#!/usr/bin/env python3
"""Build the Q1461 exact pair-inversion and independent root-control tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "probe.cpp": HERE / "probe.cpp",
    "sparse_sum.hpp": HERE / "sparse_sum.hpp",
    "root_field_cli.cpp": PARENT / "q1420_root_theory/root_field_cli.cpp",
    "root_field.hpp": PARENT / "q1420_root_theory/root_field.hpp",
    "lift_gate.hpp": PARENT / "q1422_leaf_lift_gate/lift_gate.hpp",
}
BINARIES = {
    "probe": (HERE / "probe", SOURCES["probe.cpp"]),
    "control_roots": (HERE / "control_roots", SOURCES["root_field_cli.cpp"]),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(name: str) -> list[str]:
    binary, source = BINARIES[name]
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            str(source), "-o", str(binary)]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert all(binary.is_file() for binary, _ in BINARIES.values())
    return {
        "proposal_id": "Q1461",
        "machine": platform.machine(), "system": platform.system(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "commands": {name: command(name) for name in BINARIES},
        "source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "build_script_sha256": sha(Path(__file__)),
        "binary_sha256": {name: sha(binary)
                          for name, (binary, _) in BINARIES.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert not (args.rebuild and args.check)
    if args.rebuild:
        for name in BINARIES:
            subprocess.run(command(name), check=True)
    current = describe()
    if args.check:
        assert current == json.loads(RECEIPT.read_text())
        print("Q1461 native build: PASS")
    elif args.rebuild:
        if RECEIPT.exists():
            raise FileExistsError(RECEIPT)
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print("Q1461 native tools built")
    else:
        print(json.dumps(current, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
