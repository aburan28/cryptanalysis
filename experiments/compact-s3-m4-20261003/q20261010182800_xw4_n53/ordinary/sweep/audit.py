#!/usr/bin/env python3
"""Audit every frozen x-W4 solver-setting cell and any full-point relation."""

import gzip
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT.parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin"),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def replay(frozen, prepared, row, model):
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    coset = load(ROOT / "experiments/compact-s3-m4-20261003/runs/n53_ordinary_raw_preimages.json")
    coords = [sum(1 << i for i, lit in enumerate(vector) if model[lit])
              for vector in prepared["leaves"]]
    assert all(0 < value < (1 << 53) and value.bit_count() <= 4
               for value in coords)
    choice = sum(1 << i for i, lit in enumerate(prepared["selector"])
                 if model[lit])
    assert choice == row["model_replay"]["selected_target_index"]
    raw_target = tuple(map(int, coset["raw_target_points"][choice]))
    assert curve.mul(raw_target, 428) == tuple(frozen["public_target"])
    points = []
    for value in coords:
        point = curve.pointFromX(onb.fromCoords(value))
        if point is None:
            return "nonrational_x", coords, None
        points.append(curve.neg(point))
    keys_raw = (BASE / "n53_x_weight4_columns.bin").read_bytes()
    keys = {int.from_bytes(keys_raw[i:i+7], "little")
            for i in range(0, len(keys_raw), 7)}
    assert len(keys) == frozen["folded_columns_K"]
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total != raw_target:
            continue
        projected = [curve.mul(point, 428) for point in points]
        if any(point is None for point in projected):
            return "projected_identity", coords, None
        columns = []
        public = None
        for point, sign in zip(projected, signs):
            assert curve.mul(point, 21044858204113) is None
            public = curve.add(public, point if sign == 1 else curve.neg(point))
            x = point[0]
            cycle = []
            for _ in range(53):
                cycle.append(onb.toCoords(x))
                x = onb.sqr(x)
            key = min(cycle)
            assert key in keys
            columns.append(key)
        assert public == tuple(frozen["public_target"])
        return "verified_four_point_relation", coords, columns
    return "no_sign_lift", coords, None


def main():
    frozen, run, prepared = [load(path) for path in
        (HERE / "freeze.json", HERE / "run.json", PARENT / "prepare.json")]
    assert frozen["schema"] == "q20261010184000-freeze-v1"
    assert frozen["proposal_id"] == run["proposal_id"] == "Q20261010184000"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert run["candidate_id"] is run["run_id"] is None
    assert frozen["isogeny"] == run["isogeny"] == "none"
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["formula_archive_sha256"] == digest(PARENT / "formula.xcnf.gz")
    assert frozen["formula_sha256"] == prepared["formula_sha256"]
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    assert frozen["external_wall_cap_seconds_per_cell"] == 300
    assert frozen["common_solver_flags"][-2:] == ["--maxconfl", "100000"]
    raw = gzip.decompress((PARENT / "formula.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    assert run["freeze_sha256"] == digest(HERE / "freeze.json")
    for key in ("curve_id", "workload_id", "public_target",
                "actual_usable_points_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256", "formula_sha256",
                "solver_sha256"):
        assert run[key] == frozen[key]
    assert run["workload_id"] == "74f2979b3e68"
    assert run["actual_usable_points_B"] == 324042
    assert run["folded_columns_K"] == 3057
    assert len(run["cells"]) == len(frozen["cells"]) == 4
    for cell, specification in zip(run["cells"], frozen["cells"]):
        name = specification["name"]
        assert cell == load(HERE / f"{name}.json")
        assert cell["name"] == name
        assert cell["extra_flags"] == specification["extra_flags"]
        out_path = HERE / f"{name}.stdout.gz"
        err_path = HERE / f"{name}.stderr.gz"
        assert digest(out_path) == cell["stdout_gzip_sha256"]
        assert digest(err_path) == cell["stderr_gzip_sha256"]
        stdout = gzip.decompress(out_path.read_bytes()).decode(errors="replace")
        stderr = gzip.decompress(err_path.read_bytes()).decode(errors="replace")
        conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", stdout)
        assert cell["conflicts_reported"] == (
            int(conflicts[-1]) if conflicts else None)
        assert cell["solver_wall_seconds_exploratory"] >= 0
        assert cell["child_user_seconds"] >= 0
        assert cell["child_system_seconds"] >= 0
        assert cell["peak_child_rss_raw"] > 0
        assert cell["relation_check_seconds_exploratory"] >= 0
        status = cell["solver_status"]
        if status == "SAT":
            assert cell["return_code"] == 10 and not cell["external_timeout"]
            model = parsed_model(stdout)
            assert model is not None
            check_serialized_xcnf(raw, model)
            status_name, coords, columns = replay(frozen, prepared, cell, model)
            assert status_name == cell["model_replay"]["status"]
            assert coords == cell["model_replay"]["leaf_x_coords"]
            if columns is not None:
                assert columns == cell["model_replay"]["folded_columns"]
        elif status == "UNSAT":
            assert cell["return_code"] == 20
            assert "s UNSATISFIABLE" in stdout and cell["model_replay"] is None
        else:
            assert status == "BOUNDED_UNKNOWN" and cell["model_replay"] is None
            assert cell["external_timeout"] or cell[
                "conflicts_reported"] is not None
            assert "c rst" in stdout or "c confl" in stdout
            assert "ERROR" not in stderr.upper()
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010184000-audit-v1",
        "status": "PASS", "cell_statuses": [row["solver_status"] for row in
                                         run["cells"]],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "cells": len(run["cells"])}))


if __name__ == "__main__":
    main()
