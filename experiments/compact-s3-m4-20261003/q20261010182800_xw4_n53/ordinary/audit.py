#!/usr/bin/env python3
"""Independent archive and signed group-law audit of the ordinary N53 cell."""

import gzip
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PARENT = BASE.parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(PARENT / "q1419_partial_pin"),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def replay(frozen, prepared, model):
    onb, curve = field.Onb(53), curves.Curve(field.Onb(53))
    coset = load(PARENT / "runs/n53_ordinary_raw_preimages.json")
    coords = [sum(1 << i for i, bit in enumerate(row) if model[bit])
              for row in prepared["leaves"]]
    assert all(0 < value < (1 << 53) and value.bit_count() <= 4
               for value in coords)
    leaves = []
    for value in coords:
        point = curve.pointFromX(onb.fromCoords(value))
        if point is None:
            return {"status": "nonrational_x", "leaf_x_coords": coords}
        leaves.append(curve.neg(point))  # Other sign from the producer lift.
    keys_raw = (BASE / "n53_x_weight4_columns.bin").read_bytes()
    assert digest(BASE / "n53_x_weight4_columns.bin") == frozen[
        "factor_base_enumerated_set_sha256"]
    keys = {int.from_bytes(keys_raw[i:i+7], "little")
            for i in range(0, len(keys_raw), 7)}
    assert len(keys) == frozen["folded_columns_K"]
    selected = load(HERE / "run.json")["model_replay"]["selected_target_index"]
    raw_target = tuple(map(int, coset["raw_target_points"][selected]))
    assert curve.mul(raw_target, frozen["cofactor"]) == tuple(
        frozen["public_target"])
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(leaves, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total != raw_target:
            continue
        projected = [curve.mul(point, frozen["cofactor"]) for point in leaves]
        if any(point is None for point in projected):
            return {"status": "projected_identity", "leaf_x_coords": coords}
        columns = []
        for point in projected:
            assert curve.mul(point, frozen["subgroup_order_r"]) is None
            x = point[0]
            cycle = []
            for _ in range(53):
                cycle.append(onb.toCoords(x))
                x = onb.sqr(x)
            key = min(cycle)
            assert key in keys
            columns.append(key)
        public = None
        for point, sign in zip(projected, signs):
            public = curve.add(public, point if sign == 1 else curve.neg(point))
        assert public == tuple(frozen["public_target"])
        return {"status": "verified_four_point_relation",
                "leaf_x_coords": coords, "folded_columns": columns,
                "distinct_columns": len(set(columns))}
    return {"status": "no_sign_lift", "leaf_x_coords": coords}


def main():
    frozen, prepared, run = [load(HERE / name) for name in
                             ("freeze.json", "prepare.json", "run.json")]
    base = load(BASE / "run.json")
    assert frozen["schema"] == "q20261010183500-freeze-v1"
    assert (frozen["proposal_id"] == prepared["proposal_id"] ==
            run["proposal_id"] == "Q20261010183500")
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert run["candidate_id"] is run["run_id"] is None
    assert frozen["isogeny"] == run["isogeny"] == "none"
    assert frozen["base_run_sha256"] == digest(BASE / "run.json")
    assert frozen["factor_base_enumerated_set_sha256"] == digest(
        BASE / "n53_x_weight4_columns.bin")
    assert frozen["parent_run_sha256"] == digest(
        PARENT / "runs/n53_q1410_ordinary.json")
    assert frozen["parent_protocol_sha256"] == digest(
        PARENT / "q1410_balanced_s3_n53_protocol.json")
    assert frozen["parent_formula_archive_sha256"] == digest(
        PARENT / "runs/n53_q1410_ordinary.xcnf.gz")
    assert frozen["coset_sha256"] == digest(
        PARENT / "runs/n53_ordinary_raw_preimages.json")
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    assert frozen["external_wall_cap_seconds"] == 1200
    assert frozen["solver_flags"][-2:] == ["--maxconfl", "1000000"]
    assert base["actual_usable_points_B"] == frozen[
        "actual_usable_points_B"] == 324042
    assert base["folded_columns_K"] == frozen["folded_columns_K"] == 3057
    assert prepared["freeze_sha256"] == run["freeze_sha256"] == digest(
        HERE / "freeze.json")
    assert prepared["parent_formula_sha256"] == frozen[
        "parent_formula_sha256"]
    assert prepared["target_preimage_count"] == 428
    archive = HERE / "formula.xcnf.gz"
    assert prepared["formula_archive_sha256"] == digest(archive)
    raw = gzip.decompress(archive.read_bytes())
    assert len(raw) == prepared["formula_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == prepared[
        "formula_sha256"] == run["formula_sha256"]
    lines = raw.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    assert list(map(int, header[2:])) == [prepared["variables"],
        prepared["cnf_clauses"] + prepared["xor_rows"]]
    assert len(lines) == 1 + prepared["cnf_clauses"] + prepared["xor_rows"]
    assert prepared["and_gates"] > 0
    assert prepared["formula_construction_seconds_exploratory"] >= 0
    for key in ("curve_id", "workload_id", "public_target",
                "actual_usable_points_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256", "solver_sha256",
                "solver_flags"):
        assert run[key] == frozen[key]
    assert run["workload_id"] == "74f2979b3e68"
    assert run["prepare_sha256"] == digest(HERE / "prepare.json")
    out_path, err_path = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    assert run["stdout_gzip_sha256"] == digest(out_path)
    assert run["stderr_gzip_sha256"] == digest(err_path)
    stdout = gzip.decompress(out_path.read_bytes()).decode(errors="replace")
    stderr = gzip.decompress(err_path.read_bytes()).decode(errors="replace")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", stdout)
    assert run["conflicts_reported"] == (int(conflicts[-1]) if conflicts else None)
    assert run["solver_wall_seconds_exploratory"] >= 0
    assert run["child_user_seconds"] >= 0
    assert run["child_system_seconds"] >= 0
    assert run["peak_child_rss_raw"] > 0
    assert run["relation_check_seconds_exploratory"] >= 0
    status = run["solver_status"]
    if status == "SAT":
        assert run["return_code"] == 10 and not run["external_timeout"]
        model = parsed_model(stdout)
        assert model is not None
        check_serialized_xcnf(raw, model)
        independent = replay(frozen, prepared, model)
        assert independent["status"] == run["model_replay"]["status"]
        assert independent["leaf_x_coords"] == run["model_replay"][
            "leaf_x_coords"]
        if independent["status"] == "verified_four_point_relation":
            assert independent["folded_columns"] == run[
                "model_replay"]["folded_columns"]
            assert independent["distinct_columns"] == run[
                "model_replay"]["distinct_columns"]
    elif status == "UNSAT":
        assert run["return_code"] == 20
        assert "s UNSATISFIABLE" in stdout and run["model_replay"] is None
    else:
        assert status == "BOUNDED_UNKNOWN" and run["model_replay"] is None
        assert run["external_timeout"] or run["conflicts_reported"] is not None
        assert "c rst" in stdout or "c confl" in stdout
        assert "ERROR" not in stderr.upper()
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010183500-audit-v1",
        "status": "PASS", "solver_status": status,
        "relation_status": run["model_replay"]["status"] if run[
            "model_replay"] else None,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "prepare_sha256": digest(HERE / "prepare.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "solver_status": status,
                      "relation_status": run["model_replay"]["status"]
                      if run["model_replay"] else None}))


if __name__ == "__main__":
    main()
