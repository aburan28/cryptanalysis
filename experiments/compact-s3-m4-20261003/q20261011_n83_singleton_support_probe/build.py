#!/usr/bin/env python3
"""Instrument the Q1483 support check without changing its decisions."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1483 = HERE.parent / "q20261011_n83_two_root_support"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1484_singleton_build/n83")


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
    method = replace_once(method, "    bool compatible[2] = {true, true};",
                          "    int q1484_undefined = 0;\n"
                          "    bool compatible[2] = {true, true};")
    method = replace_once(method, "        if (_cnf_is_undef(var)) continue;",
                          "        if (_cnf_is_undef(var)) {\n"
                          "            ++q1484_undefined;\n"
                          "            continue;\n"
                          "        }")
    method = replace_once(method, "    return false;\n}\n\n",
                          "    if (compatible[0] && compatible[1]) {\n"
                          "        ++q1484_both;\n"
                          "    } else {\n"
                          "        ++q1484_one;\n"
                          "        q1484_one_undefined_sum += q1484_undefined;\n"
                          "        if (q1484_undefined) ++q1484_one_undefined;\n"
                          "        if (q1484_undefined < q1484_one_undefined_min)\n"
                          "            q1484_one_undefined_min = q1484_undefined;\n"
                          "        if (q1484_undefined > q1484_one_undefined_max)\n"
                          "            q1484_one_undefined_max = q1484_undefined;\n"
                          "    }\n"
                          "    return false;\n}\n\n")
    counters = (
        "/* Q1484: compatibility multiplicity and remaining middle bits. */\n"
        "static unsigned long long q1484_both = 0, q1484_one = 0;\n"
        "static unsigned long long q1484_one_undefined = 0;\n"
        "static unsigned long long q1484_one_undefined_sum = 0;\n"
        "static unsigned long long q1484_one_undefined_min = 83;\n"
        "static unsigned long long q1484_one_undefined_max = 0;\n"
    )
    data = data[:start] + counters + method + data[end:]
    anchor = '        fprintf(stderr, "Q1483_SUPPORT %lld %llu %llu %llu %llu\\n",'
    summary = (
        '        fprintf(stderr, "Q1484_SINGLETON %lld %llu %llu %llu %llu %llu %llu\\n",\n'
        '                (long long)count, q1484_both, q1484_one,\n'
        '                q1484_one_undefined, q1484_one_undefined_sum,\n'
        '                q1484_one_undefined_min, q1484_one_undefined_max);\n'
    )
    data = replace_once(data, anchor, summary + anchor)
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1483 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1483_build_sha256"] == sha(Q1483 / "build_receipt.json")
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
        "proposal_id": "Q1484", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "q1483_build_sha256": sha(Q1483 / "build_receipt.json"),
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
    print("Q1484 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
