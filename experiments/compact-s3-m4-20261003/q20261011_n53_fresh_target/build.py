#!/usr/bin/env python3
"""Build frozen Q1461 first-match native quotient-pair solver."""
from __future__ import annotations
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent / "q20261011_n53_native_pair"
TEMP = Path("/private/tmp/q1461_n53_target")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert TEMP.is_dir() and not (HERE / "build_receipt.json").exists()
    freeze = json.loads((HERE / "freeze.json").read_text())
    assert freeze["native_source_sha256"] == sha(HERE / "native_first.cpp")
    assert freeze["field_source_sha256"] == sha(PAIR / "native_field53.hpp")
    binary = TEMP / "native_first"
    command = ["/usr/bin/clang++", "-O3", "-std=c++17", "-o", str(binary),
               str(HERE / "native_first.cpp")]
    result = subprocess.run(command, capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(result.stdout)
    (HERE / "build.stderr.txt").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    output = {"proposal_id": "Q1461", "candidate_id": None,
              "compiler": subprocess.check_output([command[0], "--version"],
                                                  text=True).splitlines()[0],
              "architecture": platform.machine(), "os": platform.platform(),
              "flags": command[1:3], "binary_path": str(binary),
              "binary_sha256": sha(binary),
              "source_sha256": sha(HERE / "native_first.cpp"),
              "field_source_sha256": sha(PAIR / "native_field53.hpp"),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
              "build_stderr_sha256": sha(HERE / "build.stderr.txt")}
    (HERE / "build_receipt.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    print("BUILT Q1461", output["binary_sha256"][:12])


if __name__ == "__main__":
    main()
