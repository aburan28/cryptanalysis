#!/usr/bin/env python3
"""Build an in-process first-pair enumerator from Q1509 WDSat."""
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1509 = HERE.parent / "q20261012_n83_pair_depth_sweep"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1517_inproc_pair")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


GATE = r'''/* Q1517: prune a complete first pair at its earliest search node. */
static char q1517_seen[8][167];
static unsigned q1517_count = 0;
static bool q1517_gate(int_t branch_count) {
    if (!q1478_full(168, 166)) return false;
    char bits[167];
    for (int i = 0; i < 166; ++i)
        bits[i] = _cnf_is_true(168 + i) ? '1' : '0';
    bits[166] = 0;
    for (unsigned i = 0; i < q1517_count; ++i)
        if (memcmp(q1517_seen[i], bits, 166) == 0) return true;
    if (!q1478_full(417, 83)) {
        memcpy(q1517_seen[q1517_count], bits, 167);
        ++q1517_count;
        fprintf(stderr, "Q1517_PAIR %u %lld %llu %llu %s\n", q1517_count,
                (long long)branch_count, q1473_cnf_calls, q1473_xor_calls, bits);
        fflush(stderr);
        if (q1517_count == 8) exit(47);
    }
    return true;
}

'''


def main():
    parent = json.loads((Q1509 / "build_receipt.json").read_text())
    source = Path(parent["binary_path"]).parent / "src"
    assert sha(source / "config.h") == parent["config_sha256"]
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    BUILD.mkdir()
    shutil.copytree(source, BUILD / "src")
    target = BUILD / "src/wdsat.c"
    old = target.read_text()
    anchor = "bool wdsat_solve_rest(int_t l, int_t set_end, int_t conf[]) {\n"
    assert old.count(anchor) == 1
    target.write_text(old.replace(anchor, GATE + anchor +
                                  "\tif(q1517_gate(conf[0])) return false;\n"))
    proc = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                          text=True, capture_output=True)
    (HERE / "build.stdout.txt").write_text(
        "\n".join(x.rstrip() for x in proc.stdout.splitlines()) + "\n")
    (HERE / "build.stderr.txt").write_text(proc.stderr)
    binary = BUILD / "wdsat_solver"
    assert proc.returncode == 0 and binary.exists(), proc.stderr[-2000:]
    receipt = {"proposal_id": "Q1517", "candidate_id": None,
               "parent_build_receipt_sha256": sha(Q1509 / "build_receipt.json"),
               "parent_wdsat_sha256": sha(source / "wdsat.c"),
               "builder_sha256": sha(Path(__file__)),
               "patched_wdsat_sha256": sha(target),
               "config_sha256": sha(BUILD / "src/config.h"),
               "binary_sha256": sha(binary), "binary_path": str(binary),
               "compiler": subprocess.check_output(["gcc", "--version"],
                                                   text=True).splitlines()[0],
               "architecture": platform.machine(),
               "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
               "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
               "return_code": proc.returncode}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                         sort_keys=True) + "\n")
    print("PASS Q1517 in-process pair build", sha(binary)[:12])


if __name__ == "__main__":
    main()
