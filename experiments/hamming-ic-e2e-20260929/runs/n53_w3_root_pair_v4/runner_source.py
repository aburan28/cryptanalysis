#!/usr/bin/env python3
"""Freeze and measure one new N53 public target with W3-root IC and rho."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

from n53_group import COFACTOR, Curve, Field, GENERATOR, MODULUS, N, R, TARGET

HERE = Path(__file__).resolve().parent
CRYPTO = Path("/Volumes/SSD990/crypto")
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
GEOMETRY = HERE / "runs/n53_weight3_geometry_v1/receipt.json"
REPS = HERE / "runs/n53_w3_base_export_v1/representatives.json"
IC_SOURCE = HERE / "koblitz_w3_root_index.rs"
RHO_SOURCE = HERE / "koblitz_rho_point.rs"
IC_BINARY = CRYPTO / "target/release/examples/koblitz_w3_root_index"
RHO_BINARY = CRYPTO / "target/release/examples/koblitz_rho_point"
SOURCE_PATHS = {
    "Cargo.lock": CRYPTO / "Cargo.lock",
    "koblitz_fast_arith.rs": CRYPTO / "src/cryptanalysis/koblitz_fast_arith.rs",
    "koblitz_index_calculus.rs": CRYPTO / "src/cryptanalysis/koblitz_index_calculus.rs",
    "binary_ecc.rs": CRYPTO / "src/binary_ecc.rs",
    "lib.rs": CRYPTO / "src/lib.rs",
    "semaev_decomp.rs": CRYPTO / "src/cryptanalysis/semaev_decomp.rs",
}
def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def run_bounded(command, out, stem, limit):
    stdout_path, stderr_path = out / f"{stem}.stdout.txt", out / f"{stem}.stderr.txt"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        started = time.perf_counter_ns()
        proc = subprocess.Popen(list(map(str, command)),
                                cwd=CRYPTO, stdout=stdout, stderr=stderr)
        launch_end = time.perf_counter_ns()
        timeout = False
        while True:
            pid, wait_status, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                exit_code = os.waitstatus_to_exitcode(wait_status)
                proc.returncode = exit_code
                break
            if (time.perf_counter_ns() - launch_end) / 1e9 >= limit:
                timeout = True
                proc.kill()
                _, wait_status, usage = os.wait4(proc.pid, 0)
                exit_code = os.waitstatus_to_exitcode(wait_status)
                proc.returncode = exit_code
                break
            time.sleep(0.01)
        ended = time.perf_counter_ns()
    return {"command": list(map(str, command)), "exit_code": exit_code,
            "external_timeout": timeout, "process_launch_ns": launch_end - started,
            "process_wall_ns": ended - launch_end,
            "peak_rss_bytes": usage.ru_maxrss if platform.system() == "Darwin"
                              else usage.ru_maxrss * 1024,
            "child_user_cpu_s": usage.ru_utime, "child_system_cpu_s": usage.ru_stime,
            "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
            "external_wall_limit_seconds": limit}


def candidate_record(geometry, reps, source_hashes, binaries):
    field = {"p": 2, "n": N, "basis": "polynomial",
             "defining_polynomial_int": MODULUS,
             "element_encoding": "nonnegative polynomial coefficient bit mask"}
    curve = {"model": "y^2+x*y=x^3+1",
             "coefficients": {"a1": 1, "a2": 0, "a3": 0, "a4": 0, "a6": 1},
             "curve_order": COFACTOR * R, "trace": (1 << N) + 1 - COFACTOR * R,
             "r": R, "cofactor": COFACTOR, "G": list(GENERATOR),
             "target_group": "prime_order_r_subgroup"}
    curve["curve_id"] = "EC1N53Ckb1h" + digest({"field": field, "curve": curve})[:12]
    assert curve["curve_id"] == geometry["curve_id"] == reps["curve_id"]
    return {
        "schema_version": 1, "field": field, "curve": curve, "isogeny": "none",
        "endomorphism": {"endomorphism_order_conductor": None,
                         "frobenius_order_conductor": None,
                         "volcano_levels": None, "status": "unproved_not_used"},
        "factor_base": {
            "construction": "normal_element_3_hamming_weight_3_rational_lifts_cofactor_428_then_sorted_signed_frobenius_representatives",
            "normal_element": 3, "nominal_weight": 3,
            "nominal_masks": geometry["nominal_masks"],
            "geometric_point_count": geometry["geometric_points"],
            "actual_usable_points": geometry["actual_usable_projected_points"],
            "projected_set_sha256": geometry["projected_set_sha256"],
            "representatives_sha256": sha(REPS),
            "ordered_labeled_entries_sha256": json.loads((REPS.parent / "receipt.json").read_text())["ordered_labeled_entries_sha256"],
            "sign_frobenius_quotient": "lexicographic_minimum_signed_frobenius_orbit",
            "effective_columns": geometry["effective_signed_frobenius_columns"],
            "frobenius_eigenvalue_mod_r": reps["lambda_mod_r"]},
        "point_decomposition": {
            "m": 4, "family": "root", "summation_chain": "four_summand_two_pair_S3_root_index",
            "equation_order": "indexed_first_pair_then_S3_roots_for_second_pair",
            "encoding": "normal_basis_Hamming_weight_3_x_then_polynomial_basis_group_lift",
            "monomial_order": "none", "internal_matrix_kernel": "none",
            "root_index": "all_221_representative_x_pairs_with_frobenius_rotations",
            "implementation_source_sha256": sha(IC_SOURCE),
            "cache_policy": "target_independent_base_and_root_index_reused_for_one_target",
            "limits": {"relation_attempt_cap": "max(8*columns,columns+32)",
                       "root_index_full_build": True}},
        "relation_collection": {
            "query_distribution": "pseudorandom_nonzero_known_scalar_times_G",
            "sampling_rule": "seeded_scalar_stream_one_worker",
            "verification": "full_group_sum_and_mod_r_row_check",
            "duplicate_dependency_handling": "incremental_independent_rows_only",
            "stop": "first_batch_after_target_row_enters_verified_relation_span_or_attempt_cap",
            "source_digest": sha(IC_SOURCE)},
        "relation_linear_algebra": {
            "modulus": R, "row_rule": "four_signed_frobenius_orbit_labels_mod_r",
            "columns": geometry["effective_signed_frobenius_columns"],
            "rank_criterion": "target_coefficient_row_in_verified_relation_span",
            "solver": "gauss", "implementation": "incremental_Gaussian_elimination_mod_r",
            "block_parameters": "none", "preconditioner": "none",
            "source_digest": sha(IC_SOURCE)},
        "target_descent": {
            "policy": "direct_four_summand_S3_root_decomposition_then_relation_span_recovery",
            "success": "verified_scalar_times_G_equals_supplied_point",
            "recursive_solver": "none", "source_digest": sha(IC_SOURCE)},
        "implementation": {
            "source_sha256": source_hashes,
            "ic_binary_sha256": binaries["ic"],
            "algorithm_flags": {"curve_n": 53, "curve_a": 0, "columns": 221,
                                "workers": 1, "orbit_rule": "signed_frobenius"}}
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wall-seconds", type=int, default=120)
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--fixture-seed", type=int, default=20260930)
    parser.add_argument("--ic-seed", type=int, default=53012)
    parser.add_argument("--rho-seed", type=int, default=53013)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("pair output is immutable")
    if args.wall_seconds < 1 or args.run_number < 1:
        raise ValueError("wall limit and run number must be positive")
    assert sha(IC_SOURCE) == sha(CRYPTO / "examples/koblitz_w3_root_index.rs")
    assert sha(RHO_SOURCE) == sha(CRYPTO / "examples/koblitz_rho_point.rs")
    geometry = json.loads(GEOMETRY.read_text())
    reps = json.loads(REPS.read_text())
    assert len(reps["representatives"]) == 221
    source_hashes = {name: sha(path) for name, path in SOURCE_PATHS.items() if path.is_file()}
    source_hashes["ic_example.rs"] = sha(IC_SOURCE)
    receipt_source_hashes = {**source_hashes, "rho_example.rs": sha(RHO_SOURCE),
                             "runner.py": sha(Path(__file__)),
                             "n53_group.py": sha(HERE / "n53_group.py")}
    binaries = {"ic": sha(IC_BINARY), "rho": sha(RHO_BINARY)}
    candidate = candidate_record(geometry, reps, source_hashes, binaries)
    candidate_id = ("IC1N53Ckb1fb23426PDP4rootRCguidedLAgaussTDdirectISO0h"
                    + digest(candidate)[:12])
    scalar = 1 + int.from_bytes(hashlib.sha256(
        f"N53-W3-ROOT-ONE-UNSEEN-TARGET-v1|{args.fixture_seed}".encode()).digest(), "big") % (R - 1)
    target = Curve(Field()).mul(GENERATOR, scalar)
    assert target is not None and target != TARGET
    workload = {"curve_id": candidate["curve"]["curve_id"],
                "subgroup_order": R, "generator": list(GENERATOR),
                "target_point": list(target), "target_count": 1,
                "target_generation_law": "sha256_seed_to_nonzero_scalar_times_G",
                "target_fixture_seed": args.fixture_seed,
                "input_law": "one_frozen_public_point_no_scalar_given_to_either_solver",
                "precomputation_state": "target_independent_W3_base_and_root_index_ready",
                "cold_or_warm": "warm_index_one_target"}
    workload_id = digest(workload)[:12]
    run_id = f"{candidate_id}W{workload_id}R{args.run_number}"
    out.mkdir(parents=True)
    save(out / "candidate.json", {"candidate_id": candidate_id, "record": candidate})
    save(out / "workload.json", {"workload_id": workload_id, "record": workload,
                                 "fixture_scalar_validation_only": scalar})
    (out / "target_point.json").write_text(json.dumps(list(target), separators=(",", ":")) + "\n")
    with (out / "sage_runtime_info.json").open("wb") as runtime:
        subprocess.run([str(SAGE), "--runtime-info"], stdout=runtime, check=True)
    ic_cmd = [IC_BINARY, "53", "0", "221", str(args.ic_seed), out / "target_point.json",
              out / "ic_result.jsonl", "1", REPS]
    ic_process = run_bounded(ic_cmd, out, "ic", args.wall_seconds)
    rho_cmd = [RHO_BINARY, "53", "0", "signed_frobenius",
               out / "target_point.json", str(args.rho_seed)]
    rho_process = run_bounded(rho_cmd, out, "rho", args.wall_seconds)
    ic_lines = (out / "ic_result.jsonl").read_text().splitlines() if (out / "ic_result.jsonl").exists() else []
    rho_lines = (out / "rho.stdout.txt").read_text().splitlines()
    ic = json.loads(ic_lines[0]) if len(ic_lines) == 1 else None
    rho = json.loads(rho_lines[0]) if len(rho_lines) == 1 else None
    ic_valid = (ic_process["exit_code"] == 0 and not ic_process["external_timeout"]
                and ic is not None and ic.get("target") == list(target)
                and ic.get("group_verified") is True and ic.get("recovered_scalar") == scalar)
    rho_valid = (rho_process["exit_code"] == 0 and not rho_process["external_timeout"]
                 and rho is not None and rho.get("target_point") == list(target)
                 and rho.get("verified") is True and rho.get("recovered_scalar") == scalar)
    ic_ms = ic["timing_ms"]["target_online_after_reusable_setup"] if ic_valid else None
    rho_ms = rho["online_ms"] if rho_valid else None
    report = {"schema_version": 1, "kind": "n53_w3_root_one_unseen_target_ic_vs_rho",
              "status": "IN_PROCESS_PAIR_PASS" if ic_valid and rho_valid else "PAIR_INCOMPLETE",
              "independent_sage_replay_status": None,
              "candidate_id": candidate_id, "curve_id": candidate["curve"]["curve_id"],
              "workload_id": workload_id, "run_id": run_id, "target_point": list(target),
              "target_count": 1, "fixture_scalar_validation_only": scalar,
              "run_seeds": {"fixture": args.fixture_seed, "ic_relation": args.ic_seed,
                            "rho_walk": args.rho_seed},
              "ic": {"process": ic_process, "result_sha256": sha(out / "ic_result.jsonl") if ic else None,
                     "in_process_verified": ic_valid, "online_ms": ic_ms},
              "rho": {"process": rho_process, "result_sha256": sha(out / "rho.stdout.txt"),
                      "in_process_verified": rho_valid, "online_ms": rho_ms,
                      "policy": "one_worker_signed_frobenius_r_adding_walk_no_cross_target_table",
                      "distinguished_point_memory_bytes": 0,
                      "walk_steps": rho.get("walk_steps") if rho else None,
                      "table_entries": rho.get("table_entries") if rho else None},
              "online_speedup_in_process_only": rho_ms / ic_ms if ic_ms and rho_ms else None,
              "resource_envelope": {"workers": 1, "wall_limit_seconds_each": args.wall_seconds,
                                    "memory_limit_bytes": None, "host": platform.platform()},
              "source_sha256": receipt_source_hashes, "binary_sha256": binaries,
              "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
              "base_export_sha256": sha(REPS),
              "claim_boundary": "Paired one-target clocks; independent Sage replay required before a verified comparison."}
    save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in ("status", "candidate_id", "workload_id",
                                                 "target_point", "online_speedup_in_process_only")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
