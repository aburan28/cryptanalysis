#!/usr/bin/env python3
"""Rebuild Q1508 WDSat for four exact 166-bit pair blocks."""
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q20261012_n83_blocked_pair_handoff"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1516_pair_block")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = json.loads((PARENT / "build_receipt.json").read_text())
    source = Path(parent["binary_path"]).parent / "src"
    assert sha(source / "config.h") == parent["config_sha256"]
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    BUILD.mkdir()
    shutil.copytree(source, BUILD / "src")
    config = BUILD / "src/config.h"
    old = config.read_text()
    assert old.count("#define __MAX_ID__ 65710") == 1
    assert old.count("#define __MAX_EQ__ 192315") == 1
    config.write_text(old.replace("#define __MAX_ID__ 65710",
                                  "#define __MAX_ID__ 66040")
                         .replace("#define __MAX_EQ__ 192315",
                                  "#define __MAX_EQ__ 193000"))
    proc = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                          text=True, capture_output=True)
    (HERE / "build.stdout.txt").write_text(
        "\n".join(line.rstrip() for line in proc.stdout.splitlines()) + "\n")
    (HERE / "build.stderr.txt").write_text(proc.stderr)
    binary = BUILD / "wdsat_solver"
    assert proc.returncode == 0 and binary.exists(), proc.stderr[-2000:]
    receipt = {"proposal_id": "Q1516", "candidate_id": None,
               "parent_build_receipt_sha256": sha(PARENT / "build_receipt.json"),
               "source_sha256": sha(Path(__file__)),
               "config_sha256": sha(config), "binary_sha256": sha(binary),
               "binary_path": str(binary),
               "compiler": subprocess.check_output(["gcc", "--version"],
                                                   text=True).splitlines()[0],
               "architecture": platform.machine(),
               "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
               "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
               "return_code": proc.returncode}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                         sort_keys=True) + "\n")
    print("PASS Q1516 WDSat four-block capacity", sha(binary)[:12])


if __name__ == "__main__":
    main()
