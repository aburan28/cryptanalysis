#!/usr/bin/env python3
"""Prove CMS native-XOR parsing preserves the Q1448 pinned relations."""

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

from chain_s3 import field  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1448_torsion_phi5.build_formula import build, transformed_targets  # noqa: E402
from q1448_torsion_phi5.verify_model import replay  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402

OUTPUT = HERE / "controls.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent_path = PARENT / "q1448_torsion_phi5/protocol.json"
    validation_path = PARENT / "q1448_torsion_phi5/validation.json"
    parent = json.loads(parent_path.read_text())
    controls = json.loads(validation_path.read_text())
    binary = shutil.which("cryptominisat5")
    assert binary is not None
    binary_path = Path(binary).resolve()
    rows = []
    for row in controls["rows"]:
        n = row["degree_n"]
        if n == 53:
            formula, meta = build(n)
        else:
            formula, meta = build(n, [row["raw_target_x"]],
                                  row["public_target"])
        onb = field.Onb(n)
        for bits, mask in zip(meta["leaf_x_variables"], row["raw_leaf_x"]):
            pin_bits(formula, bits, mask)
        for bits, mask in zip(meta["leaf_phi_variables"], row["raw_leaf_x"]):
            pin_bits(formula, bits,
                     transformed_targets(onb, [mask])[0])
        pin_bits(formula, meta["target_selector_variables"],
                 row["target_selector_choice"])
        raw = xcnf_bytes(formula)
        with tempfile.TemporaryDirectory(prefix=f"q1449-n{n}-") as directory:
            xcnf_path = Path(directory) / "control.xcnf"
            model_path = Path(directory) / "model.txt"
            xcnf_path.write_bytes(raw)
            result = subprocess.run(
                [str(binary_path), "--verb", "0", "--threads", "1",
                 "--maxtime", "30", str(xcnf_path)],
                capture_output=True, text=True, timeout=45, check=False)
            model_path.write_text(result.stdout)
            assert result.returncode == 10
            check = replay(formula, meta, model_path,
                           parent["cells"][str(n)]["instance"])
            assert check["status"] == "verified_four_point_relation"
        rows.append({
            "degree_n": n, "curve_id": row["curve_id"],
            "control_law": row["control_law"],
            "xcnf_sha256": sha_bytes(raw),
            "xcnf_variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "native_xor_rows": len(formula.xors),
            "solver_exit_code": result.returncode,
            "solver_stdout_sha256": sha_bytes(result.stdout.encode()),
            "verified_relation": check,
        })
    result = {
        "kind": "q1449_phi5_native_xor_pinned_controls",
        "proposal_id": "Q1449", "candidate_id": None,
        "isogeny": "none", "status": "pass", "rows": rows,
        "parent_q1448_protocol_sha256": sha(parent_path),
        "parent_q1448_validation_sha256": sha(validation_path),
        "cms_binary_sha256": sha(binary_path),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
    }
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1449 native-XOR N53/N83 pinned controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print("Q1449 native-XOR N53/N83 pinned controls: PASS")


if __name__ == "__main__":
    main()
