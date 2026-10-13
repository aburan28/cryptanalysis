#!/usr/bin/env python3
"""Regenerate Q1531 projections and verify archived solver/model receipts."""
import hashlib
import json
from pathlib import Path

import project

HERE = Path(__file__).resolve().parent
Q1528 = project.Q1528


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = json.loads((HERE / "protocol.json").read_text())
    a = json.loads((HERE / "analysis.json").read_text())
    assert p["proposal_id"] == a["proposal_id"] == "Q1531"
    assert p["candidate_id"] is None and p["run_id"] is None
    assert p["isogeny"] == a["isogeny"] == "none"
    assert sha(HERE / "protocol.json") == a["protocol_sha256"]
    assert sha(HERE / "analyze.py") == a["source_sha256"]
    assert sha(HERE / "project.py") == p["converter_sha256"]
    assert sha(HERE / "run.py") == p["runner_sha256"]
    assert sha(Path(p["solver_path"])) == p["solver_sha256"]
    assert sha(Q1528 / "protocol.json") == p["q1528_protocol_sha256"]
    assert sha(Q1528 / "analysis.json") == a["baseline_q1528_analysis_sha256"]
    assert len(p["panel_order"]) == len(a["rows"]) == 5
    for row in a["rows"]:
        label = row["label"]
        frozen = p["inputs"][label]
        n, source_rows, nonlinear, raw = project.load(label)
        data, live, basis, info = project.project(n, source_rows, nonlinear)
        folder = HERE / "formulas"
        assert data == (folder / f"{label}.anf").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == frozen["source_anf_sha256"]
        assert sha(Q1528 / "formulas" / f"{label}.anf.gz") == frozen["source_gzip_sha256"]
        basis_record = json.loads((folder / f"{label}.basis.json").read_text())
        assert basis_record == {"live": live, "basis": [list(x) for x in basis]}
        for key in ("variables", "equations", "eliminated_pivots",
                    "pure_linear_variables", "free_variables_omitted"):
            assert info[key] == frozen[key]
        assert row["variables"] == len(live)
        assert row["eliminated_pivots"] == len(basis)
        runs = HERE / "runs" / label
        receipt = json.loads((runs / "receipt.json").read_text())
        assert sha(runs / "receipt.json") == row["receipt_sha256"]
        assert sha(runs / "stdout.txt") == receipt["stdout_sha256"]
        assert sha(runs / "stderr.txt") == receipt["stderr_sha256"]
        assert receipt["status"] == row["status"]
    assert a["rows"][0]["status"] == "SAT_VERIFIED"
    assert a["rows"][0]["verified_group_relation"]
    # Independent pinned model from Q1528 satisfies both representations and
    # round-trips through every saved affine pivot.
    label = "n53_pinned"
    source_stdout = (Q1528 / "runs" / label / "stdout.txt").read_text()
    model = next(x[2:] for x in source_stdout.splitlines()
                 if x.startswith("s ") and set(x[2:]) <= {"0", "1"})
    n, original_rows, nonlinear, _ = project.load(label)
    new, live, basis, _ = project.project(n, original_rows, nonlinear)
    reduced = "".join(model[i-1] for i in live)
    assert project.evaluate(original_rows, model)
    assert project.evaluate(project.parse_data(new)[1], reduced)
    assert project.lift_model(reduced, live, basis, n) == model
    proof = json.loads((HERE / "lean/proof_receipt.json").read_text())
    for name, key in (("AffineProjection.lean", "source_sha256"),
                      ("build.stdout.txt", "stdout_sha256"),
                      ("build.stderr.txt", "stderr_sha256")):
        assert sha(HERE / "lean" / name) == proof[key]
    assert not (HERE / "lean/build.stderr.txt").read_text()
    output = (HERE / "lean/build.stdout.txt").read_text()
    assert output.count("depends on axioms") == 2
    assert output.count("does not depend on any axioms") == 1
    print("PASS Q1531: five exact projections, receipts, pinned model, Lean")


if __name__ == "__main__":
    main()
