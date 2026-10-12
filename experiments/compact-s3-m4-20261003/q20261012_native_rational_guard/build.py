#!/usr/bin/env python3
"""Freeze and build an exact native N83 rationality conflict in WDSat."""
from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1491 = PARENT / "q20261012_n83_mask_density"
Q1494 = PARENT / "q20261012_n83_pair_base_audit"
Q1495 = PARENT / "q20261012_exact_rationality_filter"
NATIVE = PARENT.parent / "koblitz-pair-claw-20260929/native_n83_pairs.cpp"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1496_native_guard_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = load(HERE / "protocol.json")
    parent = load(Q1491 / "build_receipt.json")
    prior = load(Q1491 / "freeze.json")
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_source_sha256"]
    assert protocol["phases"] == list(range(41, 49))
    assert all(prior["mask_schedule"][str(i)]["flip_count"] == 249
               for i in protocol["phases"])
    for name in ("selected", "holdout"):
        assert prior["inputs"][name]["workload_id"] == protocol[
            f"{name}_workload_id"]
    copied = (HERE / "native_n83_pairs.cpp").read_text()
    old = '#include "../../ecc2k130/runner/generated/eccF83.h"'
    assert NATIVE.read_text().replace(old, '#include "eccF83.h"') == copied
    save(HERE / "freeze.json", {
        "proposal_id": "Q1496", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "build.py", "run.py",
                          "validate.py", "n83_guard.cpp",
                          "native_n83_pairs.cpp", "eccF83.h")},
        "q1491_build_receipt_sha256": sha(Q1491 / "build_receipt.json"),
        "q1491_freeze_sha256": sha(Q1491 / "freeze.json"),
        "q1494_result_sha256": sha(Q1494 / "result.json"),
        "q1495_result_sha256": sha(Q1495 / "result.json"),
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "original_native_source_sha256": sha(NATIVE),
        "inputs": prior["inputs"],
        "mask_schedule": {str(i): prior["mask_schedule"][str(i)]
                          for i in protocol["phases"]},
        "baseline_selected_receipts_sha256": {str(i): sha(
            Q1491 / "runs" / f"selected_phase{i}" / "receipt.json")
            for i in protocol["phases"]},
    })
    print("Q1496 frozen", sha(HERE / "freeze.json")[:12])


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def patch_c(path: Path) -> str:
    data = path.read_text()
    anchor = "static void q1464_tick(int_t count) {"
    guard = r'''
extern int q1496_pair_usable(unsigned long long, unsigned long long,
                             unsigned long long, unsigned long long);
static unsigned long long q1496_complete_checks = 0;
static unsigned long long q1496_rejections = 0;
static unsigned long long q1496_accepted_checks = 0;
static int q1496_reject_unusable(void) {
    if (!q1478_full(168, 166)) return 0;
    unsigned long long lo[2] = {0, 0}, hi[2] = {0, 0};
    for (int leaf = 0; leaf < 2; ++leaf)
        for (int bit = 0; bit < 83; ++bit)
            if (_cnf_is_true(168 + leaf * 83 + bit)) {
                if (bit < 64) lo[leaf] |= 1ULL << bit;
                else hi[leaf] |= 1ULL << (bit - 64);
            }
    ++q1496_complete_checks;
    int usable = q1496_pair_usable(lo[0], hi[0], lo[1], hi[1]);
    if (usable < 0) {
        fprintf(stderr, "Q1496_NATIVE_FAILURE\n"); fflush(stderr); exit(65);
    }
    if (!usable) { ++q1496_rejections; return 1; }
    ++q1496_accepted_checks;
    fprintf(stderr, "Q1496_PAIR_ACCEPTED %llu %llu %llu\n",
            q1496_complete_checks, q1496_rejections,
            q1496_accepted_checks);
    fflush(stderr);
    return 0;
}

'''
    data = replace_once(data, anchor, guard + anchor)
    summary = '''        fprintf(stderr, "Q1496_GUARD %lld %llu %llu %llu\\n",
                (long long)count, q1496_complete_checks,
                q1496_rejections, q1496_accepted_checks);
'''
    data = replace_once(data, '        fprintf(stderr, "Q1479_SUMMARY %lld %u %llu %llu\\n",',
                        summary + '        fprintf(stderr, "Q1479_SUMMARY %lld %u %llu %llu\\n",')
    cap = '''    if (count >= 32768) {
        fprintf(stderr, "Q1496_BRANCH_CAP %lld\\n", (long long)count);
        fprintf(stderr, "Q1496_GUARD_FINAL %lld %llu %llu %llu\\n",
                (long long)count, q1496_complete_checks,
                q1496_rejections, q1496_accepted_checks);
        fflush(stderr);
        exit(43);
    }
'''
    data = replace_once(data, '    if (count >= 1048576) {',
                        cap + '    if (count >= 1048576) {')
    anchor = "\t}\n    return true;\n}\n\nbool wdsat_set_unitary(void) {"
    data = replace_once(data, anchor,
                        "\t}\n    if (q1496_reject_unusable()) return false;\n"
                        "    return true;\n}\n\nbool wdsat_set_unitary(void) {")
    anchor = "\t}\n\treturn true;\n}\n\nbool wdsat_solve_rest(int_t l, int_t set_end, int_t conf[]) {"
    data = replace_once(data, anchor,
                        "\t}\n\tif (q1496_reject_unusable()) return false;\n"
                        "\treturn true;\n}\n\nbool wdsat_solve_rest(int_t l, int_t set_end, int_t conf[]) {")
    path.write_text(data)
    return sha(path)


def patch_makefile(path: Path) -> str:
    data = path.read_text()
    data = replace_once(data, "../wdsat_solver: $(OBJ_GEN)\n\t$(CC) $^ -o $@ $(LDFLAGS) -lm",
                        "../wdsat_solver: $(OBJ_GEN) n83_guard.o\n"
                        "\tg++ $^ -o $@ $(LDFLAGS) -lm\n\n"
                        "n83_guard.o: n83_guard.cpp native_n83_pairs.cpp eccF83.h\n"
                        "\tg++ -O3 -std=c++17 -c n83_guard.cpp -o n83_guard.o")
    path.write_text(data)
    return sha(path)


def build() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = load(HERE / "freeze.json")
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    for name in ("n83_guard.cpp", "native_n83_pairs.cpp", "eccF83.h"):
        shutil.copyfile(HERE / name, BUILD / "src" / name)
    modified = patch_c(BUILD / "src/wdsat.c")
    makefile = patch_makefile(BUILD / "src/makefile")
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    test = subprocess.run(["g++", "-O2", "-std=c++17",
                           "-DQ1496_TEST_MAIN", str(HERE / "n83_guard.cpp"),
                           "-o", str(BUILD / "guard_selftest")],
                          capture_output=True, text=True)
    assert test.returncode == 0, test.stderr[-2000:]
    audit = load(Q1494 / "result.json")
    for row in audit["rows"]:
        a, b = (leaf["coords"] for leaf in row["leaves"])
        output = subprocess.check_output(
            [str(BUILD / "guard_selftest"), format(a, "x"), format(b, "x")],
            text=True).strip()
        assert output == str(int(row["both_usable"]))
    save(HERE / "build_receipt.json", {
        "proposal_id": "Q1496", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "patched_wdsat_c_sha256": modified,
        "patched_makefile_sha256": makefile,
        "patched_source_path": str(BUILD / "src/wdsat.c"),
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "guard_selftest_binary_path": str(BUILD / "guard_selftest"),
        "guard_selftest_binary_sha256": sha(BUILD / "guard_selftest"),
        "guard_selftest_q1494_pairs_checked": len(audit["rows"]),
        "config_sha256": sha(BUILD / "src/config.h"),
        "compiler": subprocess.check_output(["g++", "--version"],
                                             text=True).splitlines()[0],
        "architecture": platform.machine(), "os": platform.platform(),
        "return_code": process.returncode,
        "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
        "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
        "source_sha256": sha(Path(__file__)),
    })
    print("Q1496 built", sha(binary)[:12])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "build"):
        raise SystemExit("usage: build.py {freeze|build}")
    globals()[sys.argv[1]]()
