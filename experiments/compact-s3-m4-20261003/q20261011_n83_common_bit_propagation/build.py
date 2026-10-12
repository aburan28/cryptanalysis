#!/usr/bin/env python3
"""Propagate sound common-root literals through native WDSat inference."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1485 = HERE.parent / "q20261011_n83_common_bit_probe"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1486_common_propagation_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static void q1464_tick(int_t count) {"
    implication = '''/* Q1486: a literal shared by both exact S3 roots is mandatory. */
static unsigned long long q1486_checks = 0, q1486_bit_tests = 0;
static unsigned long long q1486_forced = 0, q1486_failed = 0;
static unsigned long long q1486_depth = 0, q1486_max_depth = 0;
static int_t q1486_next_common_literal(void) {
    ++q1486_checks;
    for (int i = 0; i < 10; ++i) {
        ++q1486_bit_tests;
        if (!_cnf_is_true(q1483_positive[i])) return 0;
    }
    for (int i = 0; i < 166; ++i) {
        int_t var = 168 + i;
        ++q1486_bit_tests;
        if (_cnf_is_undef(var)) return 0;
        ++q1486_bit_tests;
        if ((_cnf_is_true(var) ? '1' : '0') != q1483_pair_bits[i]) return 0;
    }
    for (int i = 0; i < 83; ++i) {
        int_t var = 417 + i;
        ++q1486_bit_tests;
        if (q1483_root_bits[0][i] == q1483_root_bits[1][i] &&
            _cnf_is_undef(var))
            return q1483_root_bits[0][i] == '1' ? var : -var;
    }
    return 0;
}

'''
    data = replace_once(data, anchor, implication + anchor)
    summary_anchor = '        fprintf(stderr, "Q1485_COMMON %lld %llu %llu %llu %llu %llu\\n",'
    summary = (
        '        fprintf(stderr, "Q1486_PROPAGATE %lld %llu %llu %llu %llu %llu\\n",\n'
        '                (long long)count, q1486_checks, q1486_bit_tests,\n'
        '                q1486_forced, q1486_failed, q1486_max_depth);\n'
    )
    data = replace_once(data, summary_anchor, summary + summary_anchor)
    end_anchor = '''    if (q1482_reject_rootless()) return false;
    if (q1483_reject_unsupported()) return false;
    return true;
}

bool wdsat_set_unitary(void) {'''
    replacement = '''    if (q1482_reject_rootless()) return false;
    if (q1483_reject_unsupported()) return false;
    int_t q1486_literal = q1486_next_common_literal();
    if (q1486_literal) {
        ++q1486_forced;
        ++q1486_depth;
        if (q1486_depth > q1486_max_depth) q1486_max_depth = q1486_depth;
        bool q1486_ok = wdsat_set_true(q1486_literal);
        --q1486_depth;
        if (!q1486_ok) { ++q1486_failed; return false; }
    }
    return true;
}

bool wdsat_set_unitary(void) {'''
    data = replace_once(data, end_anchor, replacement)
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1485 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1485_build_sha256"] == sha(Q1485 / "build_receipt.json")
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
        "proposal_id": "Q1486", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "q1485_build_sha256": sha(Q1485 / "build_receipt.json"),
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
    print("Q1486 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
