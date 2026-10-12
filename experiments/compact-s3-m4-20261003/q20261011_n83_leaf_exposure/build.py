#!/usr/bin/env python3
"""Patch the pinned Q1473 native-XOR solver for leaf-exposure counters."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1478_leaf_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static unsigned char q1469_seen[__ID_SIZE__];"
    assert data.count(anchor) == 1
    values = [*range(2, 168), 2140, 2141]
    priority = ("static const int_t q1478_leafpair_first[] = {" +
                ", ".join(map(str, values)) + "};\n")
    data = data.replace(anchor, priority + anchor)
    order_anchor = '''    if (mode && strcmp(mode, "selector_pair_mids") == 0) {'''
    assert data.count(order_anchor) == 1
    order = '''    if (mode && strcmp(mode, "q1478_leafpair_first") == 0) {
        priority = q1478_leafpair_first;
        length = sizeof(q1478_leafpair_first) / sizeof(q1478_leafpair_first[0]);
    } else
'''
    data = data.replace(order_anchor, order + order_anchor)
    tick_anchor = "static void q1464_tick(int_t count) {"
    assert data.count(tick_anchor) == 1
    probe = r'''
/* Count branch snapshots where an exact S3 pair-root query can fire. */
static unsigned long long q1478_pair0 = 0, q1478_pair1 = 0;
static unsigned long long q1478_early0 = 0, q1478_early1 = 0;
static unsigned long long q1478_both = 0;
static bool q1478_full(int_t first, int_t length) {
    for (int_t v = first; v < first + length; ++v)
        if (_cnf_is_undef(v)) return false;
    return true;
}
static void q1478_snapshot(void) {
    const bool p0 = q1478_full(2, 166);
    const bool p1 = q1478_full(168, 166);
    if (p0) {
        ++q1478_pair0;
        if (!q1478_full(334, 83)) ++q1478_early0;
    }
    if (p1) {
        ++q1478_pair1;
        if (!q1478_full(417, 83)) ++q1478_early1;
    }
    if (p0 && p1) ++q1478_both;
}

'''
    data = data.replace(tick_anchor, probe + tick_anchor)
    counter_anchor = "    static long long next_checkpoint = 1;\n"
    assert data.count(counter_anchor) == 1
    data = data.replace(counter_anchor, counter_anchor + "    q1478_snapshot();\n")
    print_anchor = '''        fprintf(stderr, "Q1464_BRANCH %lld\\n", (long long)count);'''
    assert data.count(print_anchor) == 1
    summary = '''        fprintf(stderr, "Q1478_READY %lld %llu %llu %llu %llu %llu\\n",
                (long long)count, q1478_pair0, q1478_pair1,
                q1478_early0, q1478_early1, q1478_both);
'''
    data = data.replace(print_anchor, summary + print_anchor)
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    prior = json.loads((Q1473 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1473_build_sha256"] == sha(Q1473 / "build_receipt.json")
    src = Path(frozen["parent_source_dir"])
    assert sha(src / "wdsat.c") == frozen["parent_wdsat_c_sha256"] == prior[
        "selector_patch"]["wdsat_c_sha256"]
    assert sha(src / "config.h") == frozen["parent_config_sha256"] == prior[
        "config_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(src, BUILD / "src")
    modified = patch(BUILD / "src")
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    receipt = {
        "proposal_id": "Q1478", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "q1473_build_sha256": sha(Q1473 / "build_receipt.json"),
        "parent_source_wdsat_c_sha256": frozen["parent_wdsat_c_sha256"],
        "patched_wdsat_c_sha256": modified,
        "patched_source_path": str(BUILD / "src/wdsat.c"),
        "config_sha256": sha(BUILD / "src/config.h"),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "compiler": subprocess.check_output(["gcc", "--version"],
                                               text=True).splitlines()[0],
        "architecture": platform.machine(), "os": platform.platform(),
        "return_code": process.returncode,
        "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
        "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
        "source_sha256": sha(Path(__file__))}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1478 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
