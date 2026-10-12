#!/usr/bin/env python3
"""Add exact two-root middle support for one pinned leaf pair in WDSat."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1482 = PARENT / "q20261011_n83_rootless_nogood"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1483_two_root_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bit_string(value: int, n: int) -> str:
    assert 0 <= value < 1 << n
    return "".join("1" if value >> i & 1 else "0" for i in range(n))


def patch(source: Path, leaf_bits: str, roots: list[int]) -> str:
    assert len(leaf_bits) == 166 and set(leaf_bits) <= {"0", "1"}
    assert len(roots) == 2 and roots[0] != roots[1]
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static void q1464_tick(int_t count) {"
    assert data.count(anchor) == 1
    positive = [168 + i for i, bit in enumerate(leaf_bits) if bit == "1"]
    assert len(positive) == 10
    root_bits = [bit_string(value, 83) for value in roots]
    method = f'''
/* Q1483: exact support for one pair's two S3 middle-coordinate roots. */
static const char q1483_pair_bits[167] = "{leaf_bits}";
static const char q1483_root_bits[2][84] = {{"{root_bits[0]}", "{root_bits[1]}"}};
static const int_t q1483_positive[10] = {{{", ".join(map(str, positive))}}};
static unsigned long long q1483_checks = 0, q1483_bit_tests = 0;
static unsigned long long q1483_pair_matches = 0, q1483_rejections = 0;
static bool q1483_reject_unsupported(void) {{
    ++q1483_checks;
    for (int i = 0; i < 10; ++i) {{
        ++q1483_bit_tests;
        if (!_cnf_is_true(q1483_positive[i])) return false;
    }}
    for (int i = 0; i < 166; ++i) {{
        int_t var = 168 + i;
        ++q1483_bit_tests;
        if (_cnf_is_undef(var)) return false;
        ++q1483_bit_tests;
        if ((_cnf_is_true(var) ? '1' : '0') != q1483_pair_bits[i]) return false;
    }}
    ++q1483_pair_matches;
    bool compatible[2] = {{true, true}};
    for (int i = 0; i < 83; ++i) {{
        int_t var = 417 + i;
        ++q1483_bit_tests;
        if (_cnf_is_undef(var)) continue;
        char assigned = _cnf_is_true(var) ? '1' : '0';
        ++q1483_bit_tests;
        for (int root = 0; root < 2; ++root)
            if (assigned != q1483_root_bits[root][i]) compatible[root] = false;
        if (!compatible[0] && !compatible[1]) {{
            ++q1483_rejections;
            return true;
        }}
    }}
    return false;
}}

'''
    data = data.replace(anchor, method + anchor)
    print_anchor = '''        fprintf(stderr, "Q1482_NOGOOD %lld %llu %llu %llu\\n",'''
    assert data.count(print_anchor) == 1
    summary = '''        fprintf(stderr, "Q1483_SUPPORT %lld %llu %llu %llu %llu\\n",
                (long long)count, q1483_checks, q1483_bit_tests,
                q1483_pair_matches, q1483_rejections);
'''
    data = data.replace(print_anchor, summary + print_anchor)
    return_anchor = '''    if (q1482_reject_rootless()) return false;
    return true;
}

bool wdsat_set_unitary(void) {'''
    assert data.count(return_anchor) == 1
    data = data.replace(return_anchor,
                        '''    if (q1482_reject_rootless()) return false;
    if (q1483_reject_unsupported()) return false;
    return true;
}

bool wdsat_set_unitary(void) {''')
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1482 / "build_receipt.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["q1482_build_sha256"] == sha(Q1482 / "build_receipt.json")
    src = Path(frozen["parent_source_dir"])
    assert sha(src / "wdsat.c") == frozen["parent_wdsat_c_sha256"] == parent[
        "patched_wdsat_c_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(src, BUILD / "src")
    modified = patch(BUILD / "src", frozen["supported_pair1_bits"],
                     frozen["supported_middle_root_coords"])
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    receipt = {"proposal_id": "Q1483", "candidate_id": None,
               "freeze_sha256": sha(HERE / "freeze.json"),
               "q1482_build_sha256": sha(Q1482 / "build_receipt.json"),
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
    print("Q1483 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
