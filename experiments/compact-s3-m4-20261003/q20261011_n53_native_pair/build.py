#!/usr/bin/env python3
"""Build the frozen Q1454 native ONB quotient-pair stage on this host."""
from __future__ import annotations
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from export import frozen_inputs

HERE = Path(__file__).resolve().parent
FREEZE = HERE / "freeze.json"
OUT = Path("/private/tmp/q1454_n53_sweep")
RECEIPT = HERE / "build_receipt.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert json.loads(FREEZE.read_text()) == frozen_inputs()
    assert not RECEIPT.exists()
    command = ["/usr/bin/clang++", "-O3", "-std=c++17", "-o", str(OUT),
               str(HERE / "native_sweep.cpp")]
    version = subprocess.check_output([command[0], "--version"], text=True).splitlines()[0]
    subprocess.run(command, check=True)
    receipt = {"proposal_id": "Q1454", "compiler": version,
               "architecture": platform.machine(), "os": platform.platform(),
               "flags": command[1:3], "binary_path": str(OUT),
               "binary_sha256": sha(OUT),
               "native_sweep_sha256": sha(HERE / "native_sweep.cpp"),
               "native_field53_sha256": sha(HERE / "native_field53.hpp"),
               "freeze_sha256": sha(FREEZE)}
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("BUILT", receipt["binary_sha256"])


if __name__ == "__main__":
    main()
