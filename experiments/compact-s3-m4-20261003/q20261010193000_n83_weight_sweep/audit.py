#!/usr/bin/env python3
"""Independent formula, solver-stream, and group-relation audit for N83 sweep."""

import gzip
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT),
                str(ROOT / "ecc2k130/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from q1325_inputs import read_inputs  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_relation(frozen, prepared, weight, model):
    coset = json.loads((PARENT / "runs/n83_ordinary_raw_preimages.json").read_text())
    choice = decode_choice(prepared["selector"], model)
    assert 0 <= choice < len(coset["raw_target_points"])
    coords = [sum(1 << i for i, variable in enumerate(leaf)
                  if model[variable]) for leaf in prepared["leaves"]]
    assert len(coords) == 4
    assert all(0 < x < (1 << 83) and x.bit_count() <= weight for x in coords)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    points = [curve.pointFromX(onb.fromCoords(x)) for x in coords]
    assert all(point is not None for point in points)
    raw_point = tuple(map(int, coset["raw_target_points"][choice]))
    public = tuple(map(int, frozen["public_target"]))
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total != raw_point:
            continue
        projected = [curve.mul(point, frozen["cofactor"]) for point in points]
        assert all(point is not None and curve.mul(point, frozen[
            "subgroup_order_r"]) is None for point in projected)
        assert curve.mul(total, frozen["cofactor"]) == public
        columns = [OrbitKey(onb).canonical(point)[0] for point in projected]
        if weight == 5:
            _, _, _, exact_keys, _, _ = read_inputs()
            assert all(column in set(exact_keys) for column in columns)
        return {"selected_target_index": choice, "leaf_x_coords": coords,
                "signs": signs, "folded_columns": columns,
                "distinct_folded_columns": len(set(columns))}
    raise AssertionError("SAT leaves have no signed four-point lift")


def main():
    frozen = json.loads((HERE / "freeze.json").read_text())
    prepared = json.loads((HERE / "prepare.json").read_text())
    assert prepared["freeze_sha256"] == sha(HERE / "freeze.json")
    assert prepared["target_preimage_count"] == 4
    for name, value in frozen["source_sha256"].items():
        assert sha(HERE / name) == value
    for name, value in frozen["input_sha256"].items():
        assert sha(ROOT / name) == value
    assert sha(frozen["solver_path"]) == frozen["solver_sha256"]
    coset = json.loads((PARENT / "runs/n83_ordinary_raw_preimages.json").read_text())
    rows = []
    for weight in frozen["weights"]:
        meta = next(item for item in prepared["rows"] if item["weight"] == weight)
        archive = HERE / f"w{weight}.xcnf.gz"
        assert sha(archive) == meta["formula_archive_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == meta["formula_sha256"]
        formula, leaves, _, _, selector = build_balanced(
            83, weight, coset["raw_target_x_coordinates"])
        assert leaves == meta["leaves"] and selector == meta["selector"]
        control_path = HERE / f"w{weight}.audit.xcnf"
        formula.write(control_path)
        assert sha(control_path) == meta["formula_sha256"]
        control_path.unlink()
        header = raw.splitlines()[0].decode().split()
        assert header == ["p", "cnf", str(meta["variables"]),
                          str(meta["cnf_clauses"]+meta["xor_rows"])]
        receipt = json.loads((HERE / f"w{weight}.json").read_text())
        assert receipt["proposal_id"] == frozen["proposal_id"]
        assert receipt["curve_id"] == frozen["curve_id"]
        assert receipt["workload_id"] == frozen["workload_id"]
        assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
        assert receipt["prepare_sha256"] == sha(HERE / "prepare.json")
        assert receipt["formula_archive_sha256"] == sha(archive)
        if weight == 5:
            assert receipt["actual_usable_points_B"] == 30977592
            assert receipt["folded_columns_K"] == 186612
            assert receipt["factor_base_enumerated_set_sha256"] == frozen[
                "weight5_enumerated_set_sha256"]
        else:
            assert receipt["actual_usable_points_B"] is None
            assert receipt["folded_columns_K"] is None
            assert receipt["factor_base_enumerated_set_sha256"] is None
        stdout_archive = HERE / f"w{weight}.stdout.gz"
        stderr_archive = HERE / f"w{weight}.stderr.gz"
        assert sha(stdout_archive) == receipt["stdout_archive_sha256"]
        assert sha(stderr_archive) == receipt["stderr_archive_sha256"]
        output = gzip.decompress(stdout_archive.read_bytes()).decode(errors="replace")
        gzip.decompress(stderr_archive.read_bytes())
        conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", output)
        assert receipt["last_reported_conflicts"] == (
            int(conflicts[-1]) if conflicts else None)
        status = {10: "SAT", 20: "UNSAT"}.get(receipt["exit_code"],
                                                  "BOUNDED_UNKNOWN")
        assert receipt["status"] == status
        model = parsed_model(output)
        relation = None
        if status == "SAT":
            assert model is not None and receipt["relation"] is not None
            shape = check_serialized_xcnf(raw, model)
            assert shape == {"variables": meta["variables"],
                             "cnf_clauses": meta["cnf_clauses"],
                             "xor_rows": meta["xor_rows"]}
            relation = audit_relation(frozen, meta, weight, model)
            assert relation["selected_target_index"] == receipt[
                "relation"]["selected_target_index"]
            assert relation["leaf_x_coords"] == receipt[
                "relation"]["leaf_x_coords"]
        else:
            assert model is None and receipt["relation"] is None
        rows.append({"weight": weight, "status": status,
                     "last_reported_conflicts": receipt[
                         "last_reported_conflicts"],
                     "verified_relation": relation})
    result = {"status": "PASS", "proposal_id": frozen["proposal_id"],
              "auditor_source_sha256": sha(__file__),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "prepare_sha256": sha(HERE / "prepare.json"), "rows": rows}
    output_path = HERE / "audit.json"
    assert not output_path.exists()
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps([{"weight": row["weight"], "status": row["status"],
                      "relation": row["verified_relation"] is not None}
                      for row in rows]))


if __name__ == "__main__":
    main()
