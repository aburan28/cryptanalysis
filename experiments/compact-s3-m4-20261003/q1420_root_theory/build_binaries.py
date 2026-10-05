#!/usr/bin/env python3
"""Build and receipt the Q1420 native root/theory executables."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CADICAL = Path("/opt/homebrew/opt/cadical")
RECEIPT = HERE / "compile_receipt.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(source, output, cadical=False):
    args = ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror"]
    if cadical:
        args.extend(["-I" + str(CADICAL / "include")])
    args.append(str(HERE / source))
    if cadical:
        args.extend([str(CADICAL / "lib/libcadical.a"), "-pthread",
                     "-Wl,-w"])
    args.extend(["-o", str(HERE / output)])
    return args


def build():
    sources = ("root_field.hpp", "root_field_cli.cpp", "probe_cadical.cpp",
               "theory_solver.cpp")
    header = CADICAL / "include/cadical.hpp"
    library = CADICAL / "lib/libcadical.a"
    assert header.is_file() and library.is_file()
    commands = [command("root_field_cli.cpp", "root_field_cli"),
                command("probe_cadical.cpp", "probe_cadical", True),
                command("theory_solver.cpp", "theory_solver", True)]
    for args in commands:
        subprocess.run(args, check=True, capture_output=True, text=True)
    return {
        "kind": "q1420_native_compile_receipt",
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
        "source_sha256": {name: sha(HERE / name) for name in sources},
        "commands": commands,
        "binary_sha256": {name: sha(HERE / name) for name in
                          ("root_field_cli", "probe_cadical", "theory_solver")},
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
                    "source_sha256", "binary_sha256"):
            assert rebuilt[key] == stored[key], key
    if args.check:
        stored = json.loads(RECEIPT.read_text())
        assert stored["cadical_header_sha256"] == sha(
            CADICAL / "include/cadical.hpp")
        assert stored["cadical_library_sha256"] == sha(
            CADICAL / "lib/libcadical.a")
        for source, digest in stored["source_sha256"].items():
            assert sha(HERE / source) == digest
        for binary, digest in stored["binary_sha256"].items():
            assert sha(HERE / binary) == digest
    elif not args.rebuild:
        assert not RECEIPT.exists()
        RECEIPT.write_text(json.dumps(build(), indent=2,
                                      sort_keys=True) + "\n")
    print(RECEIPT)


if __name__ == "__main__":
    main()
