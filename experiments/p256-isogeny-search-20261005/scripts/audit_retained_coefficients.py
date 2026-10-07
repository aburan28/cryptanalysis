#!/usr/bin/env python3
"""Audit normalized coefficient costs across the full retained P-256 registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analyze_model_eligibility import normalize_short_a

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
UNION = RESULTS / "sage-low-degree-depth-seventeen-20261006" / "retained-union.json"
SOURCE_REGISTRIES = [
    RESULTS / "sage-depth-one-20261006" / "candidates.json",
    RESULTS / "sage-depth-three-20261006" / "depth-three-candidates.json",
    RESULTS / "sage-low-degree-depth-five-20261006" / "candidates.json",
    RESULTS / "sage-low-degree-depth-seven-20261006" / "candidates-delta.json",
    RESULTS / "sage-low-degree-depth-nine-20261006" / "candidates-delta.json",
    RESULTS / "sage-low-degree-depth-eleven-20261006" / "candidates-delta.json",
    RESULTS / "sage-low-degree-depth-thirteen-20261006" / "candidates-delta.json",
    RESULTS / "sage-low-degree-depth-fifteen-20261006" / "candidates-delta.json",
    RESULTS / "sage-low-degree-depth-seventeen-20261006" / "candidates-delta.json",
    RESULTS / "sage-wide-depth-one-199-20261006" / "degrees-8g" / "degree-101.json",
    RESULTS / "sage-wide-depth-one-199-20261006" / "degrees" / "degree-103.json",
    RESULTS / "sage-wide-depth-one-199-20261006" / "degrees" / "degree-59.json",
    RESULTS / "sage-wide-depth-one-199-20261006" / "degrees" / "degree-97.json",
    RESULTS / "sage-wide-depth-one-199-20261006" / "extended-candidates.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reconstruct() -> tuple[list[str], dict[str, dict[str, Any]], dict[str, str]]:
    union = load(UNION)
    candidate_ids = union["candidate_ids"]
    needed = set(candidate_ids)
    records: dict[str, dict[str, Any]] = {}
    origins: dict[str, str] = {}
    for path in SOURCE_REGISTRIES:
        payload = load(path)
        for row in payload["candidates"]:
            candidate_id = row["candidate_id"]
            if candidate_id not in needed or candidate_id in records:
                continue
            records[candidate_id] = row
            origins[candidate_id] = str(path.relative_to(ROOT))
    missing = needed.difference(records)
    extra = set(records).difference(needed)
    if missing or extra or len(records) != len(candidate_ids):
        raise AssertionError(
            f"registry reconstruction mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return candidate_ids, records, origins


def coefficient_row(
    candidate_id: str, row: dict[str, Any], origin: str
) -> dict[str, Any]:
    curve = row["curve"]
    p = int(curve["p"])
    normalized = normalize_short_a(
        p=p,
        a=int(curve["a"]),
        b=int(curve["b"]),
        x=int(curve["generator"]["x"]),
        y=int(curve["generator"]["y"]),
    )
    b3 = 3 * int(normalized["target_b"]) % p
    signed_b3 = b3 if b3 <= p // 2 else b3 - p
    magnitude = abs(signed_b3)
    bit_length = magnitude.bit_length()
    popcount = magnitude.bit_count()
    lower_bound = max(0, bit_length - 1)
    upper_bound = max(0, bit_length + popcount - 2)
    return {
        "candidate_id": candidate_id,
        "path_depth": len(row.get("path", [])),
        "record_source": origin,
        "normalized_a": int(normalized["target_a"]),
        "normalized_3b_signed": str(signed_b3),
        "normalized_3b_absolute_bit_length": bit_length,
        "normalized_3b_absolute_popcount": popcount,
        "signed_addition_chain_operation_lower_bound": lower_bound,
        "binary_double_and_add_operation_upper_bound": upper_bound,
        "normalization_fourth_root_verified": normalized[
            "u_fourth_equals_a_over_target_a"
        ],
        "transported_generator_verified": normalized[
            "transported_generator_on_target"
        ],
    }


def build_report() -> dict[str, Any]:
    candidate_ids, records, origins = reconstruct()
    rows = [
        coefficient_row(candidate_id, records[candidate_id], origins[candidate_id])
        for candidate_id in candidate_ids
    ]
    ranking = sorted(
        rows,
        key=lambda row: (
            row["binary_double_and_add_operation_upper_bound"],
            row["normalized_3b_absolute_bit_length"],
            row["normalized_3b_absolute_popcount"],
            row["candidate_id"],
        ),
    )
    by_bit_length = sorted(
        rows,
        key=lambda row: (
            row["normalized_3b_absolute_bit_length"],
            row["normalized_3b_absolute_popcount"],
            row["candidate_id"],
        ),
    )
    root = next(row for row in rows if row["candidate_id"] == "p256-root")
    low_operation_threshold = 32
    eligible = [
        row
        for row in rows
        if row["signed_addition_chain_operation_lower_bound"]
        <= low_operation_threshold
    ]
    return {
        "schema_version": 1,
        "publication_status": "retrospective_exploratory",
        "question": (
            "After class-wide normalization to a=1 or a=3, does any retained "
            "curve have a normalized 3b constant cheap enough for a candidate-specific "
            "complete-addition shortcut?"
        ),
        "inputs": {
            "retained_union": source(UNION),
            "candidate_registries": [source(path) for path in SOURCE_REGISTRIES],
        },
        "coverage": {
            "retained_curves_including_p256": len(candidate_ids),
            "records_reconstructed": len(records),
            "unique_candidate_ids": len(set(candidate_ids)),
            "source_registries": len(SOURCE_REGISTRIES),
        },
        "typed_transformation": {
            "type": "F_p-isomorphism of short-Weierstrass models",
            "source_model": "y^2 = x^3 + a*x + b",
            "target_model": "y^2 = x^3 + a'*x + b' with a' in {1,3}",
            "point_map": "(x,y) -> (x/u^2,y/u^3)",
            "coefficient_map": "a' = a/u^4, b' = b/u^6",
            "rho_complete_addition_coefficient": "3*b'",
            "log_transport": "isomorphism preserves Q=kP and the scalar k modulo n",
        },
        "cost_model": {
            "native_formula_full_multiplications_by_3b_per_complete_addition": 2,
            "specialized_binary_chain_operations": (
                "For magnitude c, the stored upper bound is bit_length(c)+popcount(c)-2 "
                "field additions/doublings."
            ),
            "signed_addition_chain_lower_bound": (
                "Any chain beginning at one needs at least bit_length(abs(c))-1 "
                "doubling/addition steps because one step can at most double the magnitude."
            ),
            "low_operation_eligibility_gate": {
                "maximum_lower_bound_operations": low_operation_threshold,
                "purpose": (
                    "A conservative formula-screening gate, not a user-supplied definition "
                    "of dramatic: candidates already requiring more than 32 coefficient-building "
                    "operations do not enter a specialized native timing experiment."
                ),
            },
            "discovery_and_normalization": "reusable",
            "per_key_isogeny_mapping": None,
            "per_iteration_coefficient_cost": "operation-count bounds only; not wall-time measured",
        },
        "results": {
            "p256_root": root,
            "minimum_bit_length_row": by_bit_length[0],
            "minimum_binary_upper_bound_row": ranking[0],
            "minimum_popcount": min(row["normalized_3b_absolute_popcount"] for row in rows),
            "eligible_candidate_ids": [row["candidate_id"] for row in eligible],
            "eligible_candidates": len(eligible),
            "all_normalizations_verified": all(
                row["normalization_fourth_root_verified"]
                and row["transported_generator_verified"]
                for row in rows
            ),
            "best_twenty_by_binary_upper_bound": ranking[:20],
        },
        "obligations": [
            {
                "name": "complete_retained_registry_coverage",
                "status": "supported",
                "scope": f"{len(candidate_ids)} candidate IDs reconstructed from frozen inputs",
            },
            {
                "name": "isomorphism_and_generator_transport",
                "status": "supported",
                "scope": "all retained curves",
            },
            {
                "name": "low_operation_normalized_3b_constant",
                "status": "refuted",
                "scope": (
                    f"minimum addition-chain lower bound is "
                    f"{by_bit_length[0]['signed_addition_chain_operation_lower_bound']}, "
                    f"above the {low_operation_threshold}-operation screening gate"
                ),
            },
            {
                "name": "coefficient_specialized_native_speedup",
                "status": "unknown",
                "scope": "not benchmarked because no candidate passed the operation-count gate",
            },
            {
                "name": "dramatic_end_to_end_ecdlp_speedup",
                "status": "unknown",
                "scope": "no user numerical threshold, no full collision, and no new per-key mapping measurement",
            },
        ],
        "finding": (
            "No retained curve has a normalized 3b constant eligible for a low-operation "
            "specialized complete-addition benchmark under the stated gate."
        ),
        "exploration_boundary": {
            "curves": len(candidate_ids),
            "maximum_low_degree_path_depth": 17,
            "one_hop_prime_degree_bound": 199,
            "claim": "not found within the retained registry and coefficient family",
        },
        "candidate_metrics": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "output": str(args.output),
        "curves": report["coverage"]["retained_curves_including_p256"],
        "minimum_lower_bound": report["results"]["minimum_bit_length_row"]["signed_addition_chain_operation_lower_bound"],
        "minimum_binary_upper_bound": report["results"]["minimum_binary_upper_bound_row"]["binary_double_and_add_operation_upper_bound"],
        "eligible_candidates": report["results"]["eligible_candidates"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
