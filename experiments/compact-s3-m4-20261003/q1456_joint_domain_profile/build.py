#!/usr/bin/env python3
"""Receipt the Q1456 native domain profiler build."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
CADICAL = Path("/opt/homebrew/opt/cadical")
BINARY = HERE / "domain_probe"
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "domain_probe.cpp": HERE / "domain_probe.cpp",
    "joint_base.cpp": HERE / "joint_base.cpp",
    "q1446_theory_solver.cpp": PARENT /
        "q1446_joint_pair_span/theory_solver.cpp",
    "root_field.hpp": PARENT / "q1420_root_theory/root_field.hpp",
    "lift_gate.hpp": PARENT / "q1422_leaf_lift_gate/lift_gate.hpp",
    "cached_span.hpp": PARENT / "q1432_coefficient_cache/cached_span.hpp",
    "span_filter.hpp": PARENT / "q1431_guarded_span/span_filter.hpp",
    "cadical.hpp": CADICAL / "include/cadical.hpp",
    "libcadical.a": CADICAL / "lib/libcadical.a",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command() -> list[str]:
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(CADICAL / "include"),
            str(HERE / "domain_probe.cpp"),
            str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w",
            "-o", str(BINARY)]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert BINARY.is_file()
    return {
        "proposal_id": "Q1456", "stage": "exact_joint_domain_profile",
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
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    assert not (args.check and args.rebuild)
    if args.rebuild:
        subprocess.run(command(), check=True)
    current = describe()
    if args.check or args.rebuild:
        assert current == json.loads(RECEIPT.read_text())
        print("Q1456 native domain build: PASS")
    else:
        if RECEIPT.exists():
            raise FileExistsError(RECEIPT)
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1456",
                          "binary_sha256": current["binary_sha256"]}))


if __name__ == "__main__":
    main()
