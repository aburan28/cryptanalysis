#!/usr/bin/env python3
"""Build pinned WDSat with deterministic left-branch work checkpoints."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
UPSTREAM = Path("/private/tmp/wdsat-q1458")
BUILD = Path("/private/tmp/q1464_wdsat_build")
sys.path.insert(0, str(PARENT / "q20261011_wdsat_bridge"))
from build import instrument_search, patch_quadratic_undo_storage  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_branch_work(source: Path, cap: int) -> dict:
    path = source / "wdsat.c"
    content = path.read_text()
    anchor = "static int_t set[__ID_SIZE__];\n"
    assert content.count(anchor) == 1
    helper = f"""

/* Q1464: count the upstream search's left-branch attempts. */
static void q1464_tick(int_t count) {{
    static long long next_checkpoint = 1;
    if (count == next_checkpoint) {{
        fprintf(stderr, "Q1464_BRANCH %lld\\n", (long long)count);
        fflush(stderr);
        next_checkpoint *= 2;
    }}
    if (count >= {cap}) {{
        fprintf(stderr, "Q1464_BRANCH_CAP %lld\\n", (long long)count);
        fflush(stderr);
        exit(42);
    }}
}}
"""
    content = content.replace(anchor, anchor + helper)
    site = "conf[0]++;"
    assert content.count(site) == 4
    content = content.replace(site, "conf[0]++; q1464_tick(conf[0]);")
    assert content.count("q1464_tick(conf[0]);") == 4
    path.write_text(content)
    return {"patch_kind": "four_left_branch_sites_power_of_two_checkpoints_fixed_cap",
            "branch_cap": cap, "instrumented_sites": 4,
            "wdsat_c_sha256": sha(path)}


def tree_sha(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in (".c", ".h") or path.name == "makefile":
            digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    freeze_path = HERE / "freeze.json"
    freeze = json.loads(freeze_path.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_path = PARENT / "q20261011_wdsat_shared_prefix/build_receipt.json"
    parent = json.loads(parent_path.read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["parent_build_receipt_sha256"] == sha(parent_path)
    assert freeze["shared_patch_source_sha256"] == sha(PARENT / "q20261011_wdsat_bridge/build.py")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == freeze["upstream_commit"] == protocol["solver"]["upstream_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"],
                                       cwd=UPSTREAM).strip()
    cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert cap > 0 and cap & (cap - 1) == 0
    BUILD.mkdir()
    output = {"proposal_id": "Q1464", "candidate_id": None,
              "freeze_sha256": sha(freeze_path), "upstream_commit": commit,
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "per_degree": {}}
    for name in ("n53", "n83"):
        destination = BUILD / name
        source = destination / "src"
        shutil.copytree(UPSTREAM / "src", source)
        caps = parent["per_degree"][name]["config"]
        config = source / "config.h"
        config.write_text("/* Q1464 exact Q1460/Q1463 width-four input caps. */\n" +
                          "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
        storage = patch_quadratic_undo_storage(source)
        markers = instrument_search(source)
        work = patch_branch_work(source, cap)
        make = subprocess.run(["make", "-f", "makefile"], cwd=source,
                              capture_output=True, text=True)
        (HERE / f"build_{name}.stdout.txt").write_text(make.stdout)
        (HERE / f"build_{name}.stderr.txt").write_text(make.stderr)
        binary = destination / "wdsat_solver"
        output["per_degree"][name] = {
            "config": caps, "config_sha256": sha(config),
            "storage_patch": storage, "search_markers": markers,
            "branch_patch": work, "source_tree_sha256": tree_sha(source),
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
