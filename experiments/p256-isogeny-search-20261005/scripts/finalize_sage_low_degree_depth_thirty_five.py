#!/usr/bin/env python3
"""Freeze reports and a receipt from completed depth-thirty-five evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from freeze_large_json import verify_archive

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
RESULTS = ROOT / "results"
STAGE = RESULTS / "sage-low-degree-depth-thirty-five-20261008"
CLASS_STATUS = RESULTS / "sage-class-group-20261006" / "status-depth-thirty-five.json"
CLASS_INTERRUPTION = (
    RESULTS
    / "sage-class-group-20261006"
    / "status-infrastructure-interruption-20261008.json"
)
PROTOCOL = ROOT / "protocol-depth-thirty-five-20261008.json"
MANIFEST = ROOT / "source-sage-low-degree-depth-thirty-five-20261008.sha256"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-thirty-five-20261008.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-parent-remote-commit", required=True)
    args = parser.parse_args()

    prior_union_path = (
        RESULTS
        / "sage-low-degree-depth-thirty-three-20261007"
        / "retained-union.json"
    )
    prior_receipt_path = ROOT / "receipt-sage-low-degree-depth-thirty-three-20261007.json"
    prior_positive_receipt_path = (
        ROOT / "receipt-sage-low-degree-depth-twenty-five-20261007.json"
    )
    delta_path = STAGE / "candidates-delta.json"
    delta_archive_path = STAGE / "candidates-delta.json.gz"
    delta_freeze_path = STAGE / "candidates-delta.freeze.json"
    union_path = STAGE / "retained-union.json"
    screen_path = STAGE / "native-screen" / "screening-summary.json"
    holdout_path = STAGE / "holdout.json"
    attempts_path = STAGE / "attempts.json"
    model_path = STAGE / "candidate-model-audit.json"
    coefficient_path = STAGE / "coefficient-audit.json"
    conductor_path = STAGE / "conductor-audit.json"
    mapping_path = STAGE / "mapping-holdout-positive.json"
    isolation_probe_path = STAGE / "isolation-probe.json"
    interrupted_screen_dir = STAGE / "native-screen-interrupted-environment-offline"

    delta = load(delta_path)
    union = load(union_path)
    screen = load(screen_path)
    holdout = load(holdout_path)
    attempts = load(attempts_path)
    model = load(model_path)
    coefficient = load(coefficient_path)
    conductor = load(conductor_path)
    isolation_probe = load(isolation_probe_path)
    prior_receipt = load(prior_receipt_path)
    prior_positive_receipt = load(prior_positive_receipt_path)
    class_status = load(CLASS_STATUS)
    class_interruption = load(CLASS_INTERRUPTION)
    protocol = load(PROTOCOL)
    freeze_manifest = load(delta_freeze_path)
    registry_verification = verify_archive(delta_archive_path, freeze_manifest)
    assert sha256(delta_path) == freeze_manifest["uncompressed"]["sha256"]

    hits = screen["unadjusted_screening_hits"]
    holdout_candidates = holdout["results"][1:]
    reproduced = [
        row
        for row in holdout_candidates
        if row["paired_speedup_significant_at_95_percent"]
    ]
    mapping_rows = load(mapping_path)["results"] if reproduced else []
    if not reproduced:
        assert not mapping_path.exists()
    assert [row["candidate_id"] for row in mapping_rows] == [
        row["candidate_id"] for row in reproduced
    ]
    assert isolation_probe["qualification"] == "not_qualified"
    assert prior_receipt["prior_positive_followup"]["status"] == (
        "open; local isolation probe failed"
    )
    assert prior_positive_receipt["holdout"]["reproduced_speedups"] == 1
    all_screen_relations = all(
        row["linear_relation_verified_every_trial"] for row in screen["results"]
    )
    all_holdout_relations = all(
        row["linear_relation_verified_every_trial"] for row in holdout["results"]
    )
    screen_elapsed = sum(
        load(ROOT / block["artifact"])["elapsed_wall_seconds"]
        for block in screen["blocks"]
    )
    largest = max(
        holdout_candidates,
        key=lambda row: row["paired_relative_iteration_speed"],
        default=None,
    )
    hit_speeds = [row["paired_relative_iteration_speed"] for row in hits]
    if mapping_rows:
        mapping_means = [row["per_key_mapping"]["mean_seconds"] for row in mapping_rows]
        mapping_text = (
            "The complete retained path was evaluated on both ECDLP points for every "
            f"new holdout-positive candidate. Mean per-key transfer times span "
            f"`{min(mapping_means):.6f}`-`{max(mapping_means):.6f}` seconds, and every "
            "endpoint generator and discrete-log relation verified."
        )
        mapping_cost_row = (
            f"| New positive path evaluation on `P` and `Q` | "
            f"{min(mapping_means):.6f}-{max(mapping_means):.6f} s/key | "
            "online per-key transfer; 25 samples of 50 repetitions |"
        )
    else:
        mapping_text = (
            "No new depth-34/35 candidate survived holdout, so no additional P,Q path "
            "evaluation was triggered. The depth-25 exploratory positive remains open "
            "for isolated replay, with its previously charged 0.011433-second per-key transfer."
        )
        mapping_cost_row = (
            "| New positive path evaluation on `P` and `Q` | not triggered | "
            "no new holdout-positive candidate |"
        )

    assessment_path = STAGE / "transfer-assessment.json"
    assessment = {
        "schema_version": 1,
        "status": "draft_evidence_assessment",
        "question": "Do depth-34/35 low-degree isogeny transfers from P-256 expose a reproducible Pollard-rho iteration-rate advantage?",
        "typed_correspondence": protocol["typed_transfer"],
        "artifacts": {
            "protocol": source(PROTOCOL),
            "candidate_registry_archive": source(delta_archive_path),
            "candidate_registry_freeze_manifest": source(delta_freeze_path),
            "candidate_registry_uncompressed": {
                "path": str(delta_path.relative_to(ROOT)),
                "sha256": freeze_manifest["uncompressed"]["sha256"],
                "bytes": freeze_manifest["uncompressed"]["bytes"],
                "publication": "materialize from deterministic archive",
            },
            "retained_union": source(union_path),
            "native_screen": source(screen_path),
            "holdout": source(holdout_path),
            "model_eligibility": source(model_path),
            "coefficient_audit": source(coefficient_path),
            "conductor_audit": source(conductor_path),
            **(
                {"holdout_positive_mapping": source(mapping_path)}
                if mapping_rows
                else {}
            ),
            "isolation_probe": source(isolation_probe_path),
            "exact_class_group_status": source(CLASS_STATUS),
            "exact_class_group_interruption": source(CLASS_INTERRUPTION),
            "prior_depth_thirty_three_receipt": source(prior_receipt_path),
            "prior_depth_twenty_five_positive_receipt": source(
                prior_positive_receipt_path
            ),
        },
        "obligations": [
            {
                "name": "existence",
                "status": "supported",
                "scope": "1,072 new explicit candidates",
            },
            {
                "name": "executable_construction",
                "status": "supported",
                "scope": "all edge kernels, maps, isomorphisms, and transported generators retained",
            },
            {
                "name": "map_correctness",
                "status": "supported",
                "scope": "Sage checks plus path continuity and degree-product verification",
            },
            {
                "name": "subgroup_preservation",
                "status": "supported",
                "scope": "prime-order checks, trivial kernel intersection, generator transport, and native scalar-relation checks",
            },
            {
                "name": "endomorphism_conductor",
                "status": "supported",
                "scope": "all 1,072 additions have exact conductor 1 and level-zero horizontal paths",
            },
            {
                "name": "measured_iteration_rate_advantage",
                "status": "supported_exploratory" if reproduced else "refuted_within_boundary",
                "scope": f"{len(hits)} screen hits; {len(reproduced)} fresh-holdout reproductions; local isolation gate failed",
            },
            {
                "name": "dramatic_speedup",
                "status": "unknown",
                "scope": "the user supplied no numerical threshold; report exact ratios only",
            },
            {
                "name": "host_isolated_speedup",
                "status": "unknown",
                "scope": "CPU affinity is not an isolation-service receipt",
            },
            {
                "name": "per_key_transfer_cost",
                "status": "supported",
                "scope": "complete retained path evaluated on P and Q for every new holdout-positive candidate; no transfer is triggered by a null holdout",
            },
            {
                "name": "full_class_coverage",
                "status": "unknown",
                "scope": "9,570 retained curves are bounded; exact class-group computation remains separate",
            },
        ],
        "controls": [
            "prospective protocol committed before candidate generation",
            "fresh P-256 baseline in every screening block",
            "identical native implementation for baseline and candidate",
            "complete execution-position rotation within every block",
            "tracked scalar relation verified after every timed trial",
            "fresh 30-by-2-second holdout containing every unadjusted screening hit",
            "candidate IDs deduplicated against the prior 8,498-curve union",
            "deterministic registry archive reproduced and verified against the uncompressed hash",
            "deterministic model, coefficient, and conductor replays",
        ],
        "costs": {
            "measured_seconds": {
                "reusable_depth_34_35_discovery": delta["search"]["elapsed_seconds"],
                "native_screen_blocks": screen_elapsed,
                "fresh_holdout": holdout["elapsed_wall_seconds"],
                "interrupted_exact_class_group": class_interruption[
                    "elapsed_lower_bound_seconds"
                ],
            },
            "per_key_mapping": {
                row["candidate_id"]: row["per_key_mapping"]
                for row in mapping_rows
            },
            "default_exact_class_group": class_status["status"],
            "modeled_costs": None,
        },
        "finding": (
            f"{len(reproduced)} exploratory iteration-rate advantage(s) survived holdout within depths 34 and 35; controlled isolation remains open."
            if reproduced
            else "No reproducible iteration-rate advantage was found within depths 34 and 35 using edge degrees 3, 5, 11, and 13. The separate depth-25 exploratory positive remains open for isolated replay."
        ),
        "exploration_boundary": {
            "new_curves": 1072,
            "combined_curves_including_p256": 9570,
            "combined_non_root_curves_with_native_measurements": 9569,
            "edge_degrees": [3, 5, 11, 13],
            "maximum_depth": 35,
            "claim": (
                "exploratory holdout-positive candidate found within this boundary"
                if reproduced
                else "not found within this family and boundary"
            ),
        },
        "open_obligations": [
            "finish and independently check the exact class-number calculation",
            "rerun any holdout-positive candidate under the repository host-isolation service",
            "supply and verify a genuinely non-generic ECDLP algorithm for an algorithmic speedup claim",
        ],
    }
    write_json(assessment_path, assessment)

    largest_text = "No screening candidate entered holdout."
    if largest is not None:
        ci = largest["paired_relative_iteration_speed_95_percent_ci"]
        largest_text = (
            f"The largest holdout estimate was `{largest['paired_relative_iteration_speed']:.4f}x` "
            f"with paired 95% interval `{ci[0]:.4f}x-{ci[1]:.4f}x`."
        )
    hit_range = "none"
    if hit_speeds:
        hit_range = f"{min(hit_speeds):.4f}x-{max(hit_speeds):.4f}x"
    summary = f"""# P-256 low-degree isogeny search through depth thirty-five

## Outcome

The prospectively frozen extension added 528 curves at depth thirty-four and 544
at depth thirty-five, with no overlap against the prior 8,498-curve union. The
explicit registry now contains P-256 plus 9,569 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as a deterministic gzip
archive whose manifest binds the compressed and uncompressed hashes and sizes.

All 1,072 additions received matched-native measurements in 179 root-controlled
blocks. {len(hits)} unadjusted short-screen hit(s), with point estimates in
`{hit_range}`, entered the frozen fresh 30-trial, two-second holdout. {len(reproduced)}
candidate(s) reproduced a positive interval. {largest_text}

{mapping_text}
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. Across all 9,570 retained
curves, 228,530 recorded path-edge occurrences are therefore horizontal at
level zero. The coefficient audit found a
minimum addition-chain lower bound of
`{coefficient['results']['minimum_bit_length_row']['signed_addition_chain_operation_lower_bound']}`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 1,072 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | Deterministic archive, uncompressed hash, and byte-identical repack verified. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | {'exploratory holdout-positive for ' + str(len(reproduced)) + ' candidate(s); controlled status unknown' if reproduced else 'not found within this boundary'} | {len(hits)} screen hit(s), {len(reproduced)} holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 35 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `{class_status['status']}` after an infrastructure restart. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-34/35 discovery | {delta['search']['elapsed_seconds']:.4f} s | discovery/precomputation |
| Native screening blocks | {screen_elapsed:.4f} s | exploratory per-iteration comparison |
| Fresh holdout | {holdout['elapsed_wall_seconds']:.4f} s | exploratory verification evidence |
{mapping_cost_row}
| Exact class-group attempt | {class_status['status']} | no result counted at this checkpoint |
| Interrupted exact class-group work | {class_interruption['elapsed_lower_bound_seconds']:.4f} s | infrastructure loss; no result counted |

CPU affinity separated native timing, traversal, and class-group work, but the
preserved probe shows that this host does not satisfy the repository isolation
gate. The attempts ledger records
all invocations, corrections, and any unsuccessful work in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result {'contains exploratory holdout-positive evidence but does not establish a controlled speedup' if reproduced else 'is `not found within this family and boundary`'}. It is not a universal
nonexistence result and does not enumerate the complete class group.
"""
    summary_path = STAGE / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    source_paths = [
        PROTOCOL,
        ROOT / "scripts" / "explore_sage.py",
        ROOT / "scripts" / "extend_sage_low_degree.py",
        ROOT / "scripts" / "assemble_sage_low_degree_depth_thirty_five.py",
        ROOT / "scripts" / "freeze_large_json.py",
        ROOT / "scripts" / "run_native_screen.py",
        ROOT / "scripts" / "run_native_holdout.py",
        ROOT / "scripts" / "benchmark_mapping_sage.py",
        ROOT / "scripts" / "audit_candidate_models.py",
        ROOT / "scripts" / "audit_candidate_coefficients.py",
        ROOT / "scripts" / "audit_candidate_coefficients_depth_thirty_five.py",
        ROOT / "scripts" / "audit_candidate_conductors.py",
        ROOT / "scripts" / "audit_candidate_conductors_depth_thirty_five.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_eleven.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_thirty_five.py",
        ROOT / "scripts" / "compute_class_group_sage.py",
        ROOT / "scripts" / "record_class_group_status.py",
        ROOT / "scripts" / "finalize_sage_low_degree_depth_thirty_five.py",
        REPOSITORY / "scripts" / "isolated_bench.py",
        REPOSITORY / "suite" / "examples" / "p256_isogeny_native_bench.rs",
        REPOSITORY / "suite" / "src" / "ecc" / "p256_field.rs",
        REPOSITORY / "suite" / "src" / "ct_bignum.rs",
        REPOSITORY / "suite" / "Cargo.toml",
        REPOSITORY / "suite" / "Cargo.lock",
    ]
    MANIFEST.write_text(
        "".join(
            f"{sha256(path)}  {Path(os.path.relpath(path, ROOT))}\n"
            for path in source_paths
        ),
        encoding="utf-8",
    )

    local_parent = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    native_binary = (
        REPOSITORY
        / "suite"
        / "target"
        / "release"
        / "examples"
        / "p256_isogeny_native_bench"
    )
    artifacts = [
        PROTOCOL,
        prior_receipt_path,
        prior_positive_receipt_path,
        prior_union_path,
        delta_archive_path,
        delta_freeze_path,
        union_path,
        screen_path,
        holdout_path,
        attempts_path,
        assessment_path,
        summary_path,
        model_path,
        coefficient_path,
        conductor_path,
        isolation_probe_path,
        CLASS_STATUS,
        CLASS_INTERRUPTION,
    ]
    if mapping_rows:
        artifacts.append(mapping_path)
    artifacts.extend(sorted(interrupted_screen_dir.glob("block-*.json")))
    receipt = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "status": "verified_exploratory_low_degree_depth_thirty_five",
        "claim": (
            "The prospectively frozen depth-thirty-five extension added 1,072 explicit curves "
            f"and measured every addition; {len(reproduced)} of {len(hits)} exploratory "
            "screen hits reproduced in the fresh holdout."
        ),
        "run_completed_at": iso_utc_now(),
        "source": {
            "pr_parent_remote_commit": args.pr_parent_remote_commit,
            "local_parent_commit": local_parent,
            "manifest": MANIFEST.name,
            "manifest_sha256": sha256(MANIFEST),
        },
        "runtime": {
            "sage_image": protocol["resources"]["sage_image"],
            "sage_image_digest": protocol["resources"]["sage_image_digest"],
            "native_release_binary_sha256": sha256(native_binary),
            "cpu_affinity": {
                "native_screen_and_holdout": "CPU 0",
                "sage_frontier_extension": "CPU 2",
                "concurrent_default_class_group_process": "CPU 4",
            },
            "host_isolation": protocol["resources"]["host_isolation"],
        },
        "commands": {
            "frozen_commands": protocol["commands"],
            "corrections": [
                "The frozen generic coefficient- and conductor-audit commands produced correct rows but their reusable scripts hard-coded depth-nineteen report labels. Depth-thirty-five wrappers replayed the same build_report results and corrected only those metadata labels. All invocations are preserved in attempts.json."
            ],
            "verify": "python3 scripts/verify_sage_low_degree_depth_thirty_five.py",
        },
        "artifacts": {str(path.relative_to(ROOT)): sha256(path) for path in artifacts},
        "registry_storage": {
            "working_path": str(delta_path.relative_to(ROOT)),
            "archive_path": str(delta_archive_path.relative_to(ROOT)),
            "manifest_path": str(delta_freeze_path.relative_to(ROOT)),
            "verification": registry_verification,
            "deterministic_repack_verified": True,
        },
        "search": {
            "ells": [3, 5, 11, 13],
            "input_depth": 33,
            "target_depth": 35,
            "new_depth_counts": {"34": 528, "35": 544},
            "new_non_root_curves": 1072,
            "overlap_with_prior_union": 0,
            "combined_unique_curves_including_p256": 9570,
            "explicit_paths_verified": True,
            "exceptional_automorphisms_found": False,
        },
        "screening": {
            "new_neighbors": 1072,
            "blocks": 179,
            "seconds_per_trial": 0.5,
            "candidate_trials": sum(
                block["trials_per_candidate"] * len(block["candidate_ids"])
                for block in screen["blocks"]
            ),
            "all_linear_relations_verified": all_screen_relations,
            "unadjusted_screening_hits": len(hits),
            "screening_point_estimate_range": (
                [min(hit_speeds), max(hit_speeds)] if hit_speeds else None
            ),
        },
        "holdout": {
            "candidates": len(holdout_candidates),
            "seconds_per_trial": 2.0,
            "trials_per_candidate": 30,
            "all_linear_relations_verified": all_holdout_relations,
            "reproduced_speedups": len(reproduced),
            "largest_point_estimate": (
                {
                    "candidate_id": largest["candidate_id"],
                    "paired_relative_iteration_speed": largest[
                        "paired_relative_iteration_speed"
                    ],
                    "paired_relative_iteration_speed_95_percent_ci": largest[
                        "paired_relative_iteration_speed_95_percent_ci"
                    ],
                }
                if largest is not None
                else None
            ),
        },
        "combined_native_coverage": {
            "explicit_curves_including_p256": 9570,
            "non_root_curves_with_matched_native_measurement": 9569,
            "endomorphism_conductor_one": 9570,
            "retained_path_edge_occurrences": 228530,
            "current_extension_reproduced_speedups": len(reproduced),
            "known_exploratory_holdout_positive_candidates": 1 + len(reproduced),
        },
        "prior_positive_followup": protocol["prior_positive_followup"],
        "conductor": conductor["coverage"],
        "coefficient_gate": {
            "eligible_candidates": coefficient["results"]["eligible_candidates"],
            "minimum_addition_chain_lower_bound": coefficient["results"][
                "minimum_bit_length_row"
            ]["signed_addition_chain_operation_lower_bound"],
            "minimum_binary_upper_bound": coefficient["results"][
                "minimum_binary_upper_bound_row"
            ]["binary_double_and_add_operation_upper_bound"],
        },
        "model_eligibility": {
            "target_a_counts": model["target_a_counts"],
            "all_candidate_normalizations_verified": (
                model["all_fourth_root_certificates_verified"]
                and model["all_transported_generators_on_target"]
            ),
        },
        "cost_accounting": {
            "discovery_and_reusable_precomputation_seconds": delta["search"][
                "elapsed_seconds"
            ],
            "native_screen_block_wall_seconds_total": screen_elapsed,
            "holdout_wall_seconds": holdout["elapsed_wall_seconds"],
            "interrupted_exact_class_group_wall_seconds_lower_bound": (
                class_interruption["elapsed_lower_bound_seconds"]
            ),
            "default_exact_class_group_attempt": (
                f"{class_status['status']} after at least "
                f"{class_status['elapsed_lower_bound_seconds']:.1f} seconds; no result counted"
            ),
            "per_instance_mapping": {
                row["candidate_id"]: row["per_key_mapping"]
                for row in mapping_rows
            },
            "amortization": "discovery and map parsing are reusable; complete P,Q path evaluation is charged per key",
        },
        "preserved_failures": attempts["attempts"],
        "limitations": [
            "the traversal stops at depth thirty-five and uses only edge degrees 3, 5, 11, and 13",
            "the retained registry is not the entire finite class-group orbit",
            "host-wide CPU isolation was not established",
            "the local isolation probe failed the repository host gate, so the positive timing remains exploratory",
            "screening intervals are unadjusted selection triggers",
            "no full P-256 collision was attempted or required by the protocol",
        ],
        "decision": (
            f"{len(reproduced)} holdout-positive candidate(s) require isolated and end-to-end follow-up."
            if reproduced
            else "No new candidate advances; all depth-34/35 screen hits failed the fresh holdout, while the separate depth-25 exploratory positive remains open for isolated replay."
        ),
    }
    write_json(RECEIPT, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "new_neighbors": 1072,
                "combined_native_neighbors": 9569,
                "screening_hits": len(hits),
                "reproduced_speedups": len(reproduced),
                "screen_wall_seconds": screen_elapsed,
                "holdout_wall_seconds": holdout["elapsed_wall_seconds"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
