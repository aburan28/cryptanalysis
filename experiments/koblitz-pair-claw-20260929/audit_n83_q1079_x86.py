#!/usr/bin/env python3
"""Audit an archived physical-x86 Q1079 bounded rectangle receipt."""

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bench_n83_zero_run_stage import FROZEN, generated_sources  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(bundle, binary, run_id, artifact_digest, head_sha):
    full_path = bundle / "full.json"
    host_path = bundle / "host.json"
    sage_path = bundle / "sage_verify.json"
    workflow_path = bundle / "workflow_snapshot.yml"
    full = json.loads(full_path.read_text())
    host = json.loads(host_path.read_text())
    sage = json.loads(sage_path.read_text())
    reference = json.loads((HERE / "runs/n83_portable_controls_r3.json").read_text())[
        "public_native_result"]
    base = json.loads((HERE / "n83_full_spill_screen.json").read_text())
    assert host["host_arch"] == "x86_64" and host["cpu_pclmul_available"]
    assert full["cpu_backend"] == "x86_pclmul"
    assert full["proposal_id"] == sage["proposal_id"] == "Q1079"
    assert full["candidate_id"] is sage["candidate_id"] is None
    assert full["run_id"] is None
    assert full["curve_id"] == sage["curve_id"] == host["curve_id"] == base["curve_id"]
    assert full["isogeny"] == sage["isogeny"] == host["isogeny"] == "none"
    fb = base["factor_base"]
    assert full["factor_base"] == fb
    assert fb["enumerated_set_sha256"] == host[
        "factor_base_enumerated_set_sha256"]
    assert fb["actual_usable_points_B_before_folding"] == 8000204
    assert fb["signed_frobenius_columns"] == 48194
    assert full["keyer_variant"] == "exact_longest_zero_run"
    assert full["wrapper_source_sha256"] == host["runner_source_sha256"] == sha(
        HERE / "run_n83_zero_run_chunk.py")
    assert full["zero_run_source_generator_sha256"] == host[
        "source_generator_sha256"] == sha(HERE / "bench_n83_zero_run_stage.py")
    assert host["workflow_sha256"] == sha(workflow_path)
    assert host["screen_sha256"] == sha(HERE / "n83_full_spill_screen.json")
    assert full["generated_field_sha256"] == sha(bundle / "sources/eccF83.h")
    assert full["compiled_binary_sha256"] == sha(binary)
    assert full["table_descriptors"] == 1 << 20
    assert full["query_representatives"] == 1 << 14
    assert full["table_start"] == 0 and full["query_start"] == 1 << 30
    assert full["bits_per_key"] == 20 and full["hashes"] == 10
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    with tempfile.TemporaryDirectory() as temp:
        generated = generated_sources(Path(temp))
        for source, archived in zip(generated, (
            bundle / "sources/alt_pairs.cpp", bundle / "sources/alt_core.hpp",
            bundle / "sources/alt_main.cpp")):
            assert sha(source) == sha(archived)
    for key, archived in (
        ("native_pairs_sha256", "alt_pairs.cpp"),
        ("bloom_core_sha256", "alt_core.hpp"),
        ("native_source_sha256", "alt_main.cpp"),
    ):
        assert full[key] == sha(bundle / "sources" / archived)
    checked = ("actual_B", "table_descriptors", "query_representatives",
               "lifted_query_pairs", "bloom_positive_queries",
               "duplicate_positive_keys", "exact_hit_keys", "exact_hit_queries",
               "false_positive_queries", "complement_identity_queries", "hits")
    assert all(full["native_result"][key] == reference[key] for key in checked)
    native = full["native_result"]
    assert native["bloom_positive_queries"] == 247
    assert native["exact_hit_queries"] == 0
    assert not full["verified_public_target_quotient_table_dlp"]
    assert sage["receipt_sha256"] == sha(full_path)
    assert sage["verified_relation_count"] == 0
    assert not sage["natural_public_target_relation_verified"]
    m, r = full["table_descriptors"], full["query_representatives"]
    inversions = 2 * math.ceil(m / 1024) + 2 * math.ceil(r / 8)
    calls = 26 * m + 13 * r + 13 * 83 * r + 90 * inversions
    assert str(calls) == full["native_field_add_mul_sqr_call_model"]
    assert math.isclose(math.log2(calls), full[
        "native_field_add_mul_sqr_call_model_log2"], abs_tol=1e-12)
    return {
        "kind": "n83_q1079_physical_x86_bounded_runner_audit",
        "proposal_id": "Q1079", "candidate_id": None, "run_id": None,
        "curve_id": full["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "github_run_id": run_id,
        "github_run_url": f"https://github.com/aburan28/cryptanalysis/actions/runs/{run_id}",
        "head_sha": head_sha,
        "github_artifact_digest": artifact_digest,
        "physical_backend": "x86_64 Linux PCLMUL",
        "table_descriptors": m,
        "query_representatives": r,
        "bloom_positive_queries": native["bloom_positive_queries"],
        "exact_hit_queries": 0,
        "natural_relation_yield": False,
        "complete_solve_work_log2": None,
        "bounded_field_call_model_log2": math.log2(calls),
        "target_online_seconds": full["target_online_seconds"],
        "limits": "one M20/R14 bounded control; no natural relation or full-size performance",
        "host_sha256": sha(host_path),
        "receipt_sha256": sha(full_path),
        "sage_verify_sha256": sha(sage_path),
        "workflow_snapshot_sha256": sha(workflow_path),
        "compiled_binary_sha256": sha(binary),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite audit"
    result = audit(args.bundle, args.binary, args.run_id,
                   args.artifact_digest, args.head_sha)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
