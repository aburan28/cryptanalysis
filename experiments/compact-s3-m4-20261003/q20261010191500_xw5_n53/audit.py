#!/usr/bin/env python3
"""Audit the frozen N53 weight-five formula, solver stream, and SAT relation."""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen = json.loads((HERE / "freeze.json").read_text())
    prepared = json.loads((HERE / "prepare.json").read_text())
    run = json.loads((HERE / "run.json").read_text())
    assert frozen["curve_id"] == run["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert frozen["workload_id"] == run["workload_id"] == "74f2979b3e68"
    assert frozen["candidate_id"] is run["candidate_id"] is None
    assert frozen["isogeny"] == run["isogeny"] == "none"
    assert sha(HERE / "freeze.json") == prepared["freeze_sha256"] == run[
        "freeze_sha256"]
    assert sha(HERE / "prepare.json") == run["prepare_sha256"]
    for name, value in frozen["source_sha256"].items():
        assert sha(HERE / name) == value
    for name, value in frozen["input_sha256"].items():
        assert sha(ROOT / name) == value
    assert sha(frozen["solver_path"]) == frozen["solver_sha256"]
    archive = HERE / "formula.xcnf.gz"
    assert sha(archive) == prepared["formula_archive_sha256"] == run[
        "formula_archive_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == prepared["formula_sha256"]
    out_archive = HERE / "solver.stdout.gz"
    err_archive = HERE / "solver.stderr.gz"
    assert sha(out_archive) == run["stdout_archive_sha256"]
    assert sha(err_archive) == run["stderr_archive_sha256"]
    output = gzip.decompress(out_archive.read_bytes()).decode(errors="replace")
    gzip.decompress(err_archive.read_bytes())
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", output)
    assert run["last_reported_conflicts"] == (
        int(conflicts[-1]) if conflicts else None)
    status = {10: "SAT", 20: "UNSAT"}.get(run["exit_code"],
                                              "BOUNDED_UNKNOWN")
    assert status == run["status"]
    model = parsed_model(output)
    checked = None
    if status == "SAT":
        assert model is not None and run["relation"] is not None
        checked = check_serialized_xcnf(raw, model)
        assert checked == {"variables": prepared["variables"],
                           "cnf_clauses": prepared["cnf_clauses"],
                           "xor_rows": prepared["xor_rows"]}
        choice = decode_choice(prepared["selector"], model)
        assert choice == run["relation"]["selected_target_index"]
        coset = json.loads((PARENT / "runs/n53_ordinary_raw_preimages.json").read_text())
        coords = [sum(1 << i for i, variable in enumerate(row)
                      if model[variable]) for row in prepared["leaves"]]
        assert coords == run["relation"]["leaf_x_coords"]
        assert all(0 < x < (1 << 53) and x.bit_count() <= 5 for x in coords)
        onb = field.Onb(53)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x)) for x in coords]
        assert all(p is not None for p in points)
        relation = run["relation"]["relation"]
        assert relation["leaf_x_coordinates"] == coords
        total = None
        for point, sign in zip(points, relation["signs"]):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        raw_point = tuple(map(int, coset["raw_target_points"][choice]))
        assert total == raw_point
        assert curve.mul(total, frozen["cofactor"]) == tuple(map(int,
            frozen["public_target"]))
        projected = [curve.mul(point, frozen["cofactor"]) for point in points]
        assert all(p is not None and curve.mul(p, frozen[
            "subgroup_order_r"]) is None for p in projected)
        assert [[str(v) for v in p] for p in projected] == relation[
            "projected_points"]
    else:
        assert model is None and run["relation"] is None
    result = {"status": "PASS", "proposal_id": frozen["proposal_id"],
              "run_sha256": sha(HERE / "run.json"),
              "auditor_source_sha256": sha(__file__),
              "solver_status": status, "model_replay": checked}
    output_path = HERE / "audit.json"
    assert not output_path.exists()
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
