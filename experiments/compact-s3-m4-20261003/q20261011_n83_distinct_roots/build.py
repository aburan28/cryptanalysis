#!/usr/bin/env python3
"""Capture first distinct oracle-eligible pair-1 leaves in Q1478 WDSat."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1478 = PARENT / "q20261011_n83_leaf_exposure"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1479_distinct_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static void q1478_snapshot(void) {"
    assert data.count(anchor) == 1
    capture = r'''
/* Capture at most 256 distinct complete pair-1 coordinate assignments. */
static char q1479_seen[256][167];
static unsigned short q1479_slots[1024];
static unsigned int q1479_count = 0;
static unsigned long long q1479_duplicate = 0, q1479_overcap = 0;
static bool q1479_capture_enabled = true;
static void q1479_capture_pair1(void) {
    if (!q1479_capture_enabled) return;
    char bits[167];
    unsigned long long hash = 1469598103934665603ULL;
    for (int i = 0; i < 166; ++i) {
        bits[i] = _cnf_is_true(168 + i) ? '1' : '0';
        hash = (hash ^ (unsigned char)bits[i]) * 1099511628211ULL;
    }
    bits[166] = 0;
    unsigned int slot = (unsigned int)hash & 1023U;
    while (q1479_slots[slot]) {
        if (memcmp(q1479_seen[q1479_slots[slot] - 1], bits, 166) == 0) {
            ++q1479_duplicate;
            return;
        }
        slot = (slot + 1U) & 1023U;
    }
    if (q1479_count == 256) {
        ++q1479_overcap;
        return;
    }
    memcpy(q1479_seen[q1479_count], bits, 167);
    q1479_slots[slot] = (unsigned short)(++q1479_count);
    fprintf(stderr, "Q1479_PAIR1 %u %s\n", q1479_count, bits);
    fflush(stderr);
}

'''
    data = data.replace(anchor, capture + anchor)
    old = '''        if (!q1478_full(417, 83)) ++q1478_early1;'''
    new = '''        if (!q1478_full(417, 83)) {
            ++q1478_early1;
            q1479_capture_pair1();
        }'''
    assert data.count(old) == 1
    data = data.replace(old, new)
    print_anchor = '''        fprintf(stderr, "Q1478_READY %lld %llu %llu %llu %llu %llu\\n",'''
    assert data.count(print_anchor) == 1
    summary = '''        fprintf(stderr, "Q1479_SUMMARY %lld %u %llu %llu\\n",
                (long long)count, q1479_count, q1479_duplicate, q1479_overcap);
'''
    data = data.replace(print_anchor, summary + print_anchor)
    tick = "    q1478_snapshot();\n"
    assert data.count(tick) == 1
    data = data.replace(tick, tick +
                        "    if (count >= 32768) q1479_capture_enabled = false;\n")
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    prior = json.loads((Q1478 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1478_build_sha256"] == sha(Q1478 / "build_receipt.json")
    src = Path(frozen["parent_source_dir"])
    assert sha(src / "wdsat.c") == frozen["parent_wdsat_c_sha256"] == prior[
        "patched_wdsat_c_sha256"]
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
    receipt = {"proposal_id": "Q1479", "candidate_id": None,
               "freeze_sha256": sha(HERE / "freeze.json"),
               "q1478_build_sha256": sha(Q1478 / "build_receipt.json"),
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
    print("Q1479 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
