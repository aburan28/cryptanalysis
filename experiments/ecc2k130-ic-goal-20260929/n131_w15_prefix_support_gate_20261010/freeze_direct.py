#!/usr/bin/env python3
"""Freeze independent direct enumeration source and exact W15 input."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    compiler = shutil.which("c++")
    assert compiler is not None
    version = subprocess.run([compiler, "--version"], capture_output=True,
                             text=True, check=True).stdout.splitlines()[0]
    sources = {"freeze_direct": Path(__file__),
               "run_direct": HERE / "run_direct.py",
               "enumerator": HERE / "audit_seed_counts.cpp",
               "w15_support": W15 / "support_w15.tsv",
               "w15_count": W15 / "seed_sum_count.json",
               "support_protocol": W15 / "support_protocol.json"}
    record = {
        "status": "FROZEN_BEFORE_DIRECT_W15_PAIR_ENUMERATION",
        "compiler": compiler,
        "compiler_version_first_line": version,
        "compiler_flags": ["-O3", "-std=c++17", "-Wall", "-Wextra"],
        "wall_cap_seconds": 120,
        "source_sha256": {name: sha(path) for name, path in sources.items()},
    }
    with (HERE / "direct_protocol.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(record["status"])


if __name__ == "__main__":
    main()
