#!/usr/bin/env python3
"""Compile width-three WDSat with Q1464's exact branch instrumentation."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1464 = PARENT / "q20261011_wdsat_workprobe"
UPSTREAM = Path("/private/tmp/wdsat-q1458")
BUILD = Path("/private/tmp/q1465_wdsat_build")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


q1460_build = load("q1460_build_for_q1465", Q1460 / "build.py")
q1464_build = load("q1464_build_for_q1465", Q1464 / "build.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    freeze_path = HERE / "freeze.json"
    freeze = json.loads(freeze_path.read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["prepare_receipt_sha256"] == sha(HERE / "prepare_receipt.json")
    assert freeze["q1464_build_source_sha256"] == sha(Q1464 / "build.py")
    assert freeze["q1460_build_source_sha256"] == sha(Q1460 / "build.py")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == freeze["upstream_commit"] == protocol["solver"]["upstream_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=UPSTREAM).strip()
    branch_cap = protocol["limits"]["left_branch_attempts_per_run"]
    BUILD.mkdir()
    output = {"proposal_id": "Q1465", "candidate_id": None,
              "freeze_sha256": sha(freeze_path), "upstream_commit": commit,
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "per_degree": {}}
    for name in ("n53", "n83"):
        inputs = []
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            archive = (HERE / f"{cell}.xcnf.gz").read_bytes()
            assert hashlib.sha256(archive).hexdigest() == prepared["cells"][cell]["derived_archive_sha256"]
            inputs.append(q1460_build.sizes(gzip.decompress(archive)))
        caps = {"MAX_ID": max(item["variables"] for item in inputs),
                "MAX_BUFFER_SIZE": max(max(item["cnf_occurrences"] + item["xor_occurrences"],
                                           item["cnf_implication_slots"]) for item in inputs) + 10000,
                "MAX_EQ": max(item["cnf_clauses"] + item["xor_rows"] for item in inputs) + 2,
                "MAX_EQ_SIZE": max(max(item["max_cnf_width"], item["max_xor_width"])
                                   for item in inputs) + 2,
                "MAX_XEQ": max(item["xor_rows"] for item in inputs) + 2,
                "MAX_XEQ_SIZE": max(item["max_xor_width"] for item in inputs) + 2}
        destination = BUILD / name
        source = destination / "src"
        shutil.copytree(UPSTREAM / "src", source)
        config = source / "config.h"
        config.write_text("/* Q1465 width-three CNF-XOR caps. */\n" +
                          "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
        storage = q1464_build.patch_quadratic_undo_storage(source)
        markers = q1464_build.instrument_search(source)
        branch = q1464_build.patch_branch_work(source, branch_cap)
        make = subprocess.run(["make", "-f", "makefile"], cwd=source,
                              capture_output=True, text=True)
        (HERE / f"build_{name}.stdout.txt").write_text(make.stdout)
        (HERE / f"build_{name}.stderr.txt").write_text(make.stderr)
        binary = destination / "wdsat_solver"
        output["per_degree"][name] = {
            "config": caps, "config_sha256": sha(config),
            "storage_patch": storage, "search_markers": markers,
            "branch_patch": branch, "source_tree_sha256": q1464_build.tree_sha(source),
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
