#!/usr/bin/env python3
"""One public-Q d13/m12 relation attempt, gated behind R3 and d10/m15.

This is a diagnostic, not a full IC candidate run. Launch via the checked
repository Sage launcher. A SAT model remains unverified until a separate
installed-Sage auditor checks the saved formula and group row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOMAIN = HERE.parent
GOAL = DOMAIN.parent
ROOT = GOAL.parents[1]
D10 = DOMAIN / "m15_d10_static"
M16 = DOMAIN / "m16_static"
OFFICIAL = GOAL / "n131_w2_m15_official_single_target_4g_r3_20261004"
for directory in (ROOT / "ecc2k130/codegen", M16, D10):
    sys.path.insert(0, str(directory))

import curves
import field
import indexcalc_e2e as e
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as gate
import q1358_exact_model_decoder_m16 as decoder
import continue_d10_after_r3 as predecessor

DIM = 13
LEAVES = 12
LIMIT_SECONDS = 600.0
RSS_LIMIT = 4 * 1024**3
MAX_MODELS = 4
SEED = 202610061312
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
PROPOSAL_ID = "Q20261006081500"
PROTOCOL = HERE / "public_q_first_relation_protocol_v3.json"
AUDITOR_CONTROL = HERE / "sage_public_q_auditor_planted_control_v4.json"
XCNF_VERIFIER = DOMAIN / "m16_prefix_audit_20261006/verify_xcnf_model.py"
GEOMETRY = DOMAIN / "m12_d13_static/d13_exact_geometry_v1.json"
RECEIPT = HERE / "d13_m12_formula_and_planted_control_v1.json"
FORMULA = HERE / "official_q_phi_fiber_d13_m12_v1.xcnf"
SAGE_REPLAY = HERE / "sage_d13_planted_relation_audit_v1.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def d10_gate():
    state_path = D10 / "continuation/state.json"
    if not state_path.is_file():
        return {"status": "WAIT_FOR_D10_STATE"}
    state = json.loads(state_path.read_text())
    protocol = json.loads((D10 / "d10_m15_single_target_protocol_v1.json").read_text())
    if (state.get("candidate_id") != protocol["candidate_id"] or
            state.get("target_count") != 1 or state.get("batch") is not False):
        return {"status": "WAIT_FOR_D10_IDENTITY", "state": state.get("status")}
    run_id = "%sW%sR%d" % (protocol["candidate_id"], protocol["workload_id"],
                            protocol["run_control"]["run_number"])
    run_dir = D10 / "single_target_runs" / run_id
    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text()) if result_path.is_file() else {}
    if state.get("status") == "D10_DLP_VERIFIED_RHO_PAIR_REQUIRED":
        return {"status": "STOP_D10_DLP_VERIFIED", "run_id": run_id}
    if (state.get("status") != "D10_M15_TERMINAL_WITHOUT_VERIFIED_DLP" or
            result.get("run_id") != run_id or result.get("target_count") != 1 or
            not isinstance(result.get("status"), str) or
            result["status"].startswith("RUNNING")):
        return {"status": "WAIT_FOR_D10_TERMINAL_RESULT",
                "state": state.get("status"), "run_id": run_id}
    return {"status": "READY", "run_id": run_id,
            "result_sha256": sha(result_path), "result_status": result["status"]}


def preflight():
    needed = (GEOMETRY, RECEIPT, FORMULA, SAGE_REPLAY, SOLVER, PROTOCOL,
              AUDITOR_CONTROL, XCNF_VERIFIER,
              OFFICIAL / "workload.json", OFFICIAL / "candidate_manifest.json")
    for path in needed:
        if not path.is_file():
            raise FileNotFoundError(path)
    geometry = json.loads(GEOMETRY.read_text())
    receipt = json.loads(RECEIPT.read_text())
    replay = json.loads(SAGE_REPLAY.read_text())
    control = json.loads(AUDITOR_CONTROL.read_text())
    workload = json.loads((OFFICIAL / "workload.json").read_text())
    protocol = json.loads(PROTOCOL.read_text())
    if not (geometry["status"] == receipt["status"] == replay["status"] == "PASS" and
            geometry["curve_id"] == receipt["curve_id"] == replay["curve_id"] and
            geometry["workload_id"] == receipt["workload_id"] ==
            replay["workload_id"] == workload["workload_id"] and
            workload["target_count"] == receipt["target_count"] == 1 and
            receipt["subspace_dimension"] == DIM and receipt["summand_count"] == LEAVES and
            receipt["valid_phi_selectors_per_position"] == 4134 and
            receipt["formula_file"]["sha256"] == sha(FORMULA) and
            receipt["source_sha256"] == sha(HERE / "build_d13_m12_formula.py") and
            replay["source_sha256"] == sha(HERE / "sage_replay_d13_planted_relation.py") and
            replay["input_sha256"]["formula_receipt"] == sha(RECEIPT)):
        raise ValueError("d13/m12 formula, workload, or planted controls changed")
    if (control.get("status") != "PASS" or
            control.get("proposal_id") != PROPOSAL_ID or
            control.get("auditor_source_sha256") !=
            sha(HERE / "audit_public_q_first_relation.py") or
            control.get("tampered_leaf_rejected") is not True or
            control.get("tampered_coefficient_rejected") is not True):
        raise ValueError("independent d13/m12 auditor control changed")
    expected = protocol["sha256"]
    bindings = {
        "runner": Path(__file__),
        "auditor": HERE / "audit_public_q_first_relation_v3.py",
        "auditor_control": AUDITOR_CONTROL,
        "xcnf_verifier": XCNF_VERIFIER,
        "formula": FORMULA,
        "formula_receipt": RECEIPT,
        "geometry": GEOMETRY,
        "sage_planted_replay": SAGE_REPLAY,
        "formula_gate": M16 / "phi_frobenius_sat_gate_m16_sparse_seed_v1.py",
        "decoder": M16 / "q1358_exact_model_decoder_m16.py",
        "workload": OFFICIAL / "workload.json",
        "manifest": OFFICIAL / "candidate_manifest.json",
        "solver": SOLVER,
    }
    if (protocol.get("proposal_id") != PROPOSAL_ID or
            protocol.get("candidate_id") is not None or
            protocol.get("run_id") is not None or
            protocol.get("target_count") != 1 or
            protocol.get("workload_id") != workload["workload_id"] or
            protocol.get("curve_id") != geometry["curve_id"] or
            protocol.get("resource_limit_seconds") != LIMIT_SECONDS or
            protocol.get("rss_limit_bytes") != RSS_LIMIT or
            protocol.get("max_models") != MAX_MODELS or
            any(expected.get(name) != sha(path) for name, path in bindings.items())):
        raise ValueError("d13/m12 proposal protocol or source binding changed")
    r3 = predecessor.r3_status()
    if r3["status"] != "READY":
        status = r3["status"]
        d10 = {"status": "NOT_CHECKED"}
    elif r3["target_discrete_log_recovered"]:
        status = "STOP_R3_DLP_VERIFIED"
        d10 = {"status": "NOT_CHECKED"}
    else:
        d10 = d10_gate()
        status = d10["status"]
    return {"status": status, "r3_gate": r3, "d10_gate": d10,
            "curve_id": geometry["curve_id"], "workload_id": workload["workload_id"],
            "target_count": 1, "proposal_id": PROPOSAL_ID,
            "candidate_id": None, "run_id": None,
            "protocol_sha256": sha(PROTOCOL),
            "formula_sha256": sha(FORMULA), "formula_receipt_sha256": sha(RECEIPT),
            "geometry_sha256": sha(GEOMETRY), "sage_planted_replay_sha256": sha(SAGE_REPLAY),
            "solver_sha256": sha(SOLVER), "source_sha256": sha(Path(__file__)),
            "resource_limit_seconds": LIMIT_SECONDS, "rss_limit_bytes": RSS_LIMIT,
            "claim_boundary": "public-Q first-relation proposal; no DLP or speedup"}


def solver_environment(attempt_dir, seed):
    os.environ.update({
        "IC_CMS_CLI_BIN": str(SOLVER),
        "IC_CMS_CLI_FORMULA": str(attempt_dir / "query.xcnf"),
        "IC_CMS_CLI_STDOUT": str(attempt_dir / "cryptominisat.stdout.txt"),
        "IC_CMS_CLI_STDERR": str(attempt_dir / "cryptominisat.stderr.txt"),
        "IC_CMS_CLI_PIDFILE": str(attempt_dir / "cryptominisat.pid"),
        "IC_CMS_CLI_SEED": str(seed),
        "IC_CMS_CLI_RSS_LIMIT_BYTES": str(RSS_LIMIT),
        "IC_CMS_CLI_MAX_MATRIX_ROWS": "10000",
        "IC_CMS_CLI_MAX_MATRIX_COLS": "15000",
        "IC_CMS_CLI_MAX_NUM_MATRICES": "10",
    })


def block_primary(formula, primary, model_literals):
    model = {abs(lit): lit > 0 for lit in model_literals if lit}
    clause = []
    for variables in primary.values():
        for variable in variables:
            if variable not in model:
                raise ValueError("SAT model omitted a primary variable")
            clause.append(-variable if model[variable] else variable)
    formula.addClause(clause)


def run(pre):
    # All target-independent setup stays outside the partial query clock.
    gate.DIM, gate.M = DIM, LEAVES
    decoder.DIM, decoder.LEAVES = DIM, LEAVES
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    geometry = json.loads(GEOMETRY.read_text())
    receipt = json.loads(RECEIPT.read_text())
    manifest = json.loads((OFFICIAL / "candidate_manifest.json").read_text())
    workload = json.loads((OFFICIAL / "workload.json").read_text())
    curve_record = manifest["candidate_record"]["curve"]
    order = int(curve_record["subgroup_order"])
    generator = tuple(onb.fromCoords(int(value)) for value in curve_record["generator"])
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    basis = [int(value, 16) for value in geometry["domain"]["basis_coordinate_masks_hex"]]
    valid_codes = []
    for mask, code in gate.span_with_coefficients(basis):
        if mask:
            point = curve.pointFromX(onb.add(onb.inv(onb.fromCoords(mask)), onb.one()))
            if point is not None and curve.mul(point, 4) is not None:
                valid_codes.append(code)
    valid_codes.sort()
    if len(valid_codes) != 4134:
        raise ValueError("exact d13 selector count changed")
    run_dir = HERE / "public_q_runs" / ("d13_m12_" + stamp())
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_json(run_dir / "started.json", {**pre, "status": "RUNNING", "started_utc": now()})
    from subprocess import run as subprocess_run
    runtime = subprocess_run([str(ROOT / "sage"), "--runtime-info"],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    (run_dir / "sage_runtime_info.json").write_text(runtime.stdout)

    query_start = time.perf_counter_ns()
    deadline = time.monotonic() + LIMIT_SECONDS
    query_ns = solve_ns = check_ns = 0
    attempts = []
    rows = None
    status = "timeout"
    error = None
    peak_solver = peak_combined = 0
    try:
        target_fiber = [tuple(onb.fromCoords(int(value)) for value in
                              item["target_coordinates"])
                        for item in geometry["official_single_target_cofactor_fiber"]["four_verified_lifts"]]
        if [onb.toCoords(value) for value in target_fiber[0]] != [
                int(value) for value in workload["targets"][0]]:
            raise ValueError("official Q or cofactor fiber changed")
        target_phi = [int(item["phi_coordinate"]) for item in
                      geometry["official_single_target_cofactor_fiber"]["four_verified_lifts"]]
        build_start = time.perf_counter_ns()
        formula, primary, roots, *_ = gate.build_formula(onb, basis, valid_codes, target_phi)
        stats = formula.stats()
        expected = receipt["formula_counts"]
        if (stats["vars"] != expected["variables"] or
                stats["clauses"] != expected["clauses"] or
                stats["xors"] != expected["native_xors"] or
                len(roots) != expected["roots"]):
            raise ValueError("rebuilt public-Q formula counts changed")
        formula.writeDimacs(run_dir / "bound_query.xcnf")
        if sha(run_dir / "bound_query.xcnf") != pre["formula_sha256"]:
            raise ValueError("rebuilt public-Q XCNF bytes changed")
        query_ns += time.perf_counter_ns() - build_start
        for index in range(MAX_MODELS):
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                break
            attempt_dir = run_dir / "attempts" / ("model_%02d" % (index + 1))
            attempt_dir.mkdir(parents=True, exist_ok=False)
            solver_environment(attempt_dir, SEED + index)
            solver = e.CryptoMinisatCli(formula)
            solver.conf_budget(1_000_000_000_000)
            solver.time_budget(remaining)
            started = time.perf_counter_ns()
            solved = solver.solve_limited()
            elapsed = time.perf_counter_ns() - started
            solve_ns += elapsed
            peak_solver = max(peak_solver, solver.max_rss_bytes or 0)
            peak_combined = max(peak_combined, solver.max_total_rss_bytes or 0)
            attempt = {"index": index + 1, "solve_wall_ns": elapsed,
                       "solver_status": "sat" if solved is True else
                       "unsat" if solved is False else "indeterminate",
                       "stop_reason": solver.stop_reason,
                       "exit_code": solver.returncode,
                       "solver_peak_rss_bytes": solver.max_rss_bytes,
                       "combined_peak_rss_bytes": solver.max_total_rss_bytes,
                       "formula_sha256": sha(attempt_dir / "query.xcnf")}
            attempts.append(attempt)
            if index == 0 and attempt["formula_sha256"] != pre["formula_sha256"]:
                raise ValueError("solver input differs from frozen public-Q formula")
            if solved is False:
                status = "unsat"
                break
            if solved is None:
                status = "oom" if solver.stop_reason == "rss_limit" else "timeout"
                break
            checked = time.perf_counter_ns()
            model = solver.get_model()
            atomic_json(attempt_dir / "model_literals.json", model)
            try:
                codes, partials, endpoint = decoder.decode_primary(model, primary)
                attempt["decoded_primary"] = {
                    "leaf_codes": codes, "partial_phi_masks": partials,
                    "endpoint_index": endpoint}
                rows = decoder.verify_model(onb, curve, basis, valid_codes, model,
                                            target_fiber, order, eigenvalue, primary)
                if not rows:
                    raise ValueError("SAT model has no consistent signed group lift")
                attempt["local_curve_replay_passed"] = True
                attempt["decoded_rows"] = rows
                status = "decoded_relation_pending_independent_sage"
            except (ValueError, AssertionError) as rejection:
                attempt["local_curve_replay_passed"] = False
                attempt["model_rejection"] = str(rejection)
                block_primary(formula, primary, model)
                status = "model_rejected"
            check_ns += time.perf_counter_ns() - checked
            if rows:
                break
    except Exception as failure:
        status = "producer_failure"
        error = {"type": type(failure).__name__, "message": str(failure)}
    charged_ns = time.perf_counter_ns() - query_start
    query_ns += max(0, charged_ns - query_ns - solve_ns - check_ns)
    parent_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        parent_peak *= 1024
    conservative_peak = parent_peak + peak_solver
    if max(peak_combined, conservative_peak) > RSS_LIMIT and rows:
        status = "decoded_relation_outside_rss_envelope"
    result = {**pre, "status": status, "finished_utc": now(),
              "attempts": attempts, "decoded_rows": rows,
              "independently_verified_relation_count": 0,
              "independent_sage_replay_status": "PENDING" if rows else None,
              "phase_wall_ns": {"T_target_query": query_ns,
                                "T_target_PDP": solve_ns,
                                "T_target_relation_check": check_ns,
                                "T_target_descent": None,
                                "T_target_recovery_check": None},
              "partial_query_charged_wall_ns": charged_ns,
              "complete_one_target_online_wall_ns": None,
              "rho_online_wall_ns": None, "online_speedup": None,
              "peak_combined_rss_bytes": peak_combined,
              "conservative_peak_rss_bytes": conservative_peak,
              "error": error}
    atomic_json(run_dir / "result.json", result)
    print(json.dumps({"status": status, "run_dir": str(run_dir),
                      "attempts": len(attempts), "error": error}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    pre = preflight()
    if args.preflight_only or pre["status"] != "READY":
        path = HERE / "preflights" / ("d13_m12_" + stamp() + ".json")
        atomic_json(path, pre)
        print(json.dumps({"status": pre["status"], "preflight": str(path),
                          "solver_launched": False}, sort_keys=True))
        return
    run(pre)


if __name__ == "__main__":
    main()
