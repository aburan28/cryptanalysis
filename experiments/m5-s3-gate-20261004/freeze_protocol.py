#!/usr/bin/env python3
"""Freeze Q1417 inputs and source identities before any SAT measurement."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
S3 = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(S3))
from run_probe import base_record, curve_record, sha  # noqa: E402


SOURCES = (
    "experiments/m5-s3-gate-20261004/build_m5.py",
    "experiments/m5-s3-gate-20261004/run_gate.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/cofactor_preimages.py",
    "experiments/compact-s3-m4-20261003/run_group_add_probe.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
)


def build() -> dict:
    runtime_path = HERE / "sage_runtime_info.json"
    assert runtime_path.is_file()
    binary = Path(shutil.which("cryptominisat5") or "")
    assert binary.is_file()
    version = subprocess.check_output([str(binary), "--version"],
                                      text=True).splitlines()
    assert any("CryptoMiniSat version 5.14.7" in line for line in version)
    profiles = {}
    for n, weight in ((53, 3), (83, 4)):
        manifest_path, candidate = curve_record(n)
        base_path, fb = base_record(n, weight, candidate)
        ordinary_path = S3 / "runs" / f"n{n}_ordinary_frozen.json"
        preimage_path = S3 / "runs" / f"n{n}_ordinary_raw_preimages.json"
        ordinary = json.loads(ordinary_path.read_text())
        preimages = json.loads(preimage_path.read_text())
        cofactor = int(candidate["curve"]["cofactor"])
        assert ordinary["curve_id"] == candidate["curve"]["curve_id"]
        assert preimages["curve_id"] == ordinary["curve_id"]
        assert preimages["workload_id"] == ordinary["workload_id"]
        assert preimages["cofactor"] == cofactor
        assert preimages["raw_target_preimage_count"] == cofactor
        profiles[str(n)] = {
            "curve_id": ordinary["curve_id"],
            "ordinary_workload_id": ordinary["workload_id"],
            "normal_basis_weight_bound": weight,
            "cofactor": cofactor,
            "actual_B": fb["actual_usable_points_B_before_folding"],
            "folded_columns_K": fb["signed_frobenius_columns"],
            "base_digest": fb["enumerated_set_sha256"],
            "curve_manifest_sha256": sha(manifest_path),
            "base_archive_sha256": sha(base_path),
            "ordinary_receipt_sha256": sha(ordinary_path),
            "ordinary_preimages_sha256": sha(preimage_path),
            "kernel_seed": 141700 + n,
            "planted_seed": 141750 + n,
        }
    return {
        "schema_version": 1,
        "revision": 2,
        "supersedes_protocol_sha256": sha(
            HERE / "protocol_preexec_failure.json"),
        "kind": "frozen_bounded_five_summand_s3_pdp_gate",
        "proposal_id": "Q1417",
        "candidate_id": None,
        "isogeny": "none",
        "stage_code": "PDP5sat",
        "summands_m": 5,
        "equation_chain": "four factored S3 links with three free intermediate x coordinates and one SAT-selected complete raw cofactor preimage",
        "profiles": profiles,
        "run_grid": [
            {"n": n, "mode": mode}
            for n in (53, 83)
            for mode in ("planted_locked", "planted_unpinned", "ordinary")
        ],
        "limits": {
            "external_wall_seconds": {
                "planted_locked": 30,
                "planted_unpinned": 60,
                "ordinary": 120,
            },
            "max_conflicts": 1_000_000,
            "max_models": 3,
            "solver_sampled_rss_stop_bytes": 4 * (1 << 30),
            "solver_rss_sample_interval_ms": 50,
        },
        "solver": {
            "family": "cryptominisat5",
            "binary_path": str(binary),
            "binary_sha256": sha(binary),
            "version_first_lines": version[:2],
            "threads": 1,
            "rss_monitor_library": "psutil 7.2.2",
        },
        "source_sha256": {name: sha(ROOT / name) for name in SOURCES},
        "sage_runtime_info_sha256": sha(runtime_path),
        "target_policy": "one archived previously unseen ordinary public subgroup point per field; deterministic planted target only for correctness control",
        "claim_gate": {
            "planted_control_is_natural_yield": False,
            "single_ordinary_query_estimates_yield_rate": False,
            "stage_result_is_complete_dlp": False,
            "unisolated_wall_ratio_is_speedup": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
        },
    }


def main() -> None:
    output = HERE / "protocol.json"
    assert not output.exists(), "refusing to overwrite the frozen protocol"
    output.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
