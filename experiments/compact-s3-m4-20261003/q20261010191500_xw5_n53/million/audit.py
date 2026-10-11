#!/usr/bin/env python3
"""Audit million-conflict stream and replay any SAT model on the curve."""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
GRAND = PARENT.parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(GRAND / "q1419_partial_pin"), str(GRAND),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen = json.loads((HERE / "freeze.json").read_text())
    run = json.loads((HERE / "run.json").read_text())
    parent = json.loads((PARENT / "freeze.json").read_text())
    prepared = json.loads((PARENT / "prepare.json").read_text())
    assert run["freeze_sha256"] == sha(HERE / "freeze.json")
    assert frozen["workload_id"] == run["workload_id"] == "74f2979b3e68"
    assert frozen["curve_id"] == run["curve_id"] == (
        "EC1N53Ckb1hf77aab617904")
    assert frozen["isogeny"] == run["isogeny"] == "none"
    for name, value in frozen["source_sha256"].items():
        assert sha(HERE / name) == value
    for name, value in frozen["parent_sha256"].items():
        assert sha(PARENT / name) == value
    assert sha(frozen["solver_path"]) == frozen["solver_sha256"]
    raw = gzip.decompress((PARENT / "formula.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    stdout = HERE / "solver.stdout.gz"
    stderr = HERE / "solver.stderr.gz"
    assert sha(stdout) == run["stdout_archive_sha256"]
    assert sha(stderr) == run["stderr_archive_sha256"]
    output = gzip.decompress(stdout.read_bytes()).decode(errors="replace")
    gzip.decompress(stderr.read_bytes())
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", output)
    assert run["last_reported_conflicts"] == (
        int(conflicts[-1]) if conflicts else None)
    status = {10: "SAT", 20: "UNSAT"}.get(run["exit_code"],
                                              "BOUNDED_UNKNOWN")
    assert status == run["status"]
    model = parsed_model(output)
    relation = None
    if status == "SAT":
        assert model is not None
        formula = check_serialized_xcnf(raw, model)
        assert formula == {"variables": prepared["variables"],
                           "cnf_clauses": prepared["cnf_clauses"],
                           "xor_rows": prepared["xor_rows"]}
        choice = decode_choice(prepared["selector"], model)
        coset = json.loads((GRAND / "runs/n53_ordinary_raw_preimages.json").read_text())
        coords = [sum(1 << i for i, bit in enumerate(row) if model[bit])
                  for row in prepared["leaves"]]
        assert all(0 < x < (1 << 53) and x.bit_count() <= 5 for x in coords)
        onb = field.Onb(53)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x)) for x in coords]
        assert all(point is not None for point in points)
        raw_point = tuple(map(int, coset["raw_target_points"][choice]))
        public = tuple(map(int, parent["public_target"]))
        import itertools
        for signs in itertools.product((1, -1), repeat=4):
            total = None
            for point, sign in zip(points, signs):
                total = curve.add(total, point if sign == 1 else curve.neg(point))
            if total == raw_point:
                projected = [curve.mul(point, parent["cofactor"])
                             for point in points]
                assert all(point is not None and curve.mul(point,
                    parent["subgroup_order_r"]) is None for point in projected)
                assert curve.mul(total, parent["cofactor"]) == public
                relation = {"selected_target_index": choice,
                            "leaf_x_coords": coords,
                            "signs": signs,
                            "projected_points": [[str(x) for x in point]
                                                 for point in projected]}
                break
        assert relation is not None
    else:
        assert model is None
    result = {"status": "PASS", "proposal_id": frozen["proposal_id"],
              "run_sha256": sha(HERE / "run.json"),
              "auditor_source_sha256": sha(__file__),
              "solver_status": status, "verified_relation": relation}
    path = HERE / "audit.json"
    assert not path.exists()
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"audit": "PASS", "solver_status": status,
                      "verified_relation": relation is not None}))


if __name__ == "__main__":
    main()
