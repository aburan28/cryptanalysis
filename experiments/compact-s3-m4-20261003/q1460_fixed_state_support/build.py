#!/usr/bin/env python3
"""Build the standalone Q1460 exact midpoint profiler."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BINARY = HERE / "midpoint_profile"
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "midpoint_profile.cpp": HERE / "midpoint_profile.cpp",
    "root_field.hpp": PARENT / "q1420_root_theory/root_field.hpp",
    "lift_gate.hpp": PARENT / "q1422_leaf_lift_gate/lift_gate.hpp",
    "batch_roots.hpp": PARENT / "q1458_batch_roots/batch_roots.hpp",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command() -> list[str]:
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            str(SOURCES["midpoint_profile.cpp"]), "-o", str(BINARY)]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert BINARY.is_file()
    return {
        "proposal_id": "Q1460",
        "machine": platform.machine(), "system": platform.system(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "command": command(),
        "source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "build_script_sha256": sha(Path(__file__)),
        "binary_sha256": sha(BINARY),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert not (args.rebuild and args.check)
    if args.rebuild:
        subprocess.run(command(), check=True)
    current = describe()
    if args.check:
        assert current == json.loads(RECEIPT.read_text())
        print("Q1460 midpoint profiler build: PASS")
    elif args.rebuild:
        if RECEIPT.exists():
            raise FileExistsError(RECEIPT)
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print("Q1460 midpoint profiler built")
    else:
        print(json.dumps(current, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
