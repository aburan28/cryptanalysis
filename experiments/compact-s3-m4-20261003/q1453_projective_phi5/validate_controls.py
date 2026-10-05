#!/usr/bin/env python3
"""Solve pinned Q1453 circuits and replay exact N53/N83 relations."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402
from q1453_projective_phi5.build_formula import build  # noqa: E402
from q1453_projective_phi5.verify_model import replay  # noqa: E402

OUTPUT = HERE / "controls.json"
MATRIX_FLAGS = ["--maxmatrixcols", "8192", "--maxmatrixrows", "512",
                "--maxnummatrices", "8", "--autodisablegauss", "0"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validation_path = PARENT / "q1448_torsion_phi5/validation.json"
    parent_path = PARENT / "q1452_known_satisfiable_phi5/protocol.json"
    n83_parent_path = PARENT / "q1451_phi5_fixed_target/protocol.json"
    algebra_path = HERE / "algebra_validation.json"
    validation = json.loads(validation_path.read_text())
    parent = json.loads(parent_path.read_text())
    n83_parent = json.loads(n83_parent_path.read_text())
    algebra = json.loads(algebra_path.read_text())
    assert parent["proposal_id"] == "Q1452"
    assert algebra["status"] == "pass"
    binary = shutil.which("cryptominisat5")
    assert binary is not None
    binary_path = Path(binary).resolve()
    assert sha(binary_path) == parent["cms_binary_sha256"]
    rows = []
    for row in validation["rows"]:
        n = row["degree_n"]
        if n == 53:
            formula, meta = build(n, target_index=201)
            assert meta["raw_target_x_values"] == [row["raw_target_x"]]
        else:
            formula, meta = build(
                n, raw_target_override=row["raw_target_x"],
                public_target_override=row["public_target"])
        for bits, mask in zip(meta["leaf_x_variables"], row["raw_leaf_x"]):
            pin_bits(formula, bits, mask)
        raw = xcnf_bytes(formula)
        with tempfile.TemporaryDirectory(prefix=f"q1453-n{n}-") as directory:
            xcnf_path = Path(directory) / "control.xcnf"
            model_path = Path(directory) / "model.txt"
            xcnf_path.write_bytes(raw)
            result = subprocess.run(
                [str(binary_path), "--verb", "0", "--threads", "1",
                 "--maxtime", "30", *MATRIX_FLAGS, str(xcnf_path)],
                capture_output=True, text=True, timeout=45, check=False)
            assert result.returncode == 10, (n, result.returncode)
            model_path.write_text(result.stdout)
            instance = (parent["cells"]["53"]["instance"] if n == 53
                        else n83_parent["cells"]["83"]["instance"])
            check = replay(formula, meta, model_path, instance)
            assert check["status"] == "verified_four_point_relation"
            assert check["raw_leaf_x"] == row["raw_leaf_x"]
        rows.append({
            "degree_n": n, "curve_id": row["curve_id"],
            "control_law": row["control_law"],
            "raw_leaf_x": row["raw_leaf_x"],
            "raw_target_x": row["raw_target_x"],
            "xcnf_sha256": sha_bytes(raw),
            "xcnf_variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "native_xor_rows": len(formula.xors),
            "and_gates": len(formula.and_cache),
            "solver_exit_code": result.returncode,
            "solver_stdout_sha256": sha_bytes(result.stdout.encode()),
            "verified_relation": check,
        })
    output = {
        "kind": "q1453_projective_phi5_pinned_controls",
        "proposal_id": "Q1453", "candidate_id": None,
        "isogeny": "none", "status": "pass", "rows": rows,
        "matrix_flags": MATRIX_FLAGS,
        "q1448_validation_sha256": sha(validation_path),
        "parent_q1452_protocol_sha256": sha(parent_path),
        "n83_parent_q1451_protocol_sha256": sha(n83_parent_path),
        "algebra_validation_sha256": sha(algebra_path),
        "cms_binary_sha256": sha(binary_path),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
    }
    if args.check:
        assert output == json.loads(OUTPUT.read_text())
        print("Q1453 projective phi5 N53/N83 pinned controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
        print("Q1453 projective phi5 N53/N83 pinned controls: PASS")


if __name__ == "__main__":
    main()
