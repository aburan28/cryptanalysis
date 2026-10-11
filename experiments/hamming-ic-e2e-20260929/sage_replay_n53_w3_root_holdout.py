#!/usr/bin/env python3
"""Independently replay every frozen N53 ordinary-query panel witness."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from math import sqrt
from pathlib import Path
import subprocess

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime

HERE = Path(__file__).resolve().parent
REPS = HERE / "runs/n53_w3_base_export_v1/representatives.json"
EXPORT_RECEIPT = HERE / "runs/n53_w3_base_export_v1/receipt.json"
N, R, COFACTOR = 53, 21044858204113, 428
GENERATOR = (198217578752339, 7929897206038174)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def wilson(successes, total, z=1.959963984540054):
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def main(run):
    run = run.resolve()
    receipt = json.loads((run / "receipt.json").read_text())
    workload = json.loads((run / "workload.json").read_text())
    audit = json.loads((run / "fixture_audit.json").read_text())
    public_points = json.loads((run / "public_points.json").read_text())
    raw_lines = (run / "result.jsonl").read_text().splitlines()
    entries = [json.loads(line) for line in raw_lines]
    assert receipt["status"] == "PANEL_COMPLETE_PENDING_SAGE_REPLAY"
    assert receipt["result_sha256"] == sha(run / "result.jsonl")
    assert receipt["public_input_sha256"] == sha(run / "public_points.json")
    assert receipt["fixture_audit_sha256"] == sha(run / "fixture_audit.json")
    assert receipt["runtime_info_sha256"] == sha(run / "sage_runtime_info.json")
    assert receipt["source_sha256"]["representatives"] == sha(REPS)
    assert receipt["source_sha256"]["rust_example"] == sha(HERE / "koblitz_w3_root_holdout.rs")
    assert receipt["source_sha256"]["runner"] == sha(HERE / "run_n53_w3_root_holdout.py")
    assert receipt["binary_sha256"] == sha(run / "solver_binary")
    assert receipt["workload_id"] == workload["workload_id"] == digest(workload["record"])[:12]
    assert workload["record"]["public_points"] == public_points
    assert len(audit["scalars_not_given_to_solver"]) == len(public_points)
    assert len(entries) == len(public_points) + 1

    precommit = None
    if (run / "precommit_provenance.json").exists():
        precommit = json.loads((run / "precommit_provenance.json").read_text())
        manifest_bytes = (run / "precommit_manifest.json").read_bytes()
        committed_bytes = subprocess.check_output(
            ["git", "show", f"{precommit['freeze_commit']}:{precommit['manifest_repo_path']}"],
            cwd=HERE.parents[1],
        )
        assert manifest_bytes == committed_bytes
        assert hashlib.sha256(committed_bytes).hexdigest() == precommit["manifest_sha256"]
        manifest = json.loads(manifest_bytes)
        assert manifest["kind"] == "n53_w3_root_precommitted_ordinary_query_panel"
        assert manifest["public_points"] == public_points
        assert manifest["query_count"] == len(public_points)
        assert manifest["solver_input_sha256"] == receipt["public_input_sha256"]
        assert precommit["executed_public_input_sha256"] == receipt["public_input_sha256"]
        assert precommit["run_workload_id"] == receipt["workload_id"]
        source_commit = manifest["source_commit_before_panel_freeze"]
        material = f"N53-W3-ROOT-PRECOMMITTED-HOLDOUT-v1|{source_commit}".encode()
        assert int.from_bytes(hashlib.sha256(material).digest(), "big") == \
               manifest["fixture_seed_decimal"] == workload["record"]["fixture_seed"]
        subprocess.run(["git", "merge-base", "--is-ancestor", source_commit,
                        precommit["freeze_commit"]], cwd=HERE.parents[1], check=True)
        for key, relative in (("runner", "run_n53_w3_root_holdout.py"),
                              ("rust_example", "koblitz_w3_root_holdout.rs")):
            old = subprocess.check_output(
                ["git", "show", f"{precommit['freeze_commit']}:"
                 f"experiments/hamming-ic-e2e-20260929/{relative}"],
                cwd=HERE.parents[1],
            )
            assert hashlib.sha256(old).hexdigest() == receipt["source_sha256"][key]

    ring = PolynomialRing(GF(2), "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**6 + u**2 + u + 1)
    z = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert is_prime(R) and curve.cardinality() == R * COFACTOR

    def element(bits):
        return sum((z**i for i in range(N) if bits >> i & 1), field(0))

    def encode(value):
        return sum(int(coefficient) << i
                   for i, coefficient in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(element(pair[0]), element(pair[1]))

    generator = point(GENERATOR)
    assert generator != curve(0) and R * generator == curve(0)
    reps = json.loads(REPS.read_text())
    export = json.loads(EXPORT_RECEIPT.read_text())
    lam = reps["lambda_mod_r"]
    base, ordered_entries = [], []
    for column, pair in enumerate(reps["representatives"]):
        current = point(pair)
        coefficient = 1
        assert lam * current == curve(current[0]**2, current[1]**2)
        for _ in range(N):
            for signed, label in ((current, coefficient), (-current, -coefficient % R)):
                base.append(signed)
                ordered_entries.append([encode(signed[0]), encode(signed[1]), column, label])
            current = curve(current[0]**2, current[1]**2)
            coefficient = coefficient * lam % R
        assert [encode(current[0]), encode(current[1])] == pair
    assert digest(ordered_entries) == export["ordered_labeled_entries_sha256"]
    header, rows = entries[0], entries[1:]
    assert header["kind"] == "n53_w3_root_ordinary_query_panel_header"
    assert header["factor_base_points"] == len(base) == 23426
    assert header["orbit_columns"] == len(reps["representatives"]) == 221
    assert header["query_count"] == len(public_points)
    assert receipt["header"] == header

    statuses = Counter()
    for index, (pair, scalar, row) in enumerate(zip(public_points,
                                                     audit["scalars_not_given_to_solver"], rows)):
        public_point = point(pair)
        assert public_point != curve(0) and R * public_point == curve(0)
        assert scalar * generator == public_point
        assert row["kind"] == "n53_w3_root_ordinary_query"
        assert row["query_index"] == index and row["target_point"] == pair
        status = row["status"]
        statuses[status] += 1
        assert row["query_wall_ms"] >= row["extraction_ms"] >= 0
        assert row["validation_ms"] >= 0
        assert 0 <= row["state_probes"] <= header["regular_index_states"]
        if status == "VERIFIED_DECOMPOSITION":
            indices = row["point_indices"]
            assert row["group_verified"] is True
            assert len(indices) == 4 and all(0 <= j < len(base) for j in indices)
            assert sum((base[j] for j in indices), curve(0)) == public_point
            assert row["x_codes"] == [encode(base[j][0]) for j in indices]
            assert row["state_probes"] > 0
        elif status == "NO_DECOMPOSITION_FOUND":
            assert row["group_verified"] is False
            assert row["point_indices"] is None and row["x_codes"] is None
            assert row["state_probes"] == header["regular_index_states"]
        else:
            raise AssertionError(f"unexpected holdout status {status} at query {index}")
    assert dict(statuses) == receipt["status_counts"]
    successes = statuses["VERIFIED_DECOMPOSITION"]
    report = {
        "schema_version": 1, "kind": "n53_w3_root_ordinary_pdp_holdout_sage_replay",
        "status": "PASS", "workload_id": receipt["workload_id"],
        "parent_candidate_id": receipt["parent_candidate_id"],
        "query_count": len(rows), "status_counts": dict(statuses),
        "independently_verified_witnesses": successes,
        "ordinary_query_completion_fraction": successes / len(rows),
        "wilson_95_for_frozen_pseudorandom_fixture_law": wilson(successes, len(rows)),
        "interval_caveat": (
            "Descriptive binomial interval under an independent-uniform-point approximation; exact public points were committed before execution, but this is not a population guarantee"
            if precommit else
            "Descriptive binomial interval under an independent-uniform-point approximation; exact public points were not committed before execution, and this is not a population guarantee"
        ),
        "precommit_verified": precommit is not None,
        "precommit_freeze_commit": precommit["freeze_commit"] if precommit else None,
        "precommit_provenance_sha256": sha(run / "precommit_provenance.json") if precommit else None,
        "miss_semantics": "No decomposition found by this solver's full sampled-orientation index scan; not a mathematical nonexistence proof",
        "claim_boundary": "Stage diagnostic only; no DLP recovery, natural population theorem, or controlled CPU speedup",
        "result_sha256": sha(run / "result.jsonl"),
        "runtime_info_sha256": sha(run / "sage_runtime_info.json"),
        "replay_source_sha256": sha(Path(__file__)),
    }
    (run / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    main(parser.parse_args().run)
