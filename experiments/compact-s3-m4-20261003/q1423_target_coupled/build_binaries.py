#!/usr/bin/env python3
"""Build and receipt the Q1423 target-coupled exact-root solver."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_HEADER = HERE.parent / "q1420_root_theory/root_field.hpp"
LIFT_HEADER = HERE.parent / "q1422_leaf_lift_gate/lift_gate.hpp"
CADICAL = Path("/opt/homebrew/opt/cadical")
RECEIPT = HERE / "compile_receipt.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command():
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(CADICAL / "include"), str(HERE / "theory_solver.cpp"),
            str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w", "-o",
            str(HERE / "theory_solver")]


def build():
    header = CADICAL / "include/cadical.hpp"
    library = CADICAL / "lib/libcadical.a"
    assert all(path.is_file() for path in
               (header, library, ROOT_HEADER, LIFT_HEADER))
    subprocess.run(command(), check=True, capture_output=True, text=True)
    return {
        "kind": "q1423_native_compile_receipt",
        "machine": platform.machine(), "system": platform.system(),
        "release": platform.release(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "cadical_version": subprocess.run(
            ["cadical", "--version"], check=True, capture_output=True,
            text=True).stdout.strip(),
        "cadical_header_sha256": sha(header),
        "cadical_library_sha256": sha(library),
        "root_field_header_sha256": sha(ROOT_HEADER),
        "lift_gate_header_sha256": sha(LIFT_HEADER),
        "source_sha256": sha(HERE / "theory_solver.cpp"),
        "command": command(),
        "binary_sha256": sha(HERE / "theory_solver"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    assert not (args.check and args.rebuild)
    if args.check or args.rebuild:
        stored = json.loads(RECEIPT.read_text())
        if args.rebuild:
            rebuilt = build()
            for key in ("compiler_version", "cadical_version",
                        "cadical_header_sha256", "cadical_library_sha256",
                        "root_field_header_sha256", "lift_gate_header_sha256",
                        "source_sha256", "binary_sha256"):
                assert rebuilt[key] == stored[key], key
        else:
            assert stored["cadical_header_sha256"] == sha(
                CADICAL / "include/cadical.hpp")
            assert stored["cadical_library_sha256"] == sha(
                CADICAL / "lib/libcadical.a")
            assert stored["root_field_header_sha256"] == sha(ROOT_HEADER)
            assert stored["lift_gate_header_sha256"] == sha(LIFT_HEADER)
            assert stored["source_sha256"] == sha(HERE / "theory_solver.cpp")
            assert stored["binary_sha256"] == sha(HERE / "theory_solver")
    else:
        assert not RECEIPT.exists()
        RECEIPT.write_text(json.dumps(build(), indent=2, sort_keys=True) +
                           "\n")
    print(RECEIPT)


if __name__ == "__main__":
    main()
