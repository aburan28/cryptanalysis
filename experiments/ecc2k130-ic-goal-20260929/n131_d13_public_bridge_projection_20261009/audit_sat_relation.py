#!/usr/bin/env python3
"""Lift a projected public-Q SAT model and replay its factor-base row."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
DOMAIN = GOAL / "n131_phi_torsion_frobenius_domains_20261005"
SOURCE = DOMAIN / "d13_m12_probe"
OFFICIAL = GOAL / "n131_w2_m15_official_single_target_4g_r3_20261004"
RUN = HERE / "public_q_stage_R1"
PROJECTION = HERE / "budget1"
BRIDGE_FORMULA = HERE / "bridge_cnf/bridge_cnf.xcnf"
ORIGINAL = SOURCE / "official_q_phi_fiber_d13_m12_v1.xcnf"

sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(DOMAIN / "m16_prefix_audit_20261006"))
import run_public_q_first_relation as original_runner
import audit_public_q_first_relation as independent_sage
import verify_xcnf_model as xcnf


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def lift(assignment, mapping, rows_path, original_n):
    values = [None] * (original_n + 1)
    new_to_old = mapping["new_to_old"]
    if len(new_to_old) != len(assignment) or mapping["free_private"]:
        raise ValueError("unexpected projected variable map")
    for new, old in enumerate(new_to_old[1:], 1):
        values[old] = assignment[new]
    rows = [json.loads(line) for line in rows_path.open()]
    for row in reversed(rows):
        pivot = row["pivot"]
        if values[pivot] is not None:
            raise ValueError("lift pivot already assigned")
        parity = row["rhs"]
        for variable in row["variables"]:
            if variable == pivot:
                continue
            if values[variable] is None:
                raise ValueError("lift dependency out of reverse order")
            parity ^= values[variable]
        values[pivot] = bool(parity)
    if any(value is None for value in values[1:]):
        raise ValueError("lift omitted an original variable")
    return values


def save_full_model(path, values):
    with path.open("wt", encoding="ascii") as stream:
        stream.write("s SATISFIABLE\n")
        for first in range(1, len(values), 1000):
            last = min(len(values), first + 1000)
            stream.write("v " + " ".join(str(variable if values[variable]
                                                 else -variable)
                                         for variable in range(first, last)) + " 0\n")


def replay_relation(model_literals):
    runner = original_runner
    runner.gate.DIM, runner.gate.M = 13, 12
    runner.decoder.DIM, runner.decoder.LEAVES = 13, 12
    onb = runner.field.Onb(131)
    curve = runner.curves.Curve(onb)
    geometry = json.loads(runner.GEOMETRY.read_text())
    manifest = json.loads((OFFICIAL / "candidate_manifest.json").read_text())
    workload = json.loads((OFFICIAL / "workload.json").read_text())
    record = manifest["candidate_record"]["curve"]
    order = int(record["subgroup_order"])
    generator = tuple(onb.fromCoords(int(value)) for value in record["generator"])
    eigenvalue = runner.curves.frobeniusEigenvalue(curve, generator, order)
    basis = [int(value, 16) for value in geometry["domain"]["basis_coordinate_masks_hex"]]
    valid_codes = []
    for mask, code in runner.gate.span_with_coefficients(basis):
        if mask:
            point = curve.pointFromX(onb.add(onb.inv(onb.fromCoords(mask)), onb.one()))
            if point is not None and curve.mul(point, 4) is not None:
                valid_codes.append(code)
    valid_codes.sort()
    if len(valid_codes) != 4134:
        raise ValueError("selector count changed")
    target_fiber = [tuple(onb.fromCoords(int(value)) for value in
                          item["target_coordinates"])
                    for item in geometry["official_single_target_cofactor_fiber"]["four_verified_lifts"]]
    if [onb.toCoords(value) for value in target_fiber[0]] != workload["targets"][0]:
        raise ValueError("public target changed")
    target_phi = [int(item["phi_coordinate"]) for item in
                  geometry["official_single_target_cofactor_fiber"]["four_verified_lifts"]]
    formula, primary, roots, *_ = runner.gate.build_formula(onb, basis, valid_codes,
                                                             target_phi)
    rebuilt = RUN / "rebuilt_original_public_q.xcnf"
    formula.writeDimacs(rebuilt)
    if sha(rebuilt) != sha(ORIGINAL) or len(roots) != 1441:
        raise ValueError("reconstructed public-Q formula differs from frozen bytes")
    codes, partials, endpoint = runner.decoder.decode_primary(model_literals, primary)
    rows = runner.decoder.verify_model(onb, curve, basis, valid_codes,
                                       model_literals, target_fiber, order,
                                       eigenvalue, primary)
    if not rows:
        raise ValueError("SAT model has no signed group relation")
    row_result = {"decoded_rows": rows,
                  "attempts": [{"local_curve_replay_passed": True,
                                "decoded_rows": rows,
                                "decoded_primary": {
                                    "leaf_codes": codes,
                                    "partial_phi_masks": partials,
                                    "endpoint_index": endpoint}}]}
    params = json.loads((OFFICIAL / "official_fixed_parameters.json").read_text())
    bridge = json.loads((OFFICIAL / "bridge_audit.json").read_text())
    checked = independent_sage.verify_rows(row_result, geometry, params, bridge)
    if len(checked) != len(rows):
        raise ValueError("independent Sage replay did not cover every decoded row")
    return row_result, checked, sha(rebuilt)


def main():
    output = RUN / "independent_sat_relation_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "solver_protocol.json").read_text())
    result = json.loads((RUN / "result.json").read_text())
    terminal = json.loads((RUN / "independent_terminal_audit.json").read_text())
    projection = json.loads((PROJECTION / "result.json").read_text())
    stdout = RUN / "cryptominisat.stdout.txt"
    if (terminal["status"] != "SAT_MODEL_REQUIRES_INDEPENDENT_RELATION_AUDIT" or
            result["status"] != "SAT_MODEL_REQUIRES_INDEPENDENT_AUDIT" or
            result["proposal_id"] != protocol["proposal_id"] or
            result["source_sha256"]["stdout"] != sha(stdout) or
            protocol["source_sha256"]["raw"] != sha(ORIGINAL) or
            protocol["source_sha256"]["bridge"] != sha(BRIDGE_FORMULA)):
        raise ValueError("SAT stage identity or terminal status failed")
    projected_check = xcnf.verify(PROJECTION / "projected.xcnf", stdout)
    assignment = xcnf.model_from_stdout(stdout, projected_check["variables"])
    mapping = json.loads((PROJECTION / "variable_map.json").read_text())
    full = lift(assignment, mapping, PROJECTION / "lift_rows.jsonl",
                projection["original_variables"])
    lifted_stdout = RUN / "lifted_bridge_model.stdout.txt"
    save_full_model(lifted_stdout, full)
    bridge_check = xcnf.verify(BRIDGE_FORMULA, lifted_stdout)
    original_check = xcnf.verify(ORIGINAL, lifted_stdout)
    literals = [variable if full[variable] else -variable
                for variable in range(1, len(full))]
    row_result, checked, rebuilt_sha = replay_relation(literals)
    receipt = {
        "kind": "n131_d13_m12_bridge_projected_public_q_independent_sat_relation_audit",
        "status": "PASS",
        "proposal_id": protocol["proposal_id"],
        "projected_model_check": projected_check,
        "lifted_bridge_model_check": bridge_check,
        "lifted_original_model_check": original_check,
        "decoded_primary": row_result["attempts"][0]["decoded_primary"],
        "decoded_rows": row_result["decoded_rows"],
        "independent_sage_row_checks": checked,
        "source_sha256": {"projected_formula": sha(PROJECTION / "projected.xcnf"),
                          "bridge_formula": sha(BRIDGE_FORMULA),
                          "original_formula": sha(ORIGINAL),
                          "rebuilt_original_formula": rebuilt_sha,
                          "solver_stdout": sha(stdout),
                          "lifted_model": sha(lifted_stdout),
                          "terminal_audit": sha(RUN / "independent_terminal_audit.json"),
                          "audit_script": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "decoded_rows": len(checked)}))


if __name__ == "__main__":
    main()
