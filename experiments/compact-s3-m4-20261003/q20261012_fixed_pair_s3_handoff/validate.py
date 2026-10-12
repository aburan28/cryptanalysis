#!/usr/bin/env python3
"""Replay the Q1513 exact inputs, XCNF hashes, SAT models, and statuses."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from pathlib import Path

from run import PARENT, HERE, build, curves, field, n53_keys, parse_assignment, verify


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    assert freeze["proposal_id"] == protocol["proposal_id"] == "Q1513"
    for relative, digest in freeze["source_and_input_sha256"].items():
        assert sha(HERE.parents[2] / relative) == digest, relative
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    keys, archive53 = n53_keys()
    fb53 = archive53["factor_base"]
    assert len(keys) == protocol["n53"]["factor_base_folded_columns_K"]
    assert fb53["enumerated_set_sha256"] == protocol["n53"]["factor_base_enumerated_set_sha256"]
    assert fb53["actual_usable_points_B_before_folding"] == protocol["n53"]["factor_base_actual_B"]
    archive83 = json.loads((PARENT / "bases/n83_weight5_full_orbits.json").read_text())
    fb83 = archive83["factor_base"]
    for key, record_key in (("actual_usable_points_B_before_folding", "factor_base_actual_B"),
                            ("signed_frobenius_columns", "factor_base_folded_columns_K"),
                            ("enumerated_set_sha256", "factor_base_enumerated_set_sha256")):
        assert fb83[key] == protocol["n83"][record_key]
    assert archive53["curve"]["curve_id"] == protocol["n53"]["curve_id"]
    assert archive83["curve"]["curve_id"] == protocol["n83"]["curve_id"]
    base_path = (HERE / protocol["n53"]["base_source"]).resolve()
    export = json.loads((PARENT / "q20261011_n53_native_pair/export_receipt.json").read_text())
    assert sha(base_path) == export["files"]["base.bin"]["sha256"]
    blob = base_path.read_bytes()
    base = [(int.from_bytes(blob[i:i + 16], "little"),
             int.from_bytes(blob[i + 16:i + 32], "little"))
            for i in range(0, len(blob), 32)]
    assert len(base) == protocol["n53"]["factor_base_actual_B"]
    onb53 = field.Onb(53)
    curve53 = curves.Curve(onb53)
    target = tuple(map(int, archive53["curve"]["generator"]))
    assert curve53.onCurve(target)
    labels53 = ("n53_ordinary_seed1513", "n53_ordinary_seed1514")
    for label, pair in zip(labels53, protocol["n53"]["ordinary_first_pair_indices"]):
        assert all(curve53.onCurve(base[i]) for i in pair)
        complement = curve53.add(target, curve53.neg(curve53.add(base[pair[0]], base[pair[1]])))
        assert complement is not None
        receipt = json.loads((HERE / f"{label}.json").read_text())
        assert onb53.toCoords(complement[0]) == receipt["complement_x_coords"]
    labels83 = ("n83_ordinary_selected", "n83_ordinary_holdout")
    onb83 = field.Onb(83)
    curve83 = curves.Curve(onb83)
    for label, relative in zip(labels83, protocol["n83"]["ordinary_complement_receipts"]):
        source = json.loads((HERE / relative).read_text())
        receipt = json.loads((HERE / f"{label}.json").read_text())
        assert int(source["complement_x_onb_hex"], 16) == receipt["complement_x_coords"]
        point = tuple(onb83.fromCoords(int(source[k], 16))
                      for k in ("complement_x_onb_hex", "complement_y_onb_hex"))
        assert curve83.onCurve(point)
    labels = (*labels53, "n53_known_pair_pinned", "n53_known_complement_unpinned",
              "n53_known_unpinned_polar1", "n53_known_unpinned_polar_false",
              "n53_known_unpinned_polar_true", *labels83, "n83_planted_pinned")
    rows = []
    for label in labels:
        receipt = json.loads((HERE / f"{label}.json").read_text())
        n = receipt["n"]
        formula, raw, leaves, onb = build(n, receipt["complement_x_coords"])
        from run import pin_bits
        for bits, value in zip(raw, receipt["pin_raw"]):
            pin_bits(formula, bits, value)
        for bits, value in zip(leaves, receipt["pin_projected"]):
            pin_bits(formula, bits, value)
        assert formula.variables == receipt["variables"]
        assert len(formula.clauses) == receipt["cnf_clauses"]
        assert len(formula.xors) == receipt["xor_rows"]
        assert sha(HERE / f"{label}.xcnf") == receipt["formula_sha256"]
        stdout = (HERE / f"{label}.stdout.txt").read_text()
        stderr = (HERE / f"{label}.stderr.txt").read_text()
        assert hashlib.sha256(stdout.encode()).hexdigest() == receipt["solver_stdout_sha256"]
        assert hashlib.sha256(stderr.encode()).hexdigest() == receipt["solver_stderr_sha256"]
        if receipt["status"] == "SAT_VERIFIED":
            values = parse_assignment(stdout, formula.variables)
            assert verify(formula, raw, leaves, onb, receipt["complement_x_coords"], values) == receipt["check"]
        else:
            assert receipt["check"] is None
            assert receipt["status"] in ("INDETERMINATE", "WALL_TIMEOUT", "SOLVER_FAILURE")
            if receipt["status"] == "SOLVER_FAILURE":
                assert "unknown polarity-mode" in stderr
            assert "s SATISFIABLE" not in stdout
        conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", stdout, re.M)
        rows.append({"label": label, "status": receipt["status"],
                     "variables": receipt["variables"],
                     "cnf_clauses": receipt["cnf_clauses"],
                     "xor_rows": receipt["xor_rows"],
                     "solver_wall_seconds_exploratory": receipt["solver_wall_seconds_exploratory"],
                     "peak_child_rss_bytes_darwin": receipt.get("child_peak_rss_bytes_darwin"),
                     "conflicts_reported": int(conflicts[-1]) if conflicts else None})
    analysis = json.loads((HERE / "analysis.json").read_text())
    assert analysis["stage_rows"] == rows
    assert analysis["verified_ordinary_relations"] == 0
    assert analysis["complete_n131_single_target_work_log2"] is None
    for n, base_size, order in ((53, 24062, 21044858204113),
                                (83, 30977592, 2417851639230796216685689)):
        expected = base_size ** 2 / (2 * (order - 1))
        supply = analysis["uniform_second_pair_supply"][str(n)]
        assert math.isclose(supply["expected_representations"], expected)
        assert math.isclose(supply["log2_expected_representations"], math.log2(expected))
    return rows


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
