#!/usr/bin/env python3
"""Move an S3 root discriminator early and optionally force its exact root."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1485 = HERE.parent / "q20261011_n83_common_bit_probe"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1489_root_domain_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def patch(source: Path, priority: list[int], discriminator: int) -> str:
    assert len(priority) == len(set(priority)) == 335
    assert priority == list(range(2, 334)) + [417 + discriminator, 2140, 2141]
    path = source / "wdsat.c"
    data = path.read_text()
    order = ("static const int_t q1489_pair_rootfirst[] = {" +
             ", ".join(map(str, priority)) + "};\n")
    data = replace_once(data, "static unsigned char q1469_seen[__ID_SIZE__];",
                        order + "static unsigned char q1469_seen[__ID_SIZE__];")
    order_anchor = '''    if (mode && strcmp(mode, "q1478_leafpair_first") == 0) {'''
    order_case = '''    if (mode && strcmp(mode, "q1489_pair_rootfirst") == 0) {
        priority = q1489_pair_rootfirst;
        length = sizeof(q1489_pair_rootfirst) / sizeof(q1489_pair_rootfirst[0]);
    } else
'''
    data = replace_once(data, order_anchor, order_case + order_anchor)
    helper_anchor = "static void q1464_tick(int_t count) {"
    helper = f'''/* Q1489: exact root-domain propagation for one verified leaf pair. */
static int q1489_domain_mode = -1;
static unsigned long long q1489_checks = 0, q1489_bit_tests = 0;
static unsigned long long q1489_forced = 0, q1489_failed = 0;
static unsigned long long q1489_depth = 0, q1489_max_depth = 0;
static void q1489_load_mode(void) {{
    if (q1489_domain_mode >= 0) return;
    const char *raw = getenv("Q1489_DOMAIN");
    if (!raw || (strcmp(raw, "0") && strcmp(raw, "1"))) {{
        fprintf(stderr, "Q1489_BAD_MODE\\n"); fflush(stderr); exit(64);
    }}
    q1489_domain_mode = raw[0] - '0';
    fprintf(stderr, "Q1489_DOMAIN %d\\n", q1489_domain_mode);
    fflush(stderr);
}}
static int_t q1489_next_root_literal(void) {{
    ++q1489_checks;
    q1489_load_mode();
    if (!q1489_domain_mode) return 0;
    for (int i = 0; i < 10; ++i) {{
        ++q1489_bit_tests;
        if (!_cnf_is_true(q1483_positive[i])) return 0;
    }}
    for (int i = 0; i < 166; ++i) {{
        int_t var = 168 + i;
        ++q1489_bit_tests;
        if (_cnf_is_undef(var)) return 0;
        ++q1489_bit_tests;
        if ((_cnf_is_true(var) ? '1' : '0') != q1483_pair_bits[i]) return 0;
    }}
    const int_t discriminator = {417 + discriminator};
    if (_cnf_is_undef(discriminator)) return 0;
    int chosen = (_cnf_is_true(discriminator) ==
                  (q1483_root_bits[0][{discriminator}] == '1')) ? 0 : 1;
    for (int i = 0; i < 83; ++i) {{
        int_t var = 417 + i;
        ++q1489_bit_tests;
        if (_cnf_is_undef(var))
            return q1483_root_bits[chosen][i] == '1' ? var : -var;
    }}
    return 0;
}}

'''
    data = replace_once(data, helper_anchor, helper + helper_anchor)
    summary_anchor = '        fprintf(stderr, "Q1485_COMMON %lld %llu %llu %llu %llu %llu\\n",'
    summary = (
        '        fprintf(stderr, "Q1489_ROOT_DOMAIN %lld %llu %llu %llu %llu %llu\\n",\n'
        '                (long long)count, q1489_checks, q1489_bit_tests,\n'
        '                q1489_forced, q1489_failed, q1489_max_depth);\n'
    )
    data = replace_once(data, summary_anchor, summary + summary_anchor)
    end_anchor = '''    if (q1482_reject_rootless()) return false;
    if (q1483_reject_unsupported()) return false;
    return true;
}

bool wdsat_set_unitary(void) {'''
    replacement = '''    if (q1482_reject_rootless()) return false;
    if (q1483_reject_unsupported()) return false;
    int_t q1489_literal = q1489_next_root_literal();
    if (q1489_literal) {
        ++q1489_forced;
        ++q1489_depth;
        if (q1489_depth > q1489_max_depth) q1489_max_depth = q1489_depth;
        bool q1489_ok = wdsat_set_true(q1489_literal);
        --q1489_depth;
        if (!q1489_ok) { ++q1489_failed; return false; }
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
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"] == parent[
        "patched_wdsat_c_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    modified = patch(BUILD / "src", frozen["priority"],
                     frozen["root_discriminator_bit"])
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    receipt = {
        "proposal_id": "Q1489", "candidate_id": None,
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
    print("Q1489 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
