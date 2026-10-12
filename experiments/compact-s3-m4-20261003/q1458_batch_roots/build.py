#!/usr/bin/env python3
"""Build and receipt the Q1458 batched-root native solver and root control."""

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
SOLVER = HERE / "native_batch_solver"
SMOKE = HERE / "smoke_roots"
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "native_batch_solver.cpp": HERE / "native_batch_solver.cpp",
    "batch_roots.hpp": HERE / "batch_roots.hpp",
    "smoke_roots.cpp": HERE / "smoke_roots.cpp",
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


def commands() -> list[list[str]]:
    common = ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror"]
    return [
        common + ["-I" + str(CADICAL / "include"),
                  str(HERE / "native_batch_solver.cpp"),
                  str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w",
                  "-o", str(SOLVER)],
        common + [str(HERE / "smoke_roots.cpp"), "-o", str(SMOKE)],
    ]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert SOLVER.is_file() and SMOKE.is_file()
    return {
        "proposal_id": "Q1458", "stage": "batched_s3_roots",
        "machine": platform.machine(), "system": platform.system(),
        "release": platform.release(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "cadical_version": subprocess.run(
            ["cadical", "--version"], check=True, capture_output=True,
            text=True).stdout.strip(),
        "commands": commands(),
        "source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "build_script_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(SOLVER),
        "smoke_binary_sha256": sha(SMOKE),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    assert not (args.check and args.rebuild)
    if args.rebuild:
        for command in commands():
            subprocess.run(command, check=True)
    current = describe()
    if args.check or args.rebuild:
        assert current == json.loads(RECEIPT.read_text())
        print("Q1458 batched-root native build: PASS")
    else:
        if RECEIPT.exists():
            raise FileExistsError(RECEIPT)
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1458",
                          "solver_binary_sha256": current[
                              "solver_binary_sha256"]}))


if __name__ == "__main__":
    main()
