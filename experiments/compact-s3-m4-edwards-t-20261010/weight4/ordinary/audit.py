#!/usr/bin/env python3
"""Audit frozen ordinary t-PDP input, solver stream, and any group relation."""

import gzip
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W4 = HERE.parent
T_PARENT = W4.parent
ROOT = HERE.parents[3]
Q1419 = ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin"
sys.path[:0] = [str(T_PARENT), str(Q1419),
                str(ROOT / "experiments/compact-s3-m4-20261003"),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from run_cell import read_profile  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
from t_link import t_of_x, x_roots_of_t  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify_relation(frozen, prepared, model):
    f, e = field.Onb(53), curves.Curve(field.Onb(53))
    packed = (W4 / "bases/n53_t_weight4_columns.bin").read_bytes()
    assert hashlib.sha256(packed).hexdigest() == frozen[
        "factor_base_enumerated_set_sha256"]
    keys = {int.from_bytes(packed[i:i+7], "little")
            for i in range(0, len(packed), 7)}
    assert len(keys) == frozen["folded_columns_K"]
    coords = [sum(1 << index for index, bit in enumerate(vector)
                  if model[bit]) for vector in prepared["leaves"]]
    points = []
    columns = []
    for value in coords:
        if value == 0 or value.bit_count() > 4:
            return {"status": "outside_t_weight", "leaf_t_coords": coords}
        roots = x_roots_of_t(f, e, f.fromCoords(value))
        if not roots:
            return {"status": "nonrational_t", "leaf_t_coords": coords}
        point = e.pointFromX(roots[1])
        if point is None:
            return {"status": "nonrational_t", "leaf_t_coords": coords}
        subgroup = e.mul(point, frozen["cofactor"])
        if subgroup is None:
            return {"status": "identity_projection", "leaf_t_coords": coords}
        assert e.mul(subgroup, frozen["subgroup_order_r"]) is None
        x = subgroup[0]
        cycle = []
        for _ in range(53):
            cycle.append(f.toCoords(x))
            x = f.sqr(x)
        key = min(cycle)
        if key not in keys:
            return {"status": "outside_exact_t_base", "leaf_t_coords": coords}
        points.append(subgroup)
        columns.append(key)
    public = tuple(frozen["public_target"])
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(points, signs):
            total = e.add(total, point if sign == 1 else e.neg(point))
        if total == public:
            # The other x lift differs by rational 2-torsion; cofactor
            # projection is the same point up to sign. Compare certificates
            # after canonicalizing the sign/orientation below.
            return {"status": "verified_four_point_relation",
                    "leaf_t_coords": coords, "signs": list(signs),
                    "folded_columns": columns,
                    "distinct_columns": len(set(columns))}
    return {"status": "no_signed_public_sum", "leaf_t_coords": coords,
            "folded_columns": columns}


def main():
    frozen = load(HERE / "freeze.json")
    assert frozen["schema"] == "q20261010174500-freeze-v1"
    assert frozen["proposal_id"] == "Q20261010174500"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert frozen["isogeny"] == "none"
    assert frozen["q1419_protocol_sha256"] == digest(Q1419 / "protocol.json")
    assert frozen["w4_run_sha256"] == digest(W4 / "run.json")
    assert frozen["w4_base_sha256"] == digest(
        W4 / "bases/n53_t_weight4_columns.bin")
    assert frozen["t_link_source_sha256"] == digest(T_PARENT / "t_link.py")
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    prepared = load(HERE / "prepare.json")
    assert prepared["freeze_sha256"] == digest(HERE / "freeze.json")
    assert prepared["proposal_id"] == frozen["proposal_id"]
    assert prepared["curve_id"] == frozen["curve_id"]
    assert prepared["workload_id"] == frozen["ordinary_workload_id"]
    profile, parent, _ = read_profile(load(Q1419 / "protocol.json"), 53)
    f = field.Onb(53)
    options = sorted({f.toCoords(t_of_x(f, f.fromCoords(x))) for x in
                      parent["raw_preimage_x_coordinates"]})
    assert options == prepared["target_t_options_coords"]
    assert prepared["raw_target_preimage_count"] == frozen[
        "raw_target_preimage_count"]
    archive = HERE / "inputs/system.xcnf.gz"
    assert digest(archive) == prepared["formula_archive_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert len(raw) == prepared["formula_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == prepared["formula_sha256"]
    lines = raw.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    assert list(map(int, header[2:])) == [prepared["variables"],
         prepared["cnf_clauses"] + prepared["xor_rows"]]
    assert len(lines) == 1 + prepared["cnf_clauses"] + prepared["xor_rows"]
    assert prepared["and_gates"] > 0
    assert prepared["formula_construction_seconds_exploratory"] >= 0
    result = load(HERE / "run.json")
    assert result["proposal_id"] == frozen["proposal_id"]
    assert result["candidate_id"] is result["run_id"] is None
    assert result["isogeny"] == "none"
    assert result["freeze_sha256"] == digest(HERE / "freeze.json")
    assert result["prepare_sha256"] == digest(HERE / "prepare.json")
    assert result["formula_sha256"] == prepared["formula_sha256"]
    assert result["solver_sha256"] == frozen["solver_sha256"]
    assert result["solver_flags"] == frozen["solver_flags"]
    assert result["actual_usable_points_B"] == frozen[
        "actual_usable_points_B"]
    assert result["folded_columns_K"] == frozen["folded_columns_K"]
    assert result["factor_base_enumerated_set_sha256"] == frozen[
        "factor_base_enumerated_set_sha256"]
    assert result["public_target"] == frozen["public_target"]
    assert result["workload_id"] == frozen["ordinary_workload_id"]
    stdout_path, stderr_path = (HERE / "solver.stdout.gz",
                                HERE / "solver.stderr.gz")
    assert digest(stdout_path) == result["stdout_gzip_sha256"]
    assert digest(stderr_path) == result["stderr_gzip_sha256"]
    stdout = gzip.decompress(stdout_path.read_bytes()).decode(errors="replace")
    stderr = gzip.decompress(stderr_path.read_bytes()).decode(errors="replace")
    matches = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", stdout)
    assert result["conflicts_reported"] == (
        int(matches[-1]) if matches else None)
    assert result["solver_wall_seconds_exploratory"] >= 0
    assert result["child_user_seconds"] >= 0
    assert result["child_system_seconds"] >= 0
    assert result["peak_child_rss_raw"] > 0
    assert result["relation_check_seconds_exploratory"] >= 0
    status = result["solver_status"]
    if status == "SAT":
        assert result["return_code"] == 10 and not result[
            "external_timeout"]
        model = parsed_model(stdout)
        assert model is not None
        check_serialized_xcnf(raw, model)
        replay = verify_relation(frozen, prepared, model)
        assert replay["status"] == result["relation"]["status"]
        assert replay["leaf_t_coords"] == result["relation"][
            "leaf_t_coords"]
        if replay["status"] == "verified_four_point_relation":
            assert replay["folded_columns"] == result["relation"][
                "folded_columns"]
            assert replay["distinct_columns"] == result["relation"][
                "distinct_columns"]
    elif status == "UNSAT":
        assert result["return_code"] == 20
        assert "s UNSATISFIABLE" in stdout and result["relation"] is None
    else:
        assert status == "BOUNDED_UNKNOWN" and result["relation"] is None
        assert result["external_timeout"] or result[
            "conflicts_reported"] is not None
        assert "c rst" in stdout or "c confl" in stdout
        assert "ERROR" not in stderr.upper()
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010174500-audit-v1",
        "status": "PASS", "solver_status": status,
        "relation_status": result["relation"]["status"] if result[
            "relation"] else None,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "prepare_sha256": digest(HERE / "prepare.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "solver_status": status,
        "relation_status": result["relation"]["status"] if result[
            "relation"] else None}))


if __name__ == "__main__":
    main()
