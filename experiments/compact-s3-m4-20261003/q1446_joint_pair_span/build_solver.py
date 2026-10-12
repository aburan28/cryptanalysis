#!/usr/bin/env python3
"""Build and receipt the Q1446 native joint-pair solver."""

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
BINARY = HERE / "theory_solver"
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "theory_solver.cpp": HERE / "theory_solver.cpp",
    "root_field.hpp": PARENT / "q1420_root_theory/root_field.hpp",
    "lift_gate.hpp": PARENT / "q1422_leaf_lift_gate/lift_gate.hpp",
    "cached_span.hpp": PARENT / "q1432_coefficient_cache/cached_span.hpp",
    "span_filter.hpp": PARENT / "q1431_guarded_span/span_filter.hpp",
    "cadical.hpp": CADICAL / "include/cadical.hpp",
    "libcadical.a": CADICAL / "lib/libcadical.a",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_command():
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(CADICAL / "include"), str(HERE / "theory_solver.cpp"),
            str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w",
            "-o", str(BINARY)]


def describe():
    assert all(path.is_file() for path in SOURCES.values())
    assert BINARY.is_file()
    return {
        "proposal_id": "Q1446",
        "machine": platform.machine(), "system": platform.system(),
        "release": platform.release(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "cadical_version": subprocess.run(
            ["cadical", "--version"], check=True, capture_output=True,
            text=True).stdout.strip(),
        "command": build_command(),
        "source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "build_script_sha256": sha(Path(__file__)),
        "binary_sha256": sha(BINARY),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    assert not (args.check and args.rebuild)
    if args.rebuild:
        subprocess.run(build_command(), check=True)
    current = describe()
    if args.check or args.rebuild:
        assert json.loads(RECEIPT.read_text()) == current
        print("Q1446 native build: PASS")
    else:
        assert not RECEIPT.exists(), "refuse overwrite"
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"binary_sha256": current["binary_sha256"],
                          "status": "pass"}, sort_keys=True))
