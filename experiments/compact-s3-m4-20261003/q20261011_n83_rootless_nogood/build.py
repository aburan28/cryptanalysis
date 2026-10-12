#!/usr/bin/env python3
"""Add a mathematically checked rootless-pair conflict to pinned Q1481 WDSat."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q20261011_n83_leaf_masks"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1482_nogood_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(source: Path, bits: str) -> str:
    assert len(bits) == 166 and set(bits) <= {"0", "1"}
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static void q1464_tick(int_t count) {"
    assert data.count(anchor) == 1
    positive = [168 + i for i, bit in enumerate(bits) if bit == "1"]
    assert len(positive) == 10
    positive_array = ", ".join(map(str, positive))
    method = f'''
/* Q1482: exact S3-rootless pair-1 assignment; field proof in freeze. */
static const char q1482_rootless_bits[167] = "{bits}";
static const int_t q1482_positive[10] = {{{positive_array}}};
static unsigned long long q1482_checks = 0, q1482_bit_tests = 0;
static unsigned long long q1482_rejections = 0;
static bool q1482_reject_rootless(void) {{
    ++q1482_checks;
    for (int i = 0; i < 10; ++i) {{
        ++q1482_bit_tests;
        if (!_cnf_is_true(q1482_positive[i])) return false;
    }}
    for (int i = 0; i < 166; ++i) {{
        int_t var = 168 + i;
        ++q1482_bit_tests;
        if (_cnf_is_undef(var)) return false;
        ++q1482_bit_tests;
        if ((_cnf_is_true(var) ? '1' : '0') != q1482_rootless_bits[i])
            return false;
    }}
    ++q1482_rejections;
    return true;
}}

'''
    data = data.replace(anchor, method + anchor)
    print_anchor = '''        fprintf(stderr, "Q1479_SUMMARY %lld %u %llu %llu\\n",'''
    assert data.count(print_anchor) == 1
    summary = '''        fprintf(stderr, "Q1482_NOGOOD %lld %llu %llu %llu\\n",
                (long long)count, q1482_checks, q1482_bit_tests,
                q1482_rejections);
'''
    data = data.replace(print_anchor, summary + print_anchor)
    return_anchor = "\t}\n    return true;\n}\n\nbool wdsat_set_unitary(void) {"
    assert data.count(return_anchor) == 1
    data = data.replace(return_anchor,
                        "\t}\n    if (q1482_reject_rootless()) return false;\n"
                        "    return true;\n}\n\nbool wdsat_set_unitary(void) {")
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1481 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1481_build_sha256"] == sha(Q1481 / "build_receipt.json")
    src = Path(frozen["parent_source_dir"])
    assert sha(src / "wdsat.c") == frozen["parent_wdsat_c_sha256"] == parent[
        "patched_wdsat_c_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(src, BUILD / "src")
    modified = patch(BUILD / "src", frozen["rootless_pair1_bits"])
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    receipt = {"proposal_id": "Q1482", "candidate_id": None,
               "freeze_sha256": sha(HERE / "freeze.json"),
               "q1481_build_sha256": sha(Q1481 / "build_receipt.json"),
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
               "source_sha256": sha(Path(__file__))}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1482 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
