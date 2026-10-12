#!/usr/bin/env python3
"""Build and fingerprint the frozen Q1529 ARM64 native quotient search."""
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
OUTPUT = Path("/Volumes/SSD990/llm/tmp/q1529-native-w5-query")
SOURCES = ("native_w5_query.cpp", "native_n83_bloom_core.hpp",
           "native_n83_pairs.cpp", "eccF83.h")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    command = ["clang++", "-O3", "-std=c++17", "-pthread",
               "-DECC2K83_ORBITS=186612", "-DECC2K83_FAST_KEYER",
               str((HERE / "native_w5_query.cpp").relative_to(REPO)),
               "-o", str(OUTPUT)]
    compiler = subprocess.run(["clang++", "--version"], text=True,
                              capture_output=True, check=True).stdout
    subprocess.run(command, cwd=REPO, check=True)
    receipt = {"command": command, "compiler_version": compiler,
               "platform": platform.platform(), "machine": platform.machine(),
               "source_sha256": {name: sha(HERE / name) for name in SOURCES},
               "binary_sha256": sha(OUTPUT), "binary_path": str(OUTPUT)}
    (HERE / "build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt["binary_sha256"])


if __name__ == "__main__":
    main()
