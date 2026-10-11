#!/usr/bin/env python3
"""Independent signed-point and archive audit of the weight-four control."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q = HERE.parent
PARENT = Q / "ordinary"
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin"),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    frozen, prepared, result = [load(HERE / name) for name in
                                ("freeze.json", "prepare.json", "run.json")]
    assert frozen["schema"] == "q20261010184800-freeze-v1"
    assert (frozen["proposal_id"] == prepared["proposal_id"] ==
            result["proposal_id"] == "Q20261010184800")
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert result["candidate_id"] is result["run_id"] is None
    assert frozen["isogeny"] == result["isogeny"] == "none"
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["ordinary_formula_archive_sha256"] == digest(
        PARENT / "formula.xcnf.gz")
    witness_path = (ROOT / "experiments/compact-s3-m4-20261003/runs/"
                    "n53_q1410_witness_locked.json")
    assert frozen["witness_receipt_sha256"] == digest(witness_path)
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    assert prepared["freeze_sha256"] == result["freeze_sha256"] == digest(
        HERE / "freeze.json")
    assert result["prepare_sha256"] == digest(HERE / "prepare.json")
    parent_raw = gzip.decompress((PARENT / "formula.xcnf.gz").read_bytes())
    assert hashlib.sha256(parent_raw).hexdigest() == frozen[
        "ordinary_formula_sha256"]
    path = HERE / "formula.xcnf.gz"
    assert digest(path) == prepared["formula_archive_sha256"]
    raw = gzip.decompress(path.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == prepared[
        "formula_sha256"] == result["formula_sha256"]
    old_lines, lines = parent_raw.decode("ascii").splitlines(), raw.decode(
        "ascii").splitlines()
    assert lines[1:len(old_lines)] == old_lines[1:]
    assert lines[len(old_lines):] == [f"{lit} 0" for lit in prepared[
        "pin_literals"]]
    header, old_header = lines[0].split(), old_lines[0].split()
    assert header[:3] == old_header[:3]
    assert int(header[3]) == int(old_header[3]) + prepared[
        "added_unit_clauses"]
    assert prepared["added_unit_clauses"] == len(prepared["pin_literals"])
    assert result["curve_id"] == frozen["curve_id"]
    assert result["workload_id"] == frozen["workload_id"] == "74f2979b3e68"
    assert result["solver_sha256"] == frozen["solver_sha256"]
    assert result["solver_flags"] == frozen["solver_flags"]
    out_path, err_path = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    assert digest(out_path) == result["stdout_gzip_sha256"]
    assert digest(err_path) == result["stderr_gzip_sha256"]
    stdout = gzip.decompress(out_path.read_bytes()).decode(errors="replace")
    stderr = gzip.decompress(err_path.read_bytes()).decode(errors="replace")
    assert result["solver_wall_seconds_exploratory"] >= 0
    assert result["child_user_seconds"] >= 0
    assert result["child_system_seconds"] >= 0
    assert result["peak_child_rss_raw"] > 0
    assert "ERROR" not in stderr.upper()
    assert result["solver_status"] == "SAT"
    assert result["return_code"] == 10 and not result["external_timeout"]
    model = parsed_model(stdout)
    assert model is not None
    check_serialized_xcnf(raw, model)
    assert all(model[abs(lit)] == (lit > 0)
               for lit in prepared["pin_literals"])
    assert result["model_replay"]["status"] == (
        "verified_four_point_relation")
    assert result["model_replay"]["leaf_x_coords"] == prepared[
        "witness_leaf_x_coords"]
    assert result["model_replay"]["selected_target_index"] == prepared[
        "selected_target_index"]
    witness = load(witness_path)["fixture"]
    onb, curve = field.Onb(53), curves.Curve(field.Onb(53))
    points = [tuple(point) for point in witness["raw_leaf_points"]]
    total = None
    for point, sign in zip(points, witness["signs"]):
        assert curve.onCurve(point)
        total = curve.add(total, point if sign == 1 else curve.neg(point))
    assert total == tuple(witness["raw_sum"])
    assert curve.mul(total, 428) == tuple(frozen["public_target"])
    keys_raw = (Q / "n53_x_weight4_columns.bin").read_bytes()
    assert digest(Q / "n53_x_weight4_columns.bin") == frozen[
        "factor_base_enumerated_set_sha256"]
    keys = {int.from_bytes(keys_raw[i:i+7], "little")
            for i in range(0, len(keys_raw), 7)}
    columns = []
    for point in points:
        subgroup = curve.mul(point, 428)
        assert subgroup is not None
        assert curve.mul(subgroup, 21044858204113) is None
        x = subgroup[0]
        cycle = []
        for _ in range(53):
            cycle.append(onb.toCoords(x))
            x = onb.sqr(x)
        key = min(cycle)
        assert key in keys
        columns.append(key)
    assert columns == result["model_replay"]["folded_columns"]
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010184800-audit-v1",
        "status": "PASS", "relation_status": "verified_four_point_relation",
        "freeze_sha256": digest(HERE / "freeze.json"),
        "prepare_sha256": digest(HERE / "prepare.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS",
                      "relation_status": "verified_four_point_relation"}))


if __name__ == "__main__":
    main()
