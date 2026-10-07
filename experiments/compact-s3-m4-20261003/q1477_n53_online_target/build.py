#!/usr/bin/env python3
"""Build and receipt the Q1477 one-target native comparator."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BINARY = HERE / "online_oracle"
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "online_oracle.cpp": HERE / "online_oracle.cpp",
    "q1468_pair_oracle.cpp": PARENT /
        "q1468_n53_pair_oracle/pair_oracle.cpp",
    "root_field.hpp": PARENT / "q1420_root_theory/root_field.hpp",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command() -> list[str]:
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            str(HERE / "online_oracle.cpp"), "-o", str(BINARY)]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert BINARY.is_file()
    return {
        "proposal_id": "Q1477", "candidate_id": None,
        "stage": "one_target_online_n53_pair_table_descent",
        "machine": platform.machine(), "system": platform.system(),
        "release": platform.release(),
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
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.build != args.check
    if args.build:
        assert not BINARY.exists() and not RECEIPT.exists()
        subprocess.run(command(), check=True)
        RECEIPT.write_text(json.dumps(describe(), sort_keys=True,
                                      indent=2) + "\n")
    else:
        assert describe() == json.loads(RECEIPT.read_text())
    print(json.dumps({"status": "pass", "binary_sha256": sha(BINARY)}))


if __name__ == "__main__":
    main()
