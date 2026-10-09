#!/usr/bin/env python3
"""Independent Sage audit of a d13/m12 ordinary-public-Q diagnostic result."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
GOAL = HERE.parents[1]
OFFICIAL = GOAL / "n131_w2_m15_official_single_target_4g_r3_20261004"
N = 131
VERIFIER_DIR = HERE.parent / "m16_prefix_audit_20261006"
sys.path.insert(0, str(VERIFIER_DIR))
import verify_xcnf_model


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sage_field(params, bridge):
    polynomial_bits = int(params["curve"]["polynomial"], 16)
    ring = PolynomialRing(GF(2), "z")
    modulus = ring([polynomial_bits >> bit & 1 for bit in range(N + 1)])
    binary = GF(2**N, name="z", modulus=modulus)
    zeta = binary.multiplicative_generator() ** ((2**N - 1) // 263)
    if zeta**263 != 1 or zeta == 1:
        raise ValueError("ONB root construction failed")
    basis = [zeta**index + zeta**(263 - index) for index in range(1, N + 1)]

    def onb(mask):
        value = binary(0)
        for bit, element in enumerate(basis):
            if (int(mask) >> bit) & 1:
                value += element
        return value

    root = onb(int(params["curve"]["onb_root"], 16))
    if sum(binary((polynomial_bits >> bit) & 1) * root**bit
           for bit in range(N + 1)) != 0:
        raise ValueError("ONB/polynomial bridge failed")

    def polynomial_element(encoded):
        mask = int(encoded, 16)
        return sum(binary((mask >> bit) & 1) * root**bit
                   for bit in range(N))

    official_q = [onb(value) for value in bridge["official_target_onb_coordinates"]]
    if official_q != [polynomial_element(params["targets"][0][axis])
                      for axis in ("x", "y")]:
        raise ValueError("official Q embedding disagrees with published coordinates")
    return binary, onb, official_q


def verify_rows(result, geometry, params, bridge,
                target_coords=None, fiber_coords=None):
    binary, onb, official_q = sage_field(params, bridge)
    curve = EllipticCurve(binary, [1, 0, 0, 0, 1])
    zero = curve(0)
    target = curve(*official_q) if target_coords is None else curve(
        *[onb(value) for value in target_coords])
    subgroup_order = int(params["curve"]["subgroup_order"])
    if (target == zero or 4 * target == zero or
            subgroup_order * (4 * target) != zero or
            (target_coords is None and subgroup_order * target != zero)):
        raise ValueError("target projection is outside the declared subgroup")
    if fiber_coords is None:
        fiber_coords = [item["target_coordinates"] for item in
                        geometry["official_single_target_cofactor_fiber"]["four_verified_lifts"]]
    fiber = [curve(*[onb(value) for value in item]) for item in fiber_coords]
    if fiber[0] != target or any(4 * point != 4 * target for point in fiber):
        raise ValueError("official Q cofactor fiber failed Sage replay")

    def phi(point):
        if point == zero or point[0] == 1:
            raise ValueError("nonfinite phi coordinate")
        return 1 / (point[0] + 1)

    basis = [int(value, 16)
             for value in geometry["domain"]["basis_coordinate_masks_hex"]]
    if len(basis) != 13:
        raise ValueError("d13 base dimension changed")
    decoded_rows = result["decoded_rows"]
    attempt = next((item for item in result["attempts"]
                    if item.get("local_curve_replay_passed") is True), None)
    if attempt is None or attempt.get("decoded_rows") != decoded_rows:
        raise ValueError("decoded rows have no matching SAT attempt")
    primary = attempt["decoded_primary"]
    codes = primary["leaf_codes"]
    partials = primary["partial_phi_masks"]
    endpoint_index = primary["endpoint_index"]
    if len(codes) != 12 or len(partials) != 10 or endpoint_index not in range(4):
        raise ValueError("wrong d13/m12 decoded-primary shape")
    endpoint = fiber[endpoint_index]
    checked = []
    for row in decoded_rows:
        sign = int(row["rhs_sign"])
        if sign not in (-1, 1) or len(row["signed_points"]) != 12:
            raise ValueError("wrong signed-row shape")
        points = [curve(*[onb(value) for value in coordinates])
                  for coordinates in row["signed_points"]]
        total = zero
        for position, (code, point) in enumerate(zip(codes, points)):
            if not 0 <= int(code) < 1 << 13:
                raise ValueError("leaf code outside 13-bit domain")
            mask = 0
            for bit, vector in enumerate(basis):
                if (int(code) >> bit) & 1:
                    mask ^= vector
            if phi(point) != onb(mask) ** (1 << position):
                raise ValueError("Sage leaf phi differs from SAT selector")
            projected = 4 * point
            if projected == zero or subgroup_order * projected != zero:
                raise ValueError("Sage leaf projection outside subgroup")
            total += point
            if 1 <= position < 11 and phi(total) != onb(partials[position - 1]):
                raise ValueError("Sage partial chain differs from SAT model")
        rhs = endpoint if sign == 1 else -endpoint
        if total != rhs:
            raise ValueError("Sage signed leaf sum misses selected endpoint")
        leaf_orbits = set()
        for point in points:
            current = 4 * point
            for _ in range(N):
                leaf_orbits.add(current)
                leaf_orbits.add(-current)
                current = curve(current[0]**2, current[1]**2)
        folded = zero
        for term in row["folded_terms"]:
            representative = curve(*[onb(value) for value in term["point"]])
            if representative == zero or subgroup_order * representative != zero:
                raise ValueError("Sage folded representative outside subgroup")
            if representative not in leaf_orbits:
                raise ValueError("folded representative is outside witness leaf orbits")
            folded += int(term["coefficient"]) * representative
        if folded != 4 * rhs:
            raise ValueError("Sage folded row misses four times selected endpoint")
        checked.append({"rhs_sign": sign,
                        "leaf_count": len(points),
                        "folded_support": len(row["folded_terms"])})
    return checked


def formula_records(path):
    with Path(path).open("rt", encoding="ascii") as stream:
        return [line.strip() for line in stream
                if line.strip() and not line.startswith(("c", "p "))]


def verify_saved_model(run_dir, result, attempt):
    index = int(attempt["index"])
    attempt_dir = run_dir / "attempts" / ("model_%02d" % index)
    formula_path = attempt_dir / "query.xcnf"
    stdout_path = attempt_dir / "cryptominisat.stdout.txt"
    model_path = attempt_dir / "model_literals.json"
    for path in (formula_path, stdout_path, model_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if attempt["formula_sha256"] != sha(formula_path):
        raise ValueError("solver formula digest differs from attempt record")
    frozen_formula = HERE / "official_q_phi_fiber_d13_m12_v1.xcnf"
    base = formula_records(frozen_formula)
    actual = formula_records(formula_path)
    if actual[:len(base)] != base or len(actual) != len(base) + index - 1:
        raise ValueError("solver input does not preserve all frozen Q constraints")
    check = verify_xcnf_model.verify(formula_path, stdout_path)
    assignment = verify_xcnf_model.model_from_stdout(
        stdout_path, check["variables"])
    saved = json.loads(model_path.read_text())
    observed = {}
    for literal in saved:
        variable = abs(int(literal))
        if not 1 <= variable <= check["variables"]:
            raise ValueError("saved model literal outside formula")
        value = literal > 0
        if variable in observed and observed[variable] != value:
            raise ValueError("saved model contains contradictory literals")
        observed[variable] = value
    if len(observed) != check["variables"] or any(
            observed[variable] != assignment[variable]
            for variable in range(1, check["variables"] + 1)):
        raise ValueError("saved model differs from CryptoMiniSat stdout")
    if attempt.get("decoded_rows") != result["decoded_rows"]:
        raise ValueError("decoded relation is not bound to the SAT attempt")
    return check, {path.name: sha(path) for path in
                   (formula_path, stdout_path, model_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.parent != (HERE / "public_q_runs").resolve():
        parser.error("run directory must be a direct d13/m12 public-Q run")
    output = run_dir / "independent_sage_replay.json"
    if output.exists():
        raise FileExistsError("preserve prior independent replay receipt")
    result_path = run_dir / "result.json"
    geometry_path = HERE.parent / "m12_d13_static/d13_exact_geometry_v1.json"
    params_path = OFFICIAL / "official_fixed_parameters.json"
    bridge_path = OFFICIAL / "bridge_audit.json"
    formula_receipt_path = HERE / "d13_m12_formula_and_planted_control_v1.json"
    frozen_formula = HERE / "official_q_phi_fiber_d13_m12_v1.xcnf"
    protocol_path = HERE / "public_q_first_relation_protocol_v3.json"
    runtime_path = run_dir / "sage_runtime_info.json"
    for path in (result_path, geometry_path, params_path, bridge_path,
                 formula_receipt_path, frozen_formula, protocol_path, runtime_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    result = json.loads(result_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    params = json.loads(params_path.read_text())
    bridge = json.loads(bridge_path.read_text())
    receipt = json.loads(formula_receipt_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    runner = HERE / "run_public_q_first_relation_v3.py"
    if (result.get("workload_id") != geometry["workload_id"] or
            result.get("curve_id") != geometry["curve_id"] or
            result.get("target_count") != 1 or
            result.get("proposal_id") != "Q20261006081500" or
            protocol.get("proposal_id") != result["proposal_id"] or
            result.get("protocol_sha256") != sha(protocol_path) or
            result.get("source_sha256") != sha(runner) or
            result.get("formula_sha256") != receipt["formula_file"]["sha256"] or
            result["formula_sha256"] != sha(frozen_formula) or
            bridge["status"] != "PASS"):
        raise ValueError("d13/m12 result identity or resource envelope failed")
    rss_ok = max(result.get("peak_combined_rss_bytes") or 0,
                 result.get("conservative_peak_rss_bytes") or 0) <= result["rss_limit_bytes"]
    checked = []
    xcnf_check = None
    attempt_hashes = None
    if result.get("decoded_rows") and rss_ok:
        attempt = next((item for item in result["attempts"]
                        if item.get("local_curve_replay_passed") is True and
                        item.get("decoded_rows") == result["decoded_rows"]), None)
        if attempt is None:
            raise ValueError("no matching saved SAT model for decoded rows")
        xcnf_check, attempt_hashes = verify_saved_model(run_dir, result, attempt)
        checked = verify_rows(result, geometry, params, bridge)
        status = "PASS" if checked else "NO_RELATION_RECORDED"
    elif result.get("decoded_rows"):
        status = "OUTSIDE_RESOURCE_ENVELOPE"
    else:
        status = "NO_RELATION_RECORDED"
    audit = {
        "kind": "ecc2k130_n131_d13_m12_public_q_first_relation_independent_sage_audit_v1",
        "status": status, "curve_id": geometry["curve_id"],
        "workload_id": geometry["workload_id"], "target_count": 1,
        "proposal_id": result["proposal_id"],
        "candidate_id": None, "run_id": None,
        "verified_model_count": int(status == "PASS"),
        "verified_sign_options": len(checked),
        "verified_rows": checked,
        "rss_gate_passed": rss_ok,
        "saved_xcnf_assignment_check": xcnf_check,
        "attempt_artifact_sha256": attempt_hashes,
        "claim_boundary": "one ordinary-Q relation diagnostic only; no factor logs, DLP, rho, or speedup",
        "input_sha256": {path.name: sha(path) for path in
                         (result_path, geometry_path, params_path, bridge_path,
                         formula_receipt_path, frozen_formula, protocol_path,
                         runtime_path)},
        "xcnf_verifier_source_sha256": sha(VERIFIER_DIR / "verify_xcnf_model.py"),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "verified_model_count": int(status == "PASS"),
                      "receipt": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
