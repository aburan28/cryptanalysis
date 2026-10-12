#!/usr/bin/env python3
"""Patch exact Q1473 WDSat to probe and undo both root selector signs."""
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
BUILD = Path("/Volumes/SSD990/llm/tmp/q1477_root_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(source: Path) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "bool wdsat_set_unitary(void) {"
    assert data.count(anchor) == 1
    probe = r'''
/* Q1477: one root lookahead per selector sign, with complete undo. */
static void q1477_probe_root(void) {
    if (set[0] != 2140 || !_cnf_is_undef(2140)) {
        fprintf(stderr, "Q1477_BAD_ROOT\n"); fflush(stderr); exit(64);
    }
    const int_t root_cnf = cnf_history_top;
    const int_t root_xor = xorset_history_top;
    const int_t literals[2] = {-2140, 2140};
    for (int i = 0; i < 2; ++i) {
        const unsigned long long old_cnf = q1473_cnf_calls;
        const unsigned long long old_xor = q1473_xor_calls;
        _cnf_breakpoint;
        _xorset_breakpoint;
        const bool ok = wdsat_set_true(literals[i]);
        const int_t cnf_assigned = cnf_history_top - root_cnf;
        const int_t xor_assigned = xorset_history_top - root_xor;
        const unsigned long long cnf_calls = q1473_cnf_calls - old_cnf;
        const unsigned long long xor_calls = q1473_xor_calls - old_xor;
        cnf_undo();
        xorset_undo();
        if (cnf_history_top != root_cnf || xorset_history_top != root_xor ||
            !_cnf_is_undef(2140) || !_xorset_is_undef(2140)) {
            fprintf(stderr, "Q1477_RESTORE_FAILURE\n"); fflush(stderr); exit(64);
        }
        fprintf(stderr, "Q1477_ROOT %lld %d %llu %llu %lld %lld\n",
                (long long)literals[i], (int)ok, cnf_calls, xor_calls,
                (long long)cnf_assigned, (long long)xor_assigned);
        fflush(stderr);
    }
    fprintf(stderr, "Q1477_ROOT_RESTORED %lld %lld\n",
            (long long)root_cnf, (long long)root_xor);
    fflush(stderr);
}

'''
    data = data.replace(anchor, probe + anchor)
    call = 'fprintf(stderr, "Q1458_SEARCH_START\\n"); fflush(stderr);'
    assert data.count(call) == 1
    data = data.replace(call, 'q1477_probe_root();\n\texit(43);\n\t' + call)
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
        "proposal_id": "Q1477", "candidate_id": None,
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
    print("Q1477 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
