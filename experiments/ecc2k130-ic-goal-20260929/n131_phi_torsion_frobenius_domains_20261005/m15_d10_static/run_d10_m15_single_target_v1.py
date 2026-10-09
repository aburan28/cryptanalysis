#!/usr/bin/env python3
"""Full single-target IC pipeline for the sparse-seed d10/m15 candidate.

All local Sage launches must use the checked repository launcher.  The runner
fails closed while the frozen W2 R3 solver is live and never launches a
multi-target workload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import resource
import selectors
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parents[1]
ROOT = GOAL.parents[1]
SOURCE_RUN = GOAL / "n131_w2_m15_official_single_target_4g_r3_20261004"
CODEGEN = ROOT / "ecc2k130" / "codegen"
M16_DIR = HERE.parent / "m16_static"
for directory in (CODEGEN, SOURCE_RUN, M16_DIR, HERE):
    sys.path.insert(0, str(directory))

import curves
import field
import indexcalc_e2e as e
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as gate
import q1358_exact_model_decoder_m16 as decoder
import sparse_seed_d10_m15_pipeline as pipeline


MANIFEST = HERE / "d10_m15_candidate_manifest_v1.json"
PROTOCOL = HERE / "d10_m15_single_target_protocol_v1.json"
WORKLOAD = SOURCE_RUN / "workload.json"
CURVE_RECORD = SOURCE_RUN / "field_curve_record.json"
BRIDGE = SOURCE_RUN / "bridge_audit.json"
RUNTIME_INFO = HERE / "sage_runtime_info_d10_candidate.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
MAX_PRECOMPUTE_ATTEMPTS = 256
LEAVES = 15
PRECOMPUTE_QUERY_SECONDS = 604800.0
ONLINE_QUERY_SECONDS = 604800.0
CONFLICT_LIMIT = 1_000_000_000_000
MAX_MODELS_PER_RELATION = 4
RSS_LIMIT_BYTES = 4 * 1024**3
CMS_MATRIX_ROWS = 10000
CMS_MATRIX_COLS = 15000
CMS_NUM_MATRICES = 10


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parent_peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def r3_process_state(run_dir):
    import psutil

    observations = sorted(Path(run_dir).glob("live_process_observation_*.json"))
    if not observations:
        return {"active": None, "reason": "missing process-identity receipt"}
    observation_path = observations[-1]
    observation = json.loads(observation_path.read_text())
    active = False
    uncertain = False
    checked = []
    for item in observation.get("processes", []):
        pid, created = item.get("pid"), item.get("create_time_epoch")
        if pid is None or created is None:
            checked.append({"pid": pid, "identity_incomplete": True})
            uncertain = True
            continue
        try:
            process = psutil.Process(int(pid))
            same = abs(process.create_time() - float(created)) < 0.05
            alive = process.is_running() and process.status() != psutil.STATUS_ZOMBIE
            checked.append({"pid": int(pid), "identity_matches": same,
                            "alive": alive, "active_match": same and alive})
            active |= same and alive
        except psutil.NoSuchProcess:
            checked.append({"pid": int(pid), "alive": False,
                            "active_match": False})
        except psutil.AccessDenied:
            checked.append({"pid": int(pid), "access_denied": True})
            uncertain = True
    if not checked:
        uncertain = True
    return {"active": True if active else None if uncertain else False,
            "receipt": str(observation_path), "checked_processes": checked}


def r3_terminal_gate():
    old_protocol = json.loads((SOURCE_RUN / "protocol.json").read_text())
    old_workload = json.loads(WORKLOAD.read_text())
    run_id = "%sW%sR%d" % (old_protocol["candidate_id"],
                            old_protocol["workload_id"],
                            old_protocol["run_control"]["run_number"])
    run_dir = SOURCE_RUN / "runs" / run_id
    process = r3_process_state(run_dir)
    result_path = run_dir / "result.json"
    if process["active"] is not False:
        status = "WAIT_FOR_R3_DRAIN" if process["active"] else "WAIT_FOR_R3_PROCESS_OBSERVATION"
    elif not result_path.is_file():
        status = "WAIT_FOR_R3_TERMINAL_RECEIPT"
    else:
        result = json.loads(result_path.read_text())
        terminal_status = result.get("status")
        bound = (result.get("run_id") == run_id and
                 result.get("candidate_id") == old_protocol["candidate_id"] and
                 result.get("curve_id") == old_workload["curve_id"] and
                 result.get("workload_id") == old_workload["workload_id"] and
                 result.get("target_count") == 1 and
                 isinstance(terminal_status, str) and terminal_status and
                 not terminal_status.startswith("RUNNING"))
        if not bound:
            status = "WAIT_FOR_R3_TERMINAL_RECEIPT"
        elif (terminal_status == "verified_single_target_dlp" and
              result.get("target_discrete_log_recovered") is True):
            audit_path = run_dir / "independent_sage_scalar_replay.json"
            if not audit_path.is_file():
                status = "R3_DLP_RESULT_REQUIRES_INDEPENDENT_AUDIT"
            else:
                audit = json.loads(audit_path.read_text())
                audit_bound = (
                    audit.get("status") == "PASS_VERIFIED_SINGLE_TARGET_DLP" and
                    audit.get("candidate_id") == old_protocol["candidate_id"] and
                    audit.get("run_id") == run_id and
                    audit.get("curve_id") == old_workload["curve_id"] and
                    audit.get("workload_id") == old_workload["workload_id"] and
                    audit.get("target_count") == 1 and
                    audit.get("batch") is False and
                    audit.get("scalar_replay_passed") is True)
                process["independent_scalar_replay"] = {
                    "path": str(audit_path),
                    "status": audit.get("status"),
                    "bound_to_r3_run": audit_bound,
                }
                status = "READY" if audit_bound else "R3_DLP_INDEPENDENT_AUDIT_FAILED"
        else:
            status = "READY"
    return status, process, result_path


def source_hashes():
    paths = {
        "runner": sha(Path(__file__)),
        "pipeline": sha(HERE / "sparse_seed_d10_m15_pipeline.py"),
        "formula_gate": sha(M16_DIR / "phi_frobenius_sat_gate_m16_sparse_seed_v1.py"),
        "decoder": sha(M16_DIR / "q1358_exact_model_decoder_m16.py"),
        "formula_builder": sha(HERE / "build_d10_m15_formula.py"),
        "geometry_builder": sha(HERE / "audit_d10_geometry.py"),
        "geometry_seed_screen": sha(HERE / "screen_d10_extension.py"),
        "codegen_e2e": sha(CODEGEN / "indexcalc_e2e.py"),
        "codegen_field": sha(CODEGEN / "field.py"),
        "codegen_curves": sha(CODEGEN / "curves.py"),
        "codegen_cnf": sha(CODEGEN / "cnf.py"),
        "codegen_ir": sha(CODEGEN / "ir.py"),
        "codegen_decomp": sha(CODEGEN / "decomp.py"),
        "solver": sha(SOLVER),
    }
    return paths


def evidence_hashes():
    return {
        "planted_witness_builder": sha(HERE / "export_d10_planted_witness.py"),
        "sage_full_base_audit_builder": sha(HERE / "sage_audit_d10_full_base.py"),
        "sage_planted_replay_builder": sha(HERE / "sage_replay_d10_planted_relation.py"),
        "single_target_auditor": sha(HERE / "audit_d10_m15_single_target.py"),
        "continuation_watcher": sha(HERE / "continue_d10_after_r3.py"),
        "geometry_receipt": sha(HERE / "d10_exact_geometry_v1.json"),
        "formula_receipt": sha(HERE / "d10_m15_formula_and_planted_control_v1.json"),
        "formula_file": sha(HERE / "official_q_phi_fiber_d10_m15_v1.xcnf"),
        "planted_witness": sha(HERE / "d10_planted_witness_v1.json"),
        "sage_full_base_audit": sha(HERE / "sage_d10_full_base_audit_v1.json"),
        "sage_planted_replay": sha(HERE / "sage_d10_planted_relation_audit_v1.json"),
        "sage_runtime_info": sha(RUNTIME_INFO),
        "curve_record": sha(CURVE_RECORD),
        "workload": sha(WORKLOAD),
        "bridge_audit": sha(BRIDGE),
    }


def preflight():
    geometry_path = HERE / "d10_exact_geometry_v1.json"
    formula_path = HERE / "official_q_phi_fiber_d10_m15_v1.xcnf"
    formula_receipt_path = HERE / "d10_m15_formula_and_planted_control_v1.json"
    witness_path = HERE / "d10_planted_witness_v1.json"
    base_audit_path = HERE / "sage_d10_full_base_audit_v1.json"
    replay_path = HERE / "sage_d10_planted_relation_audit_v1.json"
    required = (MANIFEST, PROTOCOL, WORKLOAD, CURVE_RECORD, BRIDGE,
                RUNTIME_INFO, SOLVER, geometry_path, formula_path,
                formula_receipt_path, witness_path, base_audit_path,
                replay_path, HERE / "sparse_seed_d10_m15_pipeline.py",
                HERE / "audit_d10_m15_single_target.py",
                HERE / "continue_d10_after_r3.py",
                M16_DIR / "phi_frobenius_sat_gate_m16_sparse_seed_v1.py",
                M16_DIR / "q1358_exact_model_decoder_m16.py")
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = json.loads(MANIFEST.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    workload = json.loads(WORKLOAD.read_text())
    curve_data = json.loads(CURVE_RECORD.read_text())
    bridge = json.loads(BRIDGE.read_text())
    runtime = json.loads(RUNTIME_INFO.read_text())
    geometry = json.loads(geometry_path.read_text())
    formula_receipt = json.loads(formula_receipt_path.read_text())
    witness = json.loads(witness_path.read_text())
    base_audit = json.loads(base_audit_path.read_text())
    sage_replay = json.loads(replay_path.read_text())

    if manifest.get("candidate_id") != protocol.get("candidate_id"):
        raise ValueError("candidate manifest/protocol ID mismatch")
    candidate_core = manifest["candidate_record"]
    candidate_identity = digest(candidate_core)
    if candidate_identity != manifest.get("candidate_identity_sha256"):
        raise ValueError("candidate manifest identity digest mismatch")
    expected_candidate_id = (
        "IC1N131Ckb1fb%dPDP15satRCdirectLAgaussTDdirectISO0h%s" %
        (candidate_core["factor_base"][
            "actual_usable_points_before_sign_frobenius_folding"],
         candidate_identity[:12]))
    if manifest.get("candidate_id") != expected_candidate_id or \
            protocol.get("candidate_id") != expected_candidate_id:
        raise ValueError("candidate ID does not encode the frozen d10/m15 record")
    if (candidate_core.get("field") != curve_data.get("field") or
            candidate_core.get("curve") != curve_data.get("curve") or
            candidate_core.get("isogeny") != "none"):
        raise ValueError("candidate field, curve, or isogeny differs from the frozen instance")

    if (protocol.get("candidate_manifest_sha256") != sha(MANIFEST) or
            protocol.get("target_count") != 1 or protocol.get("batch") is not False or
            workload.get("target_count") != 1 or
            len(workload.get("targets", [])) != 1):
        raise ValueError("candidate identity or one-target workload changed")
    if (protocol.get("workload_id") != workload.get("workload_id") or
            protocol.get("curve_id") != workload.get("curve_id") or
            protocol.get("curve_id") != curve_data["curve"]["curve_id"] or
            protocol.get("workload_sha256") != sha(WORKLOAD) or
            protocol.get("curve_record_sha256") != sha(CURVE_RECORD) or
            protocol.get("bridge_sha256") != sha(BRIDGE)):
        raise ValueError("frozen workload, curve, or bridge digest changed")
    if bridge.get("status") != "PASS" or \
            bridge.get("official_generator_onb_coordinates") != candidate_core["curve"]["generator"] or \
            bridge.get("official_target_onb_coordinates") != workload["targets"][0] or \
            int(bridge.get("subgroup_order", "0")) != candidate_core["curve"]["subgroup_order"]:
        raise ValueError("official generator, public target, or subgroup bridge changed")
    curve_core = {key: value for key, value in curve_data["curve"].items()
                  if key != "curve_id"}
    if digest({"field": curve_data["field"], "curve": curve_core}) != curve_data["curve_sha256"]:
        raise ValueError("official curve record no longer matches its curve ID")
    workload_core = {key: value for key, value in workload.items()
                     if key not in ("workload_id", "workload_sha256")}
    if digest(workload_core) != workload.get("workload_sha256"):
        raise ValueError("official workload no longer matches its workload ID")

    fb = candidate_core["factor_base"]
    geom_fb = geometry["factor_base"]
    if (geometry.get("status") != "PASS" or geometry.get("target_count") != 1 or
            geometry.get("curve_id") != workload["curve_id"] or
            geometry.get("workload_id") != workload["workload_id"] or
            geometry.get("source_sha256") != sha(HERE / "audit_d10_geometry.py") or
            geometry.get("inputs_sha256", {}).get("workload") != sha(WORKLOAD) or
            fb.get("nominal_subspace_dimension_or_bound") != 10 or
            fb.get("ordered_basis_coordinate_masks_hex") !=
            geometry["domain"]["basis_coordinate_masks_hex"] or
            fb.get("actual_usable_points_before_sign_frobenius_folding") !=
            geom_fb["actual_distinct_nonidentity_subgroup_points_before_sign_frobenius_folding"] or
            fb.get("effective_relation_matrix_columns") != geom_fb["folded_frobenius_columns"] or
            fb.get("enumerated_point_set_sha256") !=
            geom_fb["enumerated_signed_subgroup_point_set_sha256"] or
            candidate_core["point_decomposition"].get("summand_count") != LEAVES):
        raise ValueError("frozen candidate record disagrees with exact d10/m15 geometry")
    if (base_audit.get("status") != "PASS" or
            base_audit.get("target_count") != 1 or
            base_audit.get("workload_id") != workload["workload_id"] or
            base_audit.get("curve_id") != workload["curve_id"] or
            base_audit.get("source_sha256") != sha(HERE / "sage_audit_d10_full_base.py") or
            base_audit.get("input_sha256", {}).get("d10_exact_geometry_v1.json") !=
            sha(geometry_path) or
            base_audit.get("input_sha256", {}).get("d10_m15_formula_and_planted_control_v1.json") !=
            sha(formula_receipt_path) or
            base_audit.get("input_sha256", {}).get("bridge_audit.json") != sha(BRIDGE) or
            base_audit.get("input_sha256", {}).get("workload.json") != sha(WORKLOAD) or
            base_audit.get("enumerated_point_set_sha256") != fb["enumerated_point_set_sha256"] or
            base_audit.get("actual_usable_points_before_folding") !=
            fb["actual_usable_points_before_sign_frobenius_folding"] or
            base_audit.get("folded_columns") != fb["effective_relation_matrix_columns"] or
            base_audit.get("four_endpoint_fiber") != "PASS"):
        raise ValueError("independent Sage full-base or public-Q fiber audit failed")

    formula = formula_receipt
    planted = formula.get("planted_control", {})
    formula_template = M16_DIR / "phi_frobenius_sat_gate_m16_sparse_seed_v1.py"
    if (formula.get("status") != "PASS" or formula.get("target_count") != 1 or
            formula.get("summand_count") != LEAVES or
            formula.get("subspace_dimension") != 10 or
            formula.get("source_sha256") != sha(HERE / "build_d10_m15_formula.py") or
            formula.get("factor_base_point_set_sha256") != fb["enumerated_point_set_sha256"] or
            formula.get("formula_file", {}).get("sha256") != sha(formula_path) or
            formula.get("formula_file", {}).get("bytes") != formula_path.stat().st_size or
            formula.get("inputs_sha256", {}).get("workload") != sha(WORKLOAD) or
            formula.get("inputs_sha256", {}).get("formula_template") != sha(formula_template) or
            formula.get("inputs_sha256", {}).get("geometry") != sha(geometry_path) or
            planted.get("status") != "PASS" or planted.get("solver_launched") is not False):
        raise ValueError("frozen d10/m15 single-target formula or planted control failed")
    if (witness.get("status") != "PASS" or witness.get("target_count") != 1 or
            witness.get("summand_count") != LEAVES or
            witness.get("formula_control_receipt_sha256") != sha(formula_receipt_path) or
            witness.get("source_sha256") != sha(HERE / "export_d10_planted_witness.py") or
            witness.get("inputs_sha256", {}).get("geometry") != sha(geometry_path) or
            witness.get("inputs_sha256", {}).get("official_workload") != sha(WORKLOAD) or
            witness.get("inputs_sha256", {}).get("runtime_info") != sha(RUNTIME_INFO)):
        raise ValueError("d10/m15 planted witness is stale or incomplete")
    if (sage_replay.get("status") != "PASS" or
            sage_replay.get("target_count") != 1 or
            sage_replay.get("summand_count") != LEAVES or
            sage_replay.get("exact_leaf_point_checks") != LEAVES or
            sage_replay.get("exact_partial_phi_chain_checks") != LEAVES - 2 or
            sage_replay.get("target_fiber_endpoint_checks") != 4 or
            not sage_replay.get("planted_sum_equals_synthetic_target") or
            sage_replay.get("source_sha256") != sha(HERE / "sage_replay_d10_planted_relation.py") or
            sage_replay.get("input_sha256", {}).get("geometry") != sha(geometry_path) or
            sage_replay.get("input_sha256", {}).get("formula_receipt") !=
            sha(formula_receipt_path) or
            sage_replay.get("input_sha256", {}).get("witness") != sha(witness_path) or
            sage_replay.get("input_sha256", {}).get("base_audit") != sha(base_audit_path) or
            sage_replay.get("input_sha256", {}).get("params") != sha(SOURCE_RUN / "official_fixed_parameters.json") or
            sage_replay.get("input_sha256", {}).get("bridge") != sha(BRIDGE) or
            sage_replay.get("input_sha256", {}).get("runtime_info") != sha(RUNTIME_INFO)):
        raise ValueError("independent installed-Sage planted relation replay failed")

    if runtime.get("status") != "verified" or runtime.get("manifest_sha256") != \
            sha(ROOT / "experiments/sage-binary-arithmetic/runtime-current.json"):
        raise ValueError("checked Sage runtime receipt is stale")
    current_sources = source_hashes()
    if (protocol.get("source_sha256") != current_sources or
            manifest.get("provenance", {}).get("source_sha256") != current_sources):
        raise ValueError("a d10/m15 implementation or frozen source changed after freeze")
    component_hashes = candidate_core.get("implementation", {}).get("component_sha256", {})
    if component_hashes != current_sources:
        raise ValueError("candidate record does not bind the exact d10/m15 pipeline")
    current_evidence = evidence_hashes()
    if (manifest.get("provenance", {}).get("evidence_sha256") != current_evidence or
            protocol.get("evidence_sha256") != current_evidence or
            manifest.get("provenance", {}).get("runtime_info_sha256") !=
            current_evidence["sage_runtime_info"] or
            protocol.get("runtime_info_sha256") != current_evidence["sage_runtime_info"]):
        raise ValueError("candidate or run protocol evidence digests changed")
    if protocol.get("solver_sha256") != sha(SOLVER):
        raise ValueError("CryptoMiniSat binary changed after freeze")
    run_control = protocol.get("run_control", {})
    resource_envelope = protocol.get("resource_envelope", {})
    if (run_control.get("precomputation_attempt_cap") != MAX_PRECOMPUTE_ATTEMPTS or
            run_control.get("precomputation_query_seconds") != PRECOMPUTE_QUERY_SECONDS or
            run_control.get("online_query_seconds") != ONLINE_QUERY_SECONDS or
            run_control.get("models_per_relation_target") != MAX_MODELS_PER_RELATION or
            run_control.get("max_conflicts_per_query") != CONFLICT_LIMIT or
            resource_envelope.get("combined_sage_and_solver_rss_limit_bytes") != RSS_LIMIT_BYTES or
            resource_envelope.get("cms_max_matrix_rows") != CMS_MATRIX_ROWS or
            resource_envelope.get("cms_max_matrix_columns") != CMS_MATRIX_COLS or
            resource_envelope.get("cms_max_matrices") != CMS_NUM_MATRICES or
            resource_envelope.get("solver_threads") != 1):
        raise ValueError("single-target run limits differ from the frozen protocol")

    r3_status, process, r3_result_path = r3_terminal_gate()
    status = r3_status
    if status == "READY":
        prior = sorted((HERE / "single_target_runs").glob("*/result.json"))
        if prior:
            raise FileExistsError("a d10/m15 single-target run already exists")
    receipt = {
        "kind": "ecc2k130_n131_d10_m15_single_target_pipeline_preflight",
        "status": status,
        "candidate_id": protocol["candidate_id"],
        "curve_id": workload["curve_id"],
        "workload_id": workload["workload_id"],
        "target_count": 1,
        "batch": False,
        "solver_launched": False,
        "r3_status": r3_status,
        "r3_process_state": process,
        "r3_result_path": str(r3_result_path),
        "source_sha256": source_hashes(),
        "input_sha256": {path.name: sha(path) for path in required},
        "resource_envelope": {"solver_workers": 1,
                              "combined_rss_limit_bytes": RSS_LIMIT_BYTES,
                              "precomputation_query_seconds": PRECOMPUTE_QUERY_SECONDS,
                              "online_query_seconds": ONLINE_QUERY_SECONDS,
                              "precomputation_attempt_cap": MAX_PRECOMPUTE_ATTEMPTS,
                              "models_per_relation_target": MAX_MODELS_PER_RELATION},
    }
    return receipt, manifest, protocol, workload, curve_data, bridge


def configure_solver(query_dir: Path, seed: int):
    os.environ["IC_CMS_CLI_BIN"] = str(SOLVER)
    os.environ["IC_CMS_CLI_FORMULA"] = str(query_dir / "query.xcnf")
    os.environ["IC_CMS_CLI_STDOUT"] = str(query_dir / "cryptominisat.stdout.txt")
    os.environ["IC_CMS_CLI_STDERR"] = str(query_dir / "cryptominisat.stderr.txt")
    os.environ["IC_CMS_CLI_PIDFILE"] = str(query_dir / "cryptominisat.pid")
    os.environ["IC_CMS_CLI_SEED"] = str(seed)
    os.environ["IC_CMS_CLI_RSS_LIMIT_BYTES"] = str(RSS_LIMIT_BYTES)
    os.environ["IC_CMS_CLI_MAX_MATRIX_ROWS"] = str(CMS_MATRIX_ROWS)
    os.environ["IC_CMS_CLI_MAX_MATRIX_COLS"] = str(CMS_MATRIX_COLS)
    os.environ["IC_CMS_CLI_MAX_NUM_MATRICES"] = str(CMS_NUM_MATRICES)


def stop_solver(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_measured_solver(formula, query_dir, seed, remaining_seconds):
    """Run CMS and exclude process start plus formula read from compute time."""
    query_dir = Path(query_dir)
    query_dir.mkdir(parents=True, exist_ok=True)
    formula_path = query_dir / "query.xcnf"
    stdout_path = query_dir / "cryptominisat.stdout.txt"
    stderr_path = query_dir / "cryptominisat.stderr.txt"
    pid_path = query_dir / "cryptominisat.pid"
    serialize_start_ns = time.perf_counter_ns()
    formula.writeDimacs(formula_path)
    formula_serialize_ns = time.perf_counter_ns() - serialize_start_ns
    solver_seconds = max(0.05, remaining_seconds - 2.0)
    command = [str(SOLVER), "--threads=1", "--verb=1", "--verbstat=2",
               "--printsol=1", "--restartprint=10000000",
               "--random=" + str(seed), "--maxtime=%.3f" % solver_seconds,
               "--maxmatrixrows=" + str(CMS_MATRIX_ROWS),
               "--maxmatrixcols=" + str(CMS_MATRIX_COLS),
               "--maxnummatrices=" + str(CMS_NUM_MATRICES),
               "--maxconfl=" + str(CONFLICT_LIMIT), str(formula_path)]
    rss_limit = RSS_LIMIT_BYTES
    parent_deadline = time.monotonic() + max(0.1, remaining_seconds - 1.0)
    parse_complete_ns = None
    parse_time_seconds = None
    process_start_utc = None
    parse_complete_observed_utc = None
    max_solver_rss = 0
    max_combined_rss = 0
    stop_reason = None
    process_start_ns = time.perf_counter_ns()
    process_start_utc = utc_now()
    stdout_buffer = bytearray()
    line_buffer = bytearray()
    with stderr_path.open("wb") as stderr_file, stdout_path.open("wb") as stdout_file:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=stderr_file, start_new_session=True)
        pid_path.write_text(str(process.pid) + "\n")
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while process.poll() is None or selector.get_map():
                now = time.perf_counter_ns()
                if process.poll() is None:
                    solver_rss = e.CryptoMiniSatCli.processRssBytes(process.pid)
                    parent_rss = e.CryptoMiniSatCli.processRssBytes(os.getpid())
                    if solver_rss is None or parent_rss is None:
                        stop_reason = "rss_unavailable"
                        stop_solver(process)
                        raise RuntimeError("cannot enforce combined CryptoMiniSat RSS limit")
                    max_solver_rss = max(max_solver_rss, solver_rss)
                    max_combined_rss = max(max_combined_rss, solver_rss + parent_rss)
                    if max_combined_rss > rss_limit:
                        stop_reason = "rss_limit"
                        stop_solver(process)
                        break
                    if time.monotonic() >= parent_deadline:
                        stop_reason = "parent_timeout"
                        stop_solver(process)
                        break
                timeout = 0.01 if parse_complete_ns is None else 0.1
                events = selector.select(timeout)
                for key, _ in events:
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    stdout_file.write(chunk)
                    stdout_file.flush()
                    stdout_buffer.extend(chunk)
                    line_buffer.extend(chunk)
                    while b"\n" in line_buffer:
                        line, _, rest = line_buffer.partition(b"\n")
                        line_buffer = bytearray(rest)
                        if parse_complete_ns is None and line.startswith(b"c Parsing time:"):
                            parse_complete_ns = time.perf_counter_ns()
                            parse_complete_observed_utc = utc_now()
                            try:
                                parse_time_seconds = float(line.split()[3])
                            except (IndexError, ValueError):
                                parse_time_seconds = None
                if process.poll() is not None and not events:
                    # Drain remaining stdout before closing the selector.
                    try:
                        tail = os.read(process.stdout.fileno(), 65536)
                    except OSError:
                        tail = b""
                    if tail:
                        stdout_file.write(tail)
                        stdout_file.flush()
                        stdout_buffer.extend(tail)
                        line_buffer.extend(tail)
                    elif process.stdout.closed is False:
                        selector.unregister(process.stdout)
            return_code = process.wait()
        except BaseException:
            if process.poll() is None:
                stop_solver(process)
            raise
        finally:
            selector.close()
            process.stdout.close()
    process_end_ns = time.perf_counter_ns()
    if line_buffer and parse_complete_ns is None:
        for line in line_buffer.splitlines():
            if line.startswith(b"c Parsing time:"):
                parse_complete_ns = process_end_ns
                parse_complete_observed_utc = utc_now()
                try:
                    parse_time_seconds = float(line.split()[3])
                except (IndexError, ValueError):
                    parse_time_seconds = None
                break
    computation_start_ns = parse_complete_ns
    computation_wall_ns = (process_end_ns - computation_start_ns
                           if computation_start_ns is not None else 0)
    process_startup_and_input_load_ns = (
        computation_start_ns - process_start_ns
        if computation_start_ns is not None else process_end_ns - process_start_ns)

    status = None
    model = []
    for raw_line in stdout_buffer.decode("utf-8", "replace").splitlines():
        if raw_line.startswith("s "):
            if "SATISFIABLE" in raw_line and "UNSATISFIABLE" not in raw_line:
                status = True
            elif "UNSATISFIABLE" in raw_line:
                status = False
        elif raw_line.startswith("v "):
            for token in raw_line.split()[1:]:
                literal = int(token)
                if literal:
                    model.append(literal)
    if status is True and computation_start_ns is None:
        status = None
        stop_reason = stop_reason or "missing_parse_boundary"
    if status is None and stop_reason == "rss_limit":
        pass
    elif status is None and stop_reason == "parent_timeout":
        pass
    return {
        "status": status,
        "model": model if status is True else None,
        "returncode": return_code,
        "stop_reason": stop_reason,
        "command": command,
        "pid": process.pid,
        "process_start_utc": process_start_utc,
        "parse_complete_observed_utc": parse_complete_observed_utc,
        "formula_sha256": sha(formula_path),
        "stdout_sha256": sha(stdout_path),
        "stderr_sha256": sha(stderr_path),
        "formula_serialize_ns": formula_serialize_ns,
        "process_start_ns": process_start_ns,
        "parse_complete_observed_ns": parse_complete_ns,
        "solver_reported_parse_seconds": parse_time_seconds,
        "process_startup_and_input_load_ns_excluded": process_startup_and_input_load_ns,
        "solver_compute_wall_ns": computation_wall_ns,
        "solver_peak_rss_bytes": max_solver_rss,
        "combined_peak_rss_bytes": max_combined_rss,
    }


def block_primary(formula, primary, model_literals):
    model = {abs(literal): literal > 0 for literal in model_literals if literal}
    clause = []
    for variables in primary.values():
        for variable in variables:
            if variable not in model:
                raise ValueError("SAT model omitted a primary variable")
            clause.append(-variable if model[variable] else variable)
    formula.addClause(clause)


def solve_relation(context, target, target_scalar, attempt_dir, seed,
                   formula_receipt, max_models):
    onb, curve, order, eigenvalue, generator, basis_masks, representatives, \
        lookup, key_to_column, valid_codes, official_q, fiber_coordinates = context
    query_start = time.perf_counter_ns()
    formula_build_start = time.perf_counter_ns()
    formula, primary, roots, fiber, phi_masks = pipeline.target_relation_formula(
        onb, curve, order, target, basis_masks, valid_codes, official_q,
        fiber_coordinates)
    stats = formula.stats()
    expected = formula_receipt["formula_counts"]
    if (stats["vars"] != expected["variables"] or
            stats["clauses"] != expected["clauses"] or
            stats["xors"] != expected["native_xors"] or
            len(roots) != expected["roots"]):
        raise ValueError("target formula counts differ from frozen d10/m15 receipt")
    formula_build_ns = time.perf_counter_ns() - formula_build_start
    attempts = []
    relation_check_ns = 0
    solve_ns = 0
    formula_serialize_ns = 0
    startup_excluded_ns = 0
    decoded_rows = []
    accepted_rows = []
    statuses = []
    deadline = time.monotonic() + (ONLINE_QUERY_SECONDS if target_scalar is None
                                   else PRECOMPUTE_QUERY_SECONDS)
    for model_index in range(max_models):
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            statuses.append("timeout")
            break
        model_dir = attempt_dir / ("model_%02d" % (model_index + 1))
        model_dir.mkdir(parents=True, exist_ok=False)
        solver_result = run_measured_solver(
            formula, model_dir, seed + model_index, remaining)
        solved = solver_result["status"]
        elapsed_solve = solver_result["solver_compute_wall_ns"]
        solve_ns += elapsed_solve
        formula_serialize_ns += solver_result["formula_serialize_ns"]
        startup_excluded_ns += solver_result[
            "process_startup_and_input_load_ns_excluded"]
        model_record = {
            "model_index": model_index + 1,
            "solver_status": "sat" if solved is True else "unsat" if solved is False else "indeterminate",
            "solver_compute_wall_ns": elapsed_solve,
            "solver_exit_code": solver_result["returncode"],
            "solver_stop_reason": solver_result["stop_reason"],
            "solver_peak_rss_bytes": solver_result["solver_peak_rss_bytes"],
            "combined_peak_rss_bytes": solver_result["combined_peak_rss_bytes"],
            "formula_sha256": solver_result["formula_sha256"],
            "formula_serialize_ns": solver_result["formula_serialize_ns"],
            "solver_startup_and_input_load_ns_excluded": solver_result[
                "process_startup_and_input_load_ns_excluded"],
            "solver_process_start_utc": solver_result["process_start_utc"],
            "solver_parse_complete_observed_utc": solver_result[
                "parse_complete_observed_utc"],
            "solver_reported_parse_seconds": solver_result[
                "solver_reported_parse_seconds"],
            "stdout_sha256": solver_result["stdout_sha256"],
            "stderr_sha256": solver_result["stderr_sha256"],
        }
        if solved is False:
            statuses.append("unsat")
            attempts.append(model_record)
            break
        if solved is None:
            status = ("oom" if solver_result["stop_reason"] == "rss_limit" else
                      "timeout" if solver_result["stop_reason"] == "parent_timeout" else
                          "indeterminate")
            statuses.append(status)
            attempts.append(model_record)
            break

        model = solver_result["model"]
        verify_started_ns = time.perf_counter_ns()
        try:
            codes, partials, endpoint_index = decoder.decode_primary(model, primary)
            decoded = decoder.verify_relation(
                onb, curve, basis_masks, valid_codes, codes, partials,
                endpoint_index, fiber, order, eigenvalue)
            dense = pipeline.dense_positive_rhs_row(
                onb, curve, order, target, decoded, key_to_column,
                representatives)
            if dense is None:
                raise ValueError("SAT model has no exact signed curve lift")
            model_record.update({
                "decoded_primary": {"leaf_codes": codes,
                                    "partial_phi_masks": partials,
                                    "endpoint_index": endpoint_index},
                "decoded_rows": decoded,
                "locally_verified_positive_rhs_row": True,
            })
            decoded_rows.extend(decoded)
            accepted_rows.append(dense)
            statuses.append("verified_relation")
        except (ValueError, AssertionError) as error:
            model_record["locally_verified_positive_rhs_row"] = False
            model_record["model_rejection_reason"] = str(error)
            statuses.append("model_rejected")
        relation_check_ns += time.perf_counter_ns() - verify_started_ns
        attempts.append(model_record)
        block_primary(formula, primary, model)
        if target_scalar is None and accepted_rows:
            break

    raw_wall_ns = time.perf_counter_ns() - query_start
    charged_ns = raw_wall_ns - startup_excluded_ns
    parent_rss = parent_peak_rss()
    solver_rss = max((int(item.get("solver_peak_rss_bytes") or 0)
                      for item in attempts), default=0)
    combined_solver_rss = max((int(item.get("combined_peak_rss_bytes") or 0)
                               for item in attempts), default=0)
    rss_bound = max(parent_rss + solver_rss, combined_solver_rss)
    accepted = bool(accepted_rows)
    details = {
        "status": "verified_relation" if accepted else (statuses[-1] if statuses else "no_model"),
        "formula_counts": stats,
        "frozen_official_q_formula_template_sha256": formula_receipt["formula_file"]["sha256"],
        "target_formula_sha256": attempts[0]["formula_sha256"] if attempts else None,
        "attempts": attempts,
        "model_statuses": statuses,
        "decoded_rows": decoded_rows,
        "accepted_dense_rows": accepted_rows,
        "accepted_relation_count": len(accepted_rows),
        "verified_relation_count": len(accepted_rows),
        "rank_increases": None,
        "formula_build_ns": formula_build_ns,
        "formula_serialize_ns": formula_serialize_ns,
        "solver_startup_and_input_load_ns_excluded": startup_excluded_ns,
        "raw_query_wall_ns_including_excluded_startup": raw_wall_ns,
        "solver_wall_ns": solve_ns,
        "relation_check_ns": relation_check_ns,
        "query_wall_ns": charged_ns,
        "parent_process_peak_rss_bytes": parent_rss,
        "solver_peak_rss_bytes": solver_rss,
        "combined_peak_rss_bytes": combined_solver_rss,
        "conservative_combined_peak_rss_bytes": rss_bound,
        "rss_gate_passed": rss_bound <= RSS_LIMIT_BYTES,
        "target_scalar_known_to_solver": False,
    }
    if target_scalar is not None:
        details["precomputation_target_scalar_sha256"] = hashlib.sha256(
            str(target_scalar).encode("ascii")).hexdigest()
    if not details["rss_gate_passed"]:
        details["status"] = "outside_resource_envelope"
        details["accepted_relation_count"] = 0
        details["verified_relation_count"] = 0
        details["accepted_dense_rows"] = []
        accepted_rows = []
    return accepted_rows, details


def build_context(curve_data, workload, manifest):
    ledger = e.Ledger()
    onb = e.AuditField(131, ledger)
    curve = e.AuditCurve(onb, ledger)
    order = int(curve_data["curve"]["subgroup_order"])
    generator = tuple(onb.fromCoords(int(value))
                      for value in curve_data["curve"]["generator"])
    if not curve.onCurve(generator) or curve.mul(generator, order) is not None:
        raise ValueError("official generator failed curve/subgroup verification")
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    basis_masks = [int(value, 16) for value in
                   pipeline.GEOMETRY["domain"]["basis_coordinate_masks_hex"]]
    representatives, lookup, key_to_column, valid_codes, base_receipt = \
        pipeline.build_sparse_factor_base(
            onb, curve, order, eigenvalue, basis_masks)
    target = tuple(onb.fromCoords(int(value)) for value in workload["targets"][0])
    if not curve.onCurve(target) or curve.mul(target, order) is not None:
        raise ValueError("official one-target Q failed curve/subgroup verification")
    bridge = json.loads(BRIDGE.read_text())
    official_q = tuple(onb.fromCoords(int(value)) for value in
                       bridge["official_target_onb_coordinates"])
    if target != official_q:
        raise ValueError("workload target differs from independently audited official Q")
    fiber_coordinates = [item["target_coordinates"] for item in
                         pipeline.GEOMETRY["official_single_target_cofactor_fiber"][
                             "four_verified_lifts"]]
    context = (onb, curve, order, eigenvalue, generator, basis_masks,
               representatives, lookup, key_to_column, valid_codes,
               official_q, fiber_coordinates)
    return context, target, base_receipt, ledger.report()


def run_one_target(args):
    preflight_receipt, manifest, protocol, workload, curve_data, bridge = preflight()
    if preflight_receipt["status"] != "READY":
        receipt_path = HERE / "single_target_preflights" / (
            "d10_m15_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
        atomic_json(receipt_path, preflight_receipt)
        print(json.dumps({"status": preflight_receipt["status"],
                          "preflight": str(receipt_path),
                          "solver_launched": False}, sort_keys=True))
        return 0
    if args.preflight_only:
        receipt_path = HERE / "single_target_preflights" / (
            "d10_m15_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
        atomic_json(receipt_path, preflight_receipt)
        print(json.dumps({"status": "READY", "preflight": str(receipt_path),
                          "solver_launched": False}, sort_keys=True))
        return 0

    run_control = protocol["run_control"]
    run_id = "%sW%sR%d" % (protocol["candidate_id"], protocol["workload_id"],
                            run_control["run_number"])
    run_dir = HERE / "single_target_runs" / run_id
    if run_dir.exists():
        raise FileExistsError("refusing to overwrite an existing single-target run")
    run_dir.mkdir(parents=True)
    runtime_output = subprocess.run([str(ROOT / "sage"), "--runtime-info"],
                                    capture_output=True, text=True, check=True).stdout
    (run_dir / "sage_runtime_info.json").write_text(runtime_output)
    started = {**preflight_receipt, "status": "RUNNING_FACTOR_BASE_SETUP",
               "run_id": run_id, "started_utc": utc_now()}
    atomic_json(run_dir / "started.json", started)
    setup_start = time.perf_counter_ns()
    context, target, base_receipt, setup_operations = build_context(
        curve_data, workload, manifest)
    setup_wall_ns = time.perf_counter_ns() - setup_start
    atomic_json(run_dir / "factor_base_receipt.json", base_receipt)
    started.update({"status": "RUNNING_PRECOMPUTATION",
                    "factor_base_point_count": len(base_receipt["entries"]),
                    "factor_base_folded_columns": len(base_receipt["representatives"]),
                    "factor_base_point_set_sha256":
                        base_receipt["enumerated_point_set_sha256"],
                    "setup_wall_ns_excluded": setup_wall_ns,
                    "setup_operation_record": setup_operations})
    atomic_json(run_dir / "started.json", started)
    onb, curve, order, eigenvalue, generator, basis_masks, representatives, \
        lookup, key_to_column, valid_codes, official_q, fiber_coordinates = context
    formula_receipt = json.loads((HERE / "d10_m15_formula_and_planted_control_v1.json").read_text())

    matrix = e.RelationMatrix(len(representatives), order, e.Ledger())
    attempts = []
    max_precompute_rss = 0
    precompute_start_ns = time.perf_counter_ns()
    matrix_wall_ns = 0
    random_source = random.Random(run_control["precomputation_seed"])
    atomic_json(run_dir / "precompute_progress.json", {
        "status": "RUNNING", "rank": 0,
        "rank_target": len(representatives), "attempts": attempts,
    })
    for relation_index in range(1, MAX_PRECOMPUTE_ATTEMPTS + 1):
        if len(matrix.rows) == len(representatives):
            break
        relation_dir = run_dir / "precomputation" / ("target_%04d" % relation_index)
        relation_dir.mkdir(parents=True)
        scalar = random_source.randrange(1, order)
        generation_start = time.perf_counter_ns()
        precompute_target = curve.mul(generator, scalar)
        generation_ns = time.perf_counter_ns() - generation_start
        if precompute_target is None:
            raise AssertionError("nonzero precomputation scalar generated identity")
        rows, details = solve_relation(
            context, precompute_target, scalar, relation_dir,
            int(run_control["precomputation_solver_seed"]) + relation_index * 16,
            formula_receipt, MAX_MODELS_PER_RELATION)
        independent_rows = 0
        matrix_start_ns = time.perf_counter_ns()
        for row in rows:
            if matrix.push(row, 4 * scalar % order):
                independent_rows += 1
        matrix_wall_ns += time.perf_counter_ns() - matrix_start_ns
        max_precompute_rss = max(max_precompute_rss,
                                 details["conservative_combined_peak_rss_bytes"])
        attempt = {
            "relation_index": relation_index,
            "status": "verified_relation" if rows else details["status"],
            "target_count": 1,
            "known_scalar_target_fixture": True,
            "target_scalar": str(scalar),
            "target_generation_ns": generation_ns,
            "verified_relation_count": len(rows),
            "independent_rank_gain": independent_rows,
            "matrix_rank_after": len(matrix.rows),
            "query_details": details,
            "completed_utc": utc_now(),
        }
        atomic_json(relation_dir / "result.json", attempt)
        attempts.append(attempt)
        atomic_json(run_dir / "precompute_progress.json", {
            "status": "RUNNING", "rank": len(matrix.rows),
            "rank_target": len(representatives), "attempts": attempts,
        })

    if len(matrix.rows) != len(representatives):
        precompute_wall_ns = time.perf_counter_ns() - precompute_start_ns
        result = {
            "kind": "ecc2k130_sparse_seed_d10_m15_single_target_result",
            "status": "PRECOMPUTATION_INCOMPLETE",
            "candidate_id": protocol["candidate_id"],
            "run_id": run_id,
            "curve_id": workload["curve_id"],
            "workload_id": workload["workload_id"],
            "target_count": 1,
            "batch": False,
            "target_discrete_log_recovered": False,
            "precomputation_rank": len(matrix.rows),
            "precomputation_rank_target": len(representatives),
            "precomputation_attempts": attempts,
            "precomputation_wall_ns": precompute_wall_ns,
            "precomputation_matrix_update_wall_ns": matrix_wall_ns,
            "setup_wall_ns_excluded": setup_wall_ns,
            "setup_operation_record": setup_operations,
            "setup_peak_rss_bytes": parent_peak_rss(),
            "factor_base_point_count": len(lookup),
            "factor_base_folded_columns": len(representatives),
            "rho_online_ms": None,
            "online_speedup": None,
        }
        atomic_json(run_dir / "result.json", result)
        atomic_json(run_dir / "precompute_progress.json", {
            "status": "ATTEMPT_LIMIT_REACHED", "rank": len(matrix.rows),
            "rank_target": len(representatives), "attempts": attempts,
        })
        print(json.dumps({"status": result["status"], "run_id": run_id,
                          "rank": len(matrix.rows),
                          "rank_target": len(representatives)}, sort_keys=True))
        return 2

    matrix_solve_start_ns = time.perf_counter_ns()
    logs = matrix.solution()
    matrix_wall_ns += time.perf_counter_ns() - matrix_solve_start_ns
    log_replay_start_ns = time.perf_counter_ns()
    for log_value, representative in zip(logs, representatives):
        if curve.mul(generator, log_value) != representative:
            raise AssertionError("factor-base logarithm failed scalar replay")
    log_certificate_replay_ns = time.perf_counter_ns() - log_replay_start_ns
    precompute_wall_ns = time.perf_counter_ns() - precompute_start_ns
    atomic_json(run_dir / "precomputed_logs.json", {
        "curve_id": workload["curve_id"],
        "candidate_id": protocol["candidate_id"],
        "matrix_rank": len(matrix.rows),
        "logs": [str(value) for value in logs],
        "representatives": [[str(onb.toCoords(point[0])),
                             str(onb.toCoords(point[1]))]
                            for point in representatives],
        "all_logs_independently_verified": True,
    })
    atomic_json(run_dir / "precompute_progress.json", {
        "status": "LOGS_READY", "rank": len(matrix.rows),
        "rank_target": len(representatives), "attempts": attempts,
        "precomputation_wall_ns": precompute_wall_ns,
        "matrix_update_and_solve_wall_ns": matrix_wall_ns,
        "log_certificate_replay_ns": log_certificate_replay_ns,
    })

    query_dir = run_dir / "online_target"
    query_dir.mkdir()
    online_start_utc = utc_now()
    online_start_ns = time.perf_counter_ns()
    rows, details = solve_relation(
        context, target, None, query_dir,
        int(run_control["online_solver_seed"]), formula_receipt, 1)
    descent_start = time.perf_counter_ns()
    recovered = None
    if rows:
        inverse_four = pow(4, -1, order)
        recovered = (sum(coefficient * log_value
                         for coefficient, log_value in zip(rows[0], logs)) *
                     inverse_four) % order
    descent_ns = time.perf_counter_ns() - descent_start
    recovery_start = time.perf_counter_ns()
    verified = recovered is not None and curve.mul(generator, recovered) == target
    recovery_ns = time.perf_counter_ns() - recovery_start
    online_stop_ns = time.perf_counter_ns()
    online_stop_utc = utc_now()
    online_raw_wall_ns = online_stop_ns - online_start_ns
    online_wall_ns = (online_raw_wall_ns -
                      details["solver_startup_and_input_load_ns_excluded"])
    phase_wall_ns = {
        "T_target_query": online_wall_ns - details["solver_wall_ns"] -
            details["relation_check_ns"] - descent_ns - recovery_ns,
        "T_target_PDP": details["solver_wall_ns"],
        "T_target_relation_check": details["relation_check_ns"],
        "T_target_descent": descent_ns,
        "T_target_recovery_check": recovery_ns,
    }
    if sum(phase_wall_ns.values()) != online_wall_ns:
        raise AssertionError("exclusive one-target online phase accounting failed")
    result = {
        "kind": "ecc2k130_sparse_seed_d10_m15_single_target_result",
        "status": ("verified_single_target_dlp" if verified else
                   "TARGET_RECOVERY_UNVERIFIED" if rows else details["status"]),
        "candidate_id": protocol["candidate_id"],
        "run_id": run_id,
        "curve_id": workload["curve_id"],
        "workload_id": workload["workload_id"],
        "target_count": 1,
        "batch": False,
        "target_sha256": digest(workload["targets"][0]),
        "target_discrete_log_recovered": bool(verified),
        "recovered_scalar": str(recovered) if verified else None,
        "target_relation_verified": bool(rows),
        "setup_wall_ns_excluded": setup_wall_ns,
        "setup_operation_record": setup_operations,
        "setup_peak_rss_bytes": parent_peak_rss(),
        "precomputation": {
            "rank": len(matrix.rows),
            "attempt_count": len(attempts),
            "attempts": attempts,
            "wall_ns": precompute_wall_ns,
            "matrix_update_and_solve_wall_ns": matrix_wall_ns,
            "log_certificate_replay_ns": log_certificate_replay_ns,
            "factor_base_logs_verified": True,
            "excluded_from_online_metric": True,
        },
        "primary_target_online_wall_ns": online_wall_ns,
        "primary_target_online_wall_ms": online_wall_ns / 1_000_000,
        "primary_target_raw_wall_including_excluded_solver_startup_ns":
            online_raw_wall_ns,
        "online_interval": {
            "start_utc": online_start_utc,
            "start_event": "immediately before target-specific cofactor-fiber encoding and d10/m15 formula construction after verified reusable factor-base logs are ready",
            "stop_utc": online_stop_utc,
            "stop_event": "after exact row recovery, factor-log dot product, inverse-four adjustment, and scalar replay against the supplied public Q",
            "wall_accounting": "raw start-to-stop wall less explicitly recorded CryptoMiniSat process-launch and formula-input parsing intervals; formula serialization remains charged",
            "excluded_solver_startup_and_input_load_ns":
                details["solver_startup_and_input_load_ns_excluded"],
            "excluded_internal_intervals": [
                {"start_utc": item["solver_process_start_utc"],
                 "stop_utc": item["solver_parse_complete_observed_utc"],
                 "duration_ns": item["solver_startup_and_input_load_ns_excluded"],
                 "event": "CryptoMiniSat launch and XCNF input parsing"}
                for item in details["attempts"]],
            "included_stages": ["target_cofactor_fiber", "target_formula_build",
                                "target_PDP", "target_relation_lift_and_check",
                                "target_descent", "scalar_replay"],
        },
        "exclusive_online_phases": phase_wall_ns,
        "target_query_details": details,
        "factor_base_point_count": len(lookup),
        "factor_base_folded_columns": len(representatives),
        "factor_base_point_set_sha256": base_receipt["enumerated_point_set_sha256"],
        "combined_process_rss_limit_bytes": RSS_LIMIT_BYTES,
        "resource_limit_enforced": True,
        "rho_online_ms": None,
        "online_speedup": None,
        "claim_boundary": "single-target IC DLP only; no speedup until paired rho solves this same supplied Q under matched resources",
    }
    atomic_json(run_dir / "result.json", result)
    print(json.dumps({"status": result["status"], "run_id": run_id,
                      "target_count": 1,
                      "primary_target_online_wall_ms": result["primary_target_online_wall_ms"],
                      "rho_online_ms": None, "online_speedup": None,
                      "result": str(run_dir / "result.json")}, sort_keys=True))
    return 0 if verified else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        return run_one_target(args)
    except BaseException as failure:
        try:
            protocol = json.loads(PROTOCOL.read_text())
            workload = json.loads(WORKLOAD.read_text())
            run_id = "%sW%sR%d" % (
                protocol["candidate_id"], protocol["workload_id"],
                protocol["run_control"]["run_number"])
            run_dir = HERE / "single_target_runs" / run_id
            if run_dir.is_dir() and not (run_dir / "result.json").exists():
                failed = {
                    "kind": "ecc2k130_sparse_seed_d10_m15_single_target_result",
                    "status": "PRODUCER_FAILURE",
                    "candidate_id": protocol["candidate_id"],
                    "run_id": run_id,
                    "curve_id": workload["curve_id"],
                    "workload_id": workload["workload_id"],
                    "target_count": 1,
                    "batch": False,
                    "target_discrete_log_recovered": False,
                    "error_type": type(failure).__name__,
                    "error": str(failure),
                    "rho_online_ms": None,
                    "online_speedup": None,
                }
                atomic_json(run_dir / "failure.json", failed)
                atomic_json(run_dir / "result.json", failed)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
