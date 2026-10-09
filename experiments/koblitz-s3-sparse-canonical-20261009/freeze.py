#!/usr/bin/env python3
"""Freeze paired sparse-canonical and rotation binaries before runs."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CRYPTO = ROOT.parent / "crypto"
PREVIOUS = ROOT / "experiments/koblitz-s3-pair-query-20261006-v2"
PREFIX = "IC1N53Ckb1fb25864PDP4rootRCguidedLAgaussTDdirectISO0h"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def immutable(path: Path, value: dict) -> None:
    data = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text() != data:
            raise RuntimeError(f"frozen receipt changed: {path}")
    else:
        path.write_text(data)


def main() -> None:
    prior = json.loads((PREVIOUS / "candidate_manifest.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    assert workload["workload_id"] == "c3929365e014"
    assert hashlib.sha256(canonical(workload["record"])).hexdigest() == workload["identity_sha256"]
    assert sha(HERE / "reference.rs") == sha(PREVIOUS / "candidate.rs")
    assert json.loads((HERE / "target_point.json").read_text()) == workload["record"]["targets"][0]

    components = {
        "binary_curve_point_arithmetic": CRYPTO / "src/binary_ecc/curve.rs",
        "binary_field_arithmetic": CRYPTO / "src/cryptanalysis/semaev_decomp.rs",
        "fast_binary_curve_arithmetic": CRYPTO / "src/cryptanalysis/koblitz_fast_arith.rs",
        "koblitz_curve_and_subgroup_definition": CRYPTO / "src/cryptanalysis/koblitz_index_calculus.rs",
        "cargo_manifest": HERE / "Cargo.toml",
        "cargo_lock": HERE / "Cargo.lock",
        "dependency_cargo_manifest": CRYPTO / "Cargo.toml",
        "dependency_cargo_lock": CRYPTO / "Cargo.lock",
    }
    source_hashes = {name: sha(path) for name, path in components.items()}
    frozen = {}
    for variant, stem in (("reference", "reference"), ("sparse", "candidate")):
        source = HERE / f"{stem}.rs"
        binary = HERE / "target/release" / f"s3-canonical-{variant}"
        if not binary.is_file():
            raise RuntimeError(f"missing release binary: {binary}")
        source_hash, binary_hash = sha(source), sha(binary)
        record = copy.deepcopy(prior["identity_record"])
        impl = record["implementation"]
        impl["build_command"] = "cargo build --release --offline --quiet"
        impl["executable_sha256"] = binary_hash
        impl["source_component_sha256"].update(source_hashes)
        impl["source_component_sha256"]["slice_ic_example"] = source_hash
        impl["algorithm_affecting_flags"]["normal_basis_canonicalization"] = (
            "longest cyclic zero gap with lexicographic and minimum-shift tie break"
            if variant == "sparse" else "all 53 rotations with minimum-shift tie break")
        record["point_decomposition"]["implementation_version"] += (
            "; sparse normal-basis canonicalization" if variant == "sparse"
            else "; same-dependency rotation reference rebuild")
        record["point_decomposition"]["cache_policy"] = (
            "build factor base and S3 index once per process; no cross-run shared cache")
        record["relation_collection"]["filtering"] = (
            "S3-root candidate, exact canonical root-table lookup, factor-base x-bucket lift, exact group-sum check")
        for section in ("point_decomposition", "relation_collection", "relation_linear_algebra", "target_descent"):
            record[section]["source_digest"] = source_hash
        digest = hashlib.sha256(canonical(record)).hexdigest()
        candidate_id = PREFIX + digest[:12]
        manifest = {
            "candidate_id": candidate_id,
            "identity_sha256": digest,
            "identity_record": record,
            "candidate_freeze": {
                "kind": "pre-run-frozen-candidate",
                "source_path": str(source), "source_sha256": source_hash,
                "binary_path": str(binary), "binary_sha256": binary_hash,
                "workload_path": str(HERE / "workload.json"),
                "workload_id": workload["workload_id"],
                "target_path": str(HERE / "target_point.json"),
                "target_sha256": sha(HERE / "target_point.json"),
                "resource_envelope": workload["record"]["resource_envelope"],
            },
        }
        immutable(HERE / f"{variant}_manifest.json", manifest)
        frozen[variant] = {"candidate_id": candidate_id,
                           "manifest_sha256": sha(HERE / f"{variant}_manifest.json")}
    immutable(HERE / "freeze_receipt.json", {
        "kind": "sparse_canonical_pre_run_freeze",
        "workload_id": workload["workload_id"],
        "workload_sha256": sha(HERE / "workload.json"),
        "target_sha256": sha(HERE / "target_point.json"),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"),
        "variants": frozen,
    })
    print(json.dumps(frozen, sort_keys=True))


if __name__ == "__main__":
    main()
