#!/usr/bin/env python3
"""Audit Q1515 frozen inputs, censored rows, and pinned SAT replay."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
sys.path.insert(0, str(PARENT / "q20261011_wdsat_width_lift"))
from prepare import evaluate  # noqa: E402
sys.path.insert(0, str(HERE))
from balanced_sweep import build_balanced, input_data, parse_model, verify  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    assert protocol["proposal_id"] == freeze["proposal_id"] == "Q1515"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    for name, digest in freeze["source_and_input_sha256"].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    assert sha(Path(freeze["solver_path"]).read_bytes()) == freeze["solver_binary_sha256"]
    base = json.loads((PARENT / "bases/n83_weight5_full_orbits.json").read_text())
    fb = base["factor_base"]
    assert fb["actual_usable_points_B_before_folding"] == protocol["w5_factor_base_actual_B"]
    assert fb["signed_frobenius_columns"] == protocol["w5_factor_base_folded_columns_K"]
    assert fb["enumerated_set_sha256"] == protocol["w5_factor_base_enumerated_set_sha256"]
    assert protocol["w6_factor_base_actual_B"] is None and protocol["w7_factor_base_actual_B"] is None
    labels = [f"{kind}_w{weight}" for kind in ("selected", "holdout") for weight in (5, 6, 7)]
    labels += ["planted_w7", "planted_w7_midpin", "planted_relaxed"]
    rows = []
    for label in labels:
        receipt = json.loads((HERE / f"{label}.json").read_text())
        archive = (HERE / f"{label}.xcnf.gz").read_bytes()
        assert sha(archive) == freeze["xcnf_gzip_sha256"][f"{label}.xcnf.gz"]
        raw = gzip.decompress(archive)
        assert sha(raw) == receipt["formula_sha256"]
        header = raw.splitlines()[0].split()
        assert header[:2] == [b"p", b"cnf"]
        assert int(header[2]) == receipt["variables"]
        assert int(header[3]) == receipt["cnf_clauses"] + receipt["xor_rows"]
        stdout = (HERE / f"{label}.stdout.txt").read_bytes()
        stderr = (HERE / f"{label}.stderr.txt").read_bytes()
        assert sha(stdout) == receipt["stdout_sha256"]
        assert sha(stderr) == receipt["stderr_sha256"]
        if receipt["status"] == "VERIFIED_RELATION":
            assert label == "planted_w7_midpin"
            model = parse_model(stdout.decode(), receipt["variables"])
            assert model is not None
            assert evaluate(raw, model)["xor_rows"] == receipt["xor_rows"]
            target, preimages, _ = input_data("planted")
            formula, leaves, _, _, _ = build_balanced(83, 7, preimages)
            assert verify(formula, leaves, target, 7, model) == receipt["model_check"]
        else:
            assert receipt["status"] == "INDETERMINATE"
            assert "s INDETERMINATE" in stdout.decode(errors="replace")
            assert receipt["model_check"] is None
        conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", stdout.decode(errors="replace"), re.M)
        rows.append({"label": label, "status": receipt["status"],
                     "conflicts_reported": int(conflicts[-1]) if conflicts else None,
                     "variables": receipt["variables"], "clauses": receipt["cnf_clauses"],
                     "xor_rows": receipt["xor_rows"]})
    analysis = json.loads((HERE / "analysis.json").read_text())
    assert analysis["ordinary_stage_rows"] == [
        row for row in rows if row["label"].startswith(("selected", "holdout"))]
    assert analysis["verified_ordinary_relations"] == 0
    assert analysis["full_n131_single_target_log2_work"] is None
    assert analysis["challenge_run_admitted"] is False
    return rows


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
