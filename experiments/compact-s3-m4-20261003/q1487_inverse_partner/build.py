#!/usr/bin/env python3
"""Build and receipt Q1487's inverse-partner solver and independent test."""

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
SOLVER = HERE / "native_solver"
SELFTEST = HERE / "native_selftest"
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "native_solver.cpp": HERE / "native_solver.cpp",
    "native_selftest.cpp": HERE / "native_selftest.cpp",
    "base_solver.hpp": HERE / "base_solver.hpp",
    "q1486_native_solver.cpp": PARENT /
        "q1486_window_aware_pair/native_solver.cpp",
    "batch_roots.hpp": PARENT / "q1458_batch_roots/batch_roots.hpp",
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


def command(source: Path, output: Path) -> list[str]:
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(CADICAL / "include"), str(source),
            str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w",
            "-o", str(output)]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert SOLVER.is_file() and SELFTEST.is_file()
    assert (HERE / "base_solver.hpp").read_bytes() == (
        (PARENT / "q1486_window_aware_pair/native_solver.cpp")
        .read_bytes().split(b"\nint main(", 1)[0].rstrip(b"\n") + b"\n")
    return {
        "proposal_id": "Q1487",
        "stage": "inverse_s3_partner_support",
        "machine": platform.machine(), "system": platform.system(),
        "release": platform.release(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "cadical_version": subprocess.run(
            ["cadical", "--version"], check=True, capture_output=True,
            text=True).stdout.strip(),
        "solver_command": command(HERE / "native_solver.cpp", SOLVER),
        "selftest_command": command(HERE / "native_selftest.cpp", SELFTEST),
        "source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "build_script_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(SOLVER),
        "selftest_binary_sha256": sha(SELFTEST),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    assert not (args.check and args.rebuild)
    if args.rebuild:
        subprocess.run(command(HERE / "native_solver.cpp", SOLVER),
                       check=True)
        subprocess.run(command(HERE / "native_selftest.cpp", SELFTEST),
                       check=True)
    current = describe()
    if args.check or args.rebuild:
        assert current == json.loads(RECEIPT.read_text())
        print("Q1487 native build: PASS")
    else:
        assert not RECEIPT.exists(), "refuse overwrite"
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1487",
                          "solver_binary_sha256": current[
                              "solver_binary_sha256"]}))


if __name__ == "__main__":
    main()
