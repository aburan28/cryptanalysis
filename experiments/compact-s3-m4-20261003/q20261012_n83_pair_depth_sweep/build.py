#!/usr/bin/env python3
"""Build exact-block WDSat with capacity for seven blocked pairs."""
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1508 = PARENT / "q20261012_n83_blocked_pair_handoff"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1509_pair_depth")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = json.loads((Q1508 / "build_receipt.json").read_text())
    source = Path(parent["binary_path"]).parent / "src"
    assert sha(source / "config.h") == parent["config_sha256"]
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    BUILD.mkdir()
    shutil.copytree(source, BUILD / "src")
    config = BUILD / "src/config.h"
    old = config.read_text()
    for a, b in (("__MAX_ID__ 65710", "__MAX_ID__ 66700"),
                 ("__MAX_EQ__ 192315", "__MAX_EQ__ 194000"),
                 ("__MAX_BUFFER_SIZE__ 647234", "__MAX_BUFFER_SIZE__ 680000")):
        assert old.count(a) == 1
        old = old.replace(a, b)
    config.write_text(old)
    proc = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                          text=True, capture_output=True)
    (HERE / "build.stdout.txt").write_text(
        "\n".join(line.rstrip() for line in proc.stdout.splitlines()) + "\n")
    (HERE / "build.stderr.txt").write_text(proc.stderr)
    binary = BUILD / "wdsat_solver"
    assert proc.returncode == 0 and binary.exists(), proc.stderr[-2000:]
    result = {"proposal_id": "Q1509", "candidate_id": None,
              "parent_build_receipt_sha256": sha(Q1508 / "build_receipt.json"),
              "source_sha256": sha(Path(__file__)), "config_sha256": sha(config),
              "binary_path": str(binary), "binary_sha256": sha(binary),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                    text=True).splitlines()[0],
              "architecture": platform.machine(),
              "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
              "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
              "return_code": proc.returncode}
    (HERE / "build_receipt.json").write_text(json.dumps(result, indent=2,
                                                         sort_keys=True) + "\n")
    print("PASS Q1509 seven-block capacity", sha(binary)[:12])


if __name__ == "__main__":
    main()
