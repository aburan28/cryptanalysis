#!/usr/bin/env python3
"""Build a pinned, patched WDSat for one audited factored XCNF capacity."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from verify_factor_xcnf import cnf_lits, read_formula, xor_lits


UPSTREAM = "61c6ff3f49445af2729274819edb27b85a89efc1"
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(*command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, stderr=subprocess.STDOUT)


def build(source_repo, formula_path, outdir):
    assert not outdir.exists(), "refuse to overwrite build"
    actual = call("git", "-C", str(source_repo), "rev-parse", "HEAD").decode().strip()
    assert actual == UPSTREAM, (actual, UPSTREAM)
    nvars, rows = read_formula(formula_path)
    cnf_rows = [cnf_lits(row) for row in rows if not row.startswith("x")]
    xor_rows = [xor_lits(row) for row in rows if row.startswith("x")]
    assert cnf_rows and xor_rows
    assert max(map(len, cnf_rows)) <= 4
    outdir.mkdir(parents=True)
    names = call("git", "-C", str(source_repo), "ls-tree", "-r", "--name-only",
                 UPSTREAM, "src").decode().splitlines()
    assert "src/makefile" in names and "src/config.h" in names
    for name in names:
        assert name.startswith("src/") and ".." not in Path(name).parts
        path = outdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(call("git", "-C", str(source_repo), "show",
                              f"{UPSTREAM}:{name}"))
    patch_path = HERE / "wdsat_adapter.patch"
    subprocess.run(["patch", "-p1", "-i", str(patch_path)], cwd=outdir,
                   check=True, capture_output=True)
    buffer_size = 2000000
    (outdir / "src/config.h").write_text(
        "// Q1444 capacity generated from independently audited XCNF.\n"
        f"#define __MAX_ANF_ID__ 1\n"
        f"#define __MAX_DEGREE__ 4\n"
        f"#define __MAX_ID__ {nvars + 1}\n"
        f"#define __MAX_BUFFER_SIZE__ {buffer_size}\n"
        f"#define __MAX_EQ__ {len(cnf_rows) + 1}\n"
        f"#define __MAX_EQ_SIZE__ {max(map(len, cnf_rows)) + 1}\n"
        f"#define __MAX_XEQ__ {len(xor_rows) + 1}\n"
        f"#define __MAX_XEQ_SIZE__ {max(map(len, xor_rows)) + 1}\n",
        encoding="ascii")
    command = ["make", "-C", "src"]
    completed = subprocess.run(command, cwd=outdir, capture_output=True,
                               text=True)
    (outdir / "build.stdout.txt").write_text(completed.stdout)
    (outdir / "build.stderr.txt").write_text(completed.stderr)
    assert completed.returncode == 0, completed.stderr[-1000:]
    binary = outdir / "wdsat_solver"
    assert binary.is_file()
    receipt = {
        "status": "built",
        "upstream_commit": UPSTREAM,
        "patch_sha256": sha(patch_path),
        "formula_sha256": sha(formula_path),
        "source_variables": nvars,
        "cnf_rows": len(cnf_rows),
        "xor_rows": len(xor_rows),
        "max_cnf_clause_size": max(map(len, cnf_rows)),
        "max_xor_row_size": max(map(len, xor_rows)),
        "config_sha256": sha(outdir / "src/config.h"),
        "binary_sha256": sha(binary),
        "command": command,
    }
    (outdir / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                     sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.upstream, args.formula, args.outdir),
                     sort_keys=True))
