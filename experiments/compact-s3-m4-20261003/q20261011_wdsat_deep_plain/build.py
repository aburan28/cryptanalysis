#!/usr/bin/env python3
"""Build width-four plain WDSat with a million-branch checkpoint cap."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"
UPSTREAM = Path("/private/tmp/wdsat-q1458")
BUILD = Path("/Volumes/SSD990/llm/tmp/q1466_wdsat_build")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("q1464_build_for_q1466", Q1464 / "build.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    freeze_path = HERE / "freeze.json"
    freeze = json.loads(freeze_path.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    q1464_build_path = Q1464 / "build_receipt.json"
    q1464_build = json.loads(q1464_build_path.read_text())
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["q1464_build_source_sha256"] == sha(Q1464 / "build.py")
    assert freeze["q1464_build_receipt_sha256"] == sha(q1464_build_path)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == freeze["upstream_commit"] == protocol["solver"]["upstream_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=UPSTREAM).strip()
    cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert cap == 1 << 20
    BUILD.mkdir()
    output = {"proposal_id": "Q1466", "candidate_id": None,
              "freeze_sha256": sha(freeze_path), "upstream_commit": commit,
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "per_degree": {}}
    for name in ("n53", "n83"):
        destination = BUILD / name
        source = destination / "src"
        shutil.copytree(UPSTREAM / "src", source)
        caps = q1464_build["per_degree"][name]["config"]
        config = source / "config.h"
        config.write_text("/* Q1466 Q1464 width-four caps and deeper branch stop. */\n" +
                          "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
        storage = prior.patch_quadratic_undo_storage(source)
        markers = prior.instrument_search(source)
        work = prior.patch_branch_work(source, cap)
        make = subprocess.run(["make", "-f", "makefile"], cwd=source,
                              capture_output=True, text=True)
        (HERE / f"build_{name}.stdout.txt").write_text(make.stdout)
        (HERE / f"build_{name}.stderr.txt").write_text(make.stderr)
        binary = destination / "wdsat_solver"
        output["per_degree"][name] = {
            "config": caps, "config_sha256": sha(config),
            "storage_patch": storage, "search_markers": markers,
            "branch_patch": work, "source_tree_sha256": prior.tree_sha(source),
            "return_code": make.returncode,
            "binary_path": str(binary) if binary.exists() else None,
            "binary_sha256": sha(binary) if binary.exists() else None,
            "build_stdout_sha256": sha(HERE / f"build_{name}.stdout.txt"),
            "build_stderr_sha256": sha(HERE / f"build_{name}.stderr.txt")}
        assert make.returncode == 0 and binary.exists(), make.stderr[-2000:]
        print(name, "built", output["per_degree"][name]["binary_sha256"][:12])
    (HERE / "build_receipt.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
