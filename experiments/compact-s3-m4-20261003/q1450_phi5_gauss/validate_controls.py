#!/usr/bin/env python3
"""Check that bounded Gaussian matrices activate on planted partial controls."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1448_torsion_phi5.build_formula import build, transformed_targets  # noqa: E402
from q1448_torsion_phi5.verify_model import replay  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402

OUTPUT = HERE / "controls.json"
MATRIX_FLAGS = ["--maxmatrixcols", "8192", "--maxmatrixrows", "512",
                "--maxnummatrices", "8", "--autodisablegauss", "0"]


def partial_formula(row: dict):
    n = row["degree_n"]
    if n == 53:
        formula, meta = build(n)
    else:
        formula, meta = build(n, [row["raw_target_x"]],
                              row["public_target"])
    onb = field.Onb(n)
    for bits, mask in zip(meta["leaf_x_variables"][:2],
                          row["raw_leaf_x"][:2]):
        pin_bits(formula, bits, mask)
    for bits, mask in zip(meta["leaf_phi_variables"][:2],
                          row["raw_leaf_x"][:2]):
        pin_bits(formula, bits,
                 transformed_targets(onb, [mask])[0])
    pin_bits(formula, meta["target_selector_variables"],
             row["target_selector_choice"])
    return formula, meta


def matrix_count(stdout: str) -> int:
    match = re.search(
        r"^c \[matrix\] Using (\d+) matrices recovered from ",
        stdout, re.M)
    assert match is not None
    count = int(match.group(1))
    assert count > 0
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent_path = PARENT / "q1449_phi5_native_xor/protocol.json"
    q1449_controls_path = PARENT / "q1449_phi5_native_xor/controls.json"
    validation_path = PARENT / "q1448_torsion_phi5/validation.json"
    parent = json.loads(parent_path.read_text())
    q1449_controls = json.loads(q1449_controls_path.read_text())
    validation = json.loads(validation_path.read_text())
    assert parent["proposal_id"] == "Q1449"
    assert q1449_controls["status"] == "pass"
    binary = shutil.which("cryptominisat5")
    assert binary is not None
    binary_path = Path(binary).resolve()
    assert sha(binary_path) == parent["cms_binary_sha256"]
    previous = json.loads(OUTPUT.read_text()) if args.check else None
    rows = []
    for row in validation["rows"]:
        n = row["degree_n"]
        formula, meta = partial_formula(row)
        raw = xcnf_bytes(formula)
        control_dir = HERE / "controls"
        stdout_path = control_dir / f"n{n}_partial.stdout.txt"
        stderr_path = control_dir / f"n{n}_partial.stderr.txt"
        if args.check:
            stdout = stdout_path.read_text()
            stderr = stderr_path.read_text()
            prior = next(item for item in previous["rows"]
                         if item["degree_n"] == n)
            code = prior["solver_exit_code"]
            assert sha(stdout_path) == prior["solver_stdout_sha256"]
            assert sha(stderr_path) == prior["solver_stderr_sha256"]
        else:
            if stdout_path.exists() or stderr_path.exists():
                raise FileExistsError(control_dir)
            control_dir.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"q1450-n{n}-") as directory:
                path = Path(directory) / "partial.xcnf"
                path.write_bytes(raw)
                command = [str(binary_path), "--verb", "1", "--threads", "1",
                           "--maxtime", "5", "--maxconfl", "200000",
                           *MATRIX_FLAGS, str(path)]
                try:
                    result = subprocess.run(
                        command, capture_output=True, text=True,
                        timeout=15, check=False)
                    stdout, stderr, code = (result.stdout, result.stderr,
                                            result.returncode)
                except subprocess.TimeoutExpired as error:
                    stdout = (error.stdout or b"").decode(errors="replace")
                    stderr = (error.stderr or b"").decode(errors="replace")
                    code = None
                if code == 10:
                    model_path = Path(directory) / "model.txt"
                    model_path.write_text(stdout)
                    replay(formula, meta, model_path,
                           parent["cells"][str(n)]["instance"])
            stdout_path.write_text(stdout)
            stderr_path.write_text(stderr)
        rows.append({
            "degree_n": n, "curve_id": row["curve_id"],
            "control_law": row["control_law"],
            "known_witness_leaf_x": row["raw_leaf_x"],
            "pinned_leaf_count": 2,
            "target_selector_pinned": True,
            "xcnf_sha256": sha_bytes(raw),
            "xcnf_variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "native_xor_rows": len(formula.xors),
            "gaussian_matrices_used": matrix_count(stdout),
            "solver_exit_code": code,
            "solver_status": ("external_timeout" if code is None else
                              "sat" if code == 10 else
                              "indeterminate" if code == 15 and
                              "s INDETERMINATE" in stdout else "error"),
            "solver_stdout_sha256": sha(stdout_path),
            "solver_stderr_sha256": sha(stderr_path),
            "is_ordinary_unpinned_measurement": False,
        })
    result = {
        "kind": "q1450_bounded_gauss_partial_controls",
        "proposal_id": "Q1450", "candidate_id": None,
        "isogeny": "none", "status": "pass", "rows": rows,
        "matrix_flags": MATRIX_FLAGS,
        "parent_q1449_protocol_sha256": sha(parent_path),
        "parent_q1449_controls_sha256": sha(q1449_controls_path),
        "q1448_validation_sha256": sha(validation_path),
        "cms_binary_sha256": sha(binary_path),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
    }
    if args.check:
        assert result == previous
        print("Q1450 bounded Gaussian N53/N83 partial controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print("Q1450 bounded Gaussian N53/N83 partial controls: PASS")


if __name__ == "__main__":
    main()
