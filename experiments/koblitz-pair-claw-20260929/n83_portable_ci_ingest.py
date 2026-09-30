#!/usr/bin/env python3
"""Verify and archive one physical-x86 Q1061 full-segment CI artifact."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
SOURCE = HERE / "native_n83_orbit_query_spill_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
PAIRS = HERE / "native_n83_pairs_portable.cpp"
WRAPPER = HERE / "run_n83_portable_chunk.py"
R27 = 1 << 27
R30 = 1 << 30


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_row(screen, path, *, full):
    row = json.loads(path.read_text())
    validate_receipt(screen, row)
    assert row["kind"] == (
        "n83_public_target_signed_x_query_k48194_exact_replay_chunk")
    assert row["proposal_id"] == "Q1061"
    assert row["cpu_backend"] == "x86_pclmul"
    assert row["table_start"] == 0
    assert row["table_descriptors"] == (1 << (31 if full else 20))
    assert row["query_representatives"] == (R27 if full else 1 << 14)
    assert row["query_workers"] == 4 and row["representative_batch"] == 8
    assert row["bits_per_key"] == 20 and row["hashes"] == 10
    assert row["candidate_spill_enabled"] and row["fast_keyer_enabled"]
    assert row["native_source_sha256"] == sha(SOURCE)
    assert row["bloom_core_sha256"] == sha(CORE)
    assert row["native_pairs_sha256"] == sha(PAIRS)
    assert row["wrapper_source_sha256"] == sha(WRAPPER)
    native = row["native_result"]
    assert native["candidate_store_mode"] == "unlinked_file"
    assert native["table_descriptors"] == row["table_descriptors"]
    assert native["query_representatives"] == row["query_representatives"]
    assert native["query_start"] == row["query_start"]
    assert native["peak_rss_bytes"] >= native["bloom_bytes"]
    assert native["false_positive_queries"] == (
        native["bloom_positive_queries"] - native["exact_hit_queries"])
    assert int(row["native_field_add_mul_sqr_call_model"]) == field_calls(
        row["table_descriptors"], row["query_representatives"])
    assert row["verified_public_target_quotient_table_dlp"] == bool(
        row["verified_public_target_relations"])
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    assert args.run_id > 0
    artifact = args.artifact_dir.resolve()
    assert artifact.is_dir()
    host_path = artifact / "host.json"
    control_path = artifact / "control.json"
    full_path = artifact / "full.json"
    full_marker = artifact / "full.started.json"
    assert host_path.is_file() and control_path.is_file()
    assert not (full_path.exists() and full_marker.exists()), (
        "terminal full receipt retains start marker")
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    host = json.loads(host_path.read_text())
    assert host["kind"] == "n83_portable_R27_host_preflight"
    assert host["architecture"].lower() in ("x86_64", "amd64")
    assert host["mem_available_bytes"] >= host[
        "minimum_mem_available_bytes"] >= 6 << 30
    assert host["root_free_bytes"] >= host[
        "minimum_root_free_bytes"] >= 10 << 30
    query_start = host["query_start"]
    assert R30 <= query_start < 118 * R30 and query_start % R27 == 0
    control = verified_row(screen, control_path, full=False)
    assert control["query_start"] == query_start
    full = json.loads(full_path.read_text()) if full_path.exists() else None
    full_success = False
    if full is not None:
        if full["kind"] == (
                "n83_public_target_signed_x_query_k48194_exact_replay_chunk"):
            full = verified_row(screen, full_path, full=True)
            full_success = True
        else:
            assert full["kind"] == (
                "n83_public_target_signed_x_query_k48194_chunk_failed")
            validate_receipt(screen, full)
            assert full["proposal_id"] == "Q1061"
            assert full["native_phase_counts"] is None
            assert not full["verified_public_target_quotient_table_dlp"]
            assert full["cpu_backend"] == "x86_pclmul"
            assert full["native_source_sha256"] == sha(SOURCE)
            assert full["bloom_core_sha256"] == sha(CORE)
            assert full["native_pairs_sha256"] == sha(PAIRS)
            assert full["wrapper_source_sha256"] == sha(WRAPPER)
            assert full["table_descriptors"] == 1 << 31
            assert full["query_representatives"] == R27
            assert full["query_workers"] == 4
            assert full["representative_batch"] == 8
    if full is not None:
        assert full["query_start"] == query_start
        assert full["native_source_sha256"] == control[
            "native_source_sha256"]
        assert full["curve_identity_record"] == control["curve_identity_record"]
        if full_success:
            assert full["factor_base"] == control["factor_base"]
        else:
            assert full["factor_base_enumerated_set_sha256"] == control[
                "factor_base"]["enumerated_set_sha256"]
        assert full["public_target"] == control["public_target"]
    status = ("incomplete_no_terminal_full_receipt" if full is None else
              "failed_full_segment_unknown_work" if not full_success else
              "native_verified_hit_needs_independent_sage" if full[
                  "verified_public_target_quotient_table_dlp"] else
              "unverified_exact_hit_requires_review" if full[
                  "native_result"]["exact_hit_queries"] else
              "completed_zero_hit")
    destination = RUNS / f"n83_portable_q1061_M31_R27_ci_{args.run_id}"
    assert not destination.exists(), "refusing to overwrite archived CI artifact"
    destination.mkdir()
    names = ("host.json", "control.json", "full.json",
             "full.started.json")
    copied = {}
    for name in names:
        source = artifact / name
        if source.is_file():
            copied[name] = sha(source)
            shutil.copyfile(source, destination / name)
            assert sha(destination / name) == copied[name]
    bundle = {
        "kind": "n83_portable_q1061_physical_x86_segment_ci_bundle",
        "proposal_id": "Q1061", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "query_start": query_start,
        "query_representatives": R27,
        "github_run_id": args.run_id,
        "github_run_url": (
            f"https://github.com/aburan28/cryptanalysis/actions/runs/"
            f"{args.run_id}"),
        "status": status,
        "artifact_sha256": copied,
        "Q1062_identity_screen_sha256": sha(SCREEN),
        "portable_native_source_sha256": sha(SOURCE),
        "portable_wrapper_source_sha256": sha(WRAPPER),
        "source_sha256": sha(Path(__file__)),
    }
    (destination / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    print(json.dumps(bundle), flush=True)


if __name__ == "__main__":
    main()
