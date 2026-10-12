#!/usr/bin/env python3
"""Instrument unset common-root bits without changing solver decisions."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1484 = HERE.parent / "q20261011_n83_singleton_support_probe"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1485_common_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    start = data.index("static bool q1483_reject_unsupported(void) {")
    end = data.index("static void q1464_tick(int_t count) {", start)
    method = data[start:end]
    check = (
        "    ++q1483_pair_matches;\n"
        "    ++q1485_checks;\n"
        "    int q1485_unset = 0;\n"
        "    for (int i = 0; i < 83; ++i)\n"
        "        if (q1483_root_bits[0][i] == q1483_root_bits[1][i] &&\n"
        "            _cnf_is_undef(417 + i)) ++q1485_unset;\n"
        "    q1485_unset_sum += q1485_unset;\n"
        "    if (q1485_unset) ++q1485_available;\n"
        "    if (q1485_unset < q1485_unset_min) q1485_unset_min = q1485_unset;\n"
        "    if (q1485_unset > q1485_unset_max) q1485_unset_max = q1485_unset;"
    )
    method = replace_once(method, "    ++q1483_pair_matches;", check)
    counters = (
        "/* Q1485: unassigned implications shared by both exact roots. */\n"
        "static unsigned long long q1485_checks = 0, q1485_available = 0;\n"
        "static unsigned long long q1485_unset_sum = 0;\n"
        "static unsigned long long q1485_unset_min = 49, q1485_unset_max = 0;\n"
    )
    data = data[:start] + counters + method + data[end:]
    anchor = '        fprintf(stderr, "Q1484_SINGLETON %lld %llu %llu %llu %llu %llu %llu\\n",'
    summary = (
        '        fprintf(stderr, "Q1485_COMMON %lld %llu %llu %llu %llu %llu\\n",\n'
        '                (long long)count, q1485_checks, q1485_available,\n'
        '                q1485_unset_sum, q1485_unset_min, q1485_unset_max);\n'
    )
    data = replace_once(data, anchor, summary + anchor)
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1484 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1484_build_sha256"] == sha(Q1484 / "build_receipt.json")
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"] == parent[
        "patched_wdsat_c_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    modified = patch(BUILD / "src")
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    receipt = {
        "proposal_id": "Q1485", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "q1484_build_sha256": sha(Q1484 / "build_receipt.json"),
        "patched_wdsat_c_sha256": modified,
        "patched_source_path": str(BUILD / "src/wdsat.c"),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "config_sha256": sha(BUILD / "src/config.h"),
        "compiler": subprocess.check_output(["gcc", "--version"],
                                             text=True).splitlines()[0],
        "architecture": platform.machine(), "os": platform.platform(),
        "return_code": process.returncode,
        "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
        "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
        "source_sha256": sha(Path(__file__)),
    }
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1485 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
