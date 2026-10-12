#!/usr/bin/env python3
"""Build and receipt Q1462's exact sparse-sum SAT propagator."""

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
RECEIPT = HERE / "compile_receipt.json"
SOURCES = {
    "native_solver.cpp": HERE / "native_solver.cpp",
    "control_guard.cpp": HERE / "control_guard.cpp",
    "q1461_sparse_sum.hpp": PARENT / "q1461_sparse_sum_inverse/sparse_sum.hpp",
    "q1446_theory_solver.cpp": PARENT / "q1446_joint_pair_span/theory_solver.cpp",
    "q1432_cached_span.hpp": PARENT / "q1432_coefficient_cache/cached_span.hpp",
    "q1431_span_filter.hpp": PARENT / "q1431_guarded_span/span_filter.hpp",
    "q1422_lift_gate.hpp": PARENT / "q1422_leaf_lift_gate/lift_gate.hpp",
    "q1420_root_field.hpp": PARENT / "q1420_root_theory/root_field.hpp",
    "cadical.hpp": CADICAL / "include/cadical.hpp",
    "libcadical.a": CADICAL / "lib/libcadical.a",
}
BINARIES = {
    "native_solver": (HERE / "native_solver", SOURCES["native_solver.cpp"]),
    "control_guard": (HERE / "control_guard", SOURCES["control_guard.cpp"]),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(name: str) -> list[str]:
    binary, source = BINARIES[name]
    return ["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(CADICAL / "include"), str(source),
            str(CADICAL / "lib/libcadical.a"), "-pthread", "-Wl,-w",
            "-o", str(binary)]


def describe() -> dict:
    assert all(path.is_file() for path in SOURCES.values())
    assert all(binary.is_file() for binary, _ in BINARIES.values())
    return {
        "proposal_id": "Q1462",
        "machine": platform.machine(), "system": platform.system(),
        "release": platform.release(),
        "compiler_version": subprocess.run(
            ["c++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "cadical_version": subprocess.run(
            ["cadical", "--version"], check=True, capture_output=True,
            text=True).stdout.strip(),
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
        print("Q1462 native build: PASS")
    elif args.rebuild:
        if RECEIPT.exists():
            raise FileExistsError(RECEIPT)
        RECEIPT.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n")
        print("Q1462 native solver built")
    else:
        print(json.dumps(current, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
