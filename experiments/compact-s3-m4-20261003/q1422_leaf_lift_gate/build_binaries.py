#!/usr/bin/env python3
"""Build and receipt the Q1422 native lift-gated solver and probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1420_root_theory"
CADICAL = Path("/opt/homebrew/opt/cadical")
RECEIPT = HERE / "compile_receipt.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solver_command():
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(CADICAL / "include"), str(HERE / "theory_solver.cpp"),
            str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w",
            "-o", str(HERE / "theory_solver")]


def cli_command():
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            str(HERE / "lift_gate_cli.cpp"), "-o",
            str(HERE / "lift_gate_cli")]


def build():
    header = CADICAL / "include/cadical.hpp"
    library = CADICAL / "lib/libcadical.a"
    root_header = PARENT / "root_field.hpp"
    assert header.is_file() and library.is_file() and root_header.is_file()
    for command in (cli_command(), solver_command()):
        subprocess.run(command, check=True, capture_output=True, text=True)
    return {
        "kind": "q1422_native_compile_receipt",
        "machine": platform.machine(),
        "system": platform.system(),
        "release": platform.release(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "cadical_version": subprocess.run(
            ["cadical", "--version"], check=True, capture_output=True,
            text=True).stdout.strip(),
        "cadical_header_sha256": sha(header),
        "cadical_library_sha256": sha(library),
        "root_field_header_sha256": sha(root_header),
        "source_sha256": {name: sha(HERE / name) for name in
                          ("theory_solver.cpp", "lift_gate.hpp",
                           "lift_gate_cli.cpp")},
        "commands": [cli_command(), solver_command()],
        "binary_sha256": {name: sha(HERE / name) for name in
                          ("theory_solver", "lift_gate_cli")},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    assert not (args.check and args.rebuild)
    if args.rebuild:
        stored = json.loads(RECEIPT.read_text())
        rebuilt = build()
        for key in ("compiler_version", "cadical_version",
                    "cadical_header_sha256", "cadical_library_sha256",
                    "root_field_header_sha256", "source_sha256",
                    "binary_sha256"):
            assert rebuilt[key] == stored[key], key
    elif args.check:
        stored = json.loads(RECEIPT.read_text())
        assert stored["cadical_header_sha256"] == sha(
            CADICAL / "include/cadical.hpp")
        assert stored["cadical_library_sha256"] == sha(
            CADICAL / "lib/libcadical.a")
        assert stored["root_field_header_sha256"] == sha(
            PARENT / "root_field.hpp")
        for name, digest in stored["source_sha256"].items():
            assert digest == sha(HERE / name)
        for name, digest in stored["binary_sha256"].items():
            assert digest == sha(HERE / name)
    else:
        assert not RECEIPT.exists()
        RECEIPT.write_text(json.dumps(build(), indent=2, sort_keys=True) +
                           "\n")
    print(RECEIPT)


if __name__ == "__main__":
    main()
