#!/usr/bin/env python3
"""Rebuild Q1472 WDSat with a direct two-leaf raw-x branch prefix."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PRIOR = json.loads((PARENT / "q20261011_wdsat_phase_restart/build_receipt.json").read_text())
PRIOR_SOURCE = Path(PRIOR["binary_path"]).parent / "src"
BUILD = HERE / "build"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = BUILD / "src"
    assert not source.exists()
    assert sha(PRIOR_SOURCE / "wdsat.c") == PRIOR["phase_patch"]["wdsat_c_sha256"]
    assert sha(Path(PRIOR["binary_path"])) == PRIOR["binary_sha256"]
    shutil.copytree(PRIOR_SOURCE, source)
    path = source / "wdsat.c"
    text = path.read_text()
    raw0 = list(range(2, 85))
    raw1 = list(range(18174, 18257))
    priority = [x for pair in zip(raw0, raw1) for x in pair]
    pattern = r"static const int_t q1469_selector_leaf_interleave\[\] = \{[^}]*\};"
    replacement = ("static const int_t q1469_selector_leaf_interleave[] = {" +
                   ", ".join(map(str, priority)) + "};")
    text, count = re.subn(pattern, replacement, text)
    assert count == 1
    text = text.replace('strcmp(mode, "selector_leaf_interleave")',
                        'strcmp(mode, "direct_raw_interleave")')
    assert 'strcmp(mode, "direct_raw_interleave")' in text
    path.write_text(text)
    proc = subprocess.run(["make", "-f", "makefile"], cwd=source,
                          capture_output=True, text=True, check=False)
    (HERE / "build.stdout.txt").write_text(proc.stdout)
    (HERE / "build.stderr.txt").write_text(proc.stderr)
    binary = BUILD / "wdsat_solver"
    assert proc.returncode == 0 and binary.exists(), proc.stderr[-1000:]
    result = {"proposal_id": "Q1514", "binary_path": str(binary),
              "binary_sha256": sha(binary), "prior_binary_sha256": PRIOR["binary_sha256"],
              "prior_wdsat_c_sha256": PRIOR["phase_patch"]["wdsat_c_sha256"],
              "direct_wdsat_c_sha256": sha(path), "config_sha256": sha(source / "config.h"),
              "branch_prefix_variable_ids": priority, "branch_mode": "direct_raw_interleave",
              "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
              "build_stderr_sha256": sha(HERE / "build.stderr.txt")}
    (HERE / "build_direct_receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"binary_sha256": result["binary_sha256"],
                      "prefix_len": len(priority), "return_code": proc.returncode}))


if __name__ == "__main__":
    main()
