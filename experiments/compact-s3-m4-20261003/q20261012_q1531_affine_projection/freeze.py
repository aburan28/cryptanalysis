#!/usr/bin/env python3
"""Freeze projected formula and solver identities before measured runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1528 = HERE.parent / "q20261012_q1528_gate_elimination"
SOLVER = Path("/Volumes/SSD990/llm/tmp/q1525-dpll-anf/simp/glucose")
PANEL = ("n53_pinned", "n53_ordinary", "n83_pinned", "n83_selected", "n83_holdout")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = HERE / "protocol.json"
    assert not target.exists()
    parent = json.loads((Q1528 / "protocol.json").read_text())
    assert sha(SOLVER) == parent["solver_binary_sha256"]
    inputs = {}
    for label in PANEL:
        record = json.loads((HERE / "formulas" / f"{label}.json").read_text())
        for file, key in ((f"{label}.anf", "anf_sha256"),
                          (f"{label}.anf.gz", "gzip_sha256"),
                          (f"{label}.basis.json", "basis_sha256")):
            assert sha(HERE / "formulas" / file) == record[key]
        assert sha(Q1528 / "formulas" / f"{label}.anf.gz") == record["source_gzip_sha256"]
        inputs[label] = record
    protocol = {
        "proposal_id": "Q1531", "candidate_id": None, "run_id": None,
        "stage_code": "PDP4sat", "isogeny": "none",
        "curve_ids": {"n53": "EC1N53Ckb1hf77aab617904",
                      "n83": "EC1N83Ckb1h876c2921cb64"},
        "factor_bases": {"n53": {"B": 24062, "K": 227,
                                    "digest": "05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5"},
                         "n83": {"B": 30977592, "K": 186612,
                                    "digest": "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8"}},
        "q1528_protocol_sha256": sha(Q1528 / "protocol.json"),
        "converter_sha256": sha(HERE / "project.py"),
        "runner_sha256": sha(HERE / "run.py"),
        "solver_path": str(SOLVER), "solver_sha256": sha(SOLVER),
        "solver_options": parent["solver_options"],
        "wall_seconds": parent["wall_seconds"],
        "panel_order": list(PANEL), "inputs": inputs,
        "pre_measured_control": "Q1528 n53_pinned model satisfies both original and projected ANF and round-trips through the affine basis",
        "comparison": "Q1528 exact same solver, original sources, ordered labels, and 90-second wall boundary; CPU/wall exploratory without host isolation",
        "complete_n131_solve_work_log2": None,
    }
    target.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(sha(target))


if __name__ == "__main__":
    main()
