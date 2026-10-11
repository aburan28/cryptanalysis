#!/usr/bin/env python3
"""Freeze reports and a receipt from completed depth-forty-three evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from freeze_large_json_sharded import shard_paths, verify_shards

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
RESULTS = ROOT / "results"
STAGE = RESULTS / "sage-low-degree-depth-forty-three-20261009"
CLASS_STATUS = RESULTS / "sage-class-group-20261006" / "status-depth-forty-three.json"
CLASS_INTERRUPTION = (
    RESULTS
    / "sage-class-group-20261006"
    / "status-infrastructure-interruption-20261009.json"
)
STORAGE_QUALIFICATION = (
    RESULTS / "sharded-storage-qualification-20261008" / "qualification.json"
)
PROTOCOL = ROOT / "protocol-depth-forty-three-20261009.json"
MANIFEST = ROOT / "source-sage-low-degree-depth-forty-three-20261009.sha256"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-forty-three-20261009.json"


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
        / "sage-low-degree-depth-forty-one-20261008"
        / "retained-union.json"
    )
    prior_receipt_path = ROOT / "receipt-sage-low-degree-depth-forty-one-20261008.json"
    prior_positive_receipt_path = (
        ROOT / "receipt-sage-low-degree-depth-twenty-five-20261007.json"
    )
    delta_path = STAGE / "candidates-delta.json"
    delta_archive_prefix = STAGE / "candidates-delta.json.gz"
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
    excluded_screen_dir = STAGE / "native-screen-excluded-resource-mismatch"

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
    registry_verification = verify_shards(delta_archive_prefix, freeze_manifest)
    delta_archive_shards = shard_paths(delta_archive_prefix, freeze_manifest)
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
    assert len(prior_receipt["prior_positive_followups"]) == 4
    assert all(
        row["status"] == "open; local isolation probe failed"
        for row in prior_receipt["prior_positive_followups"]
    )
    assert prior_receipt["holdout"]["reproduced_speedups"] == 0
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
    excluded_screen_blocks = sorted(excluded_screen_dir.glob("block-*.json"))
    excluded_screen_elapsed = sum(
        load(path)["elapsed_wall_seconds"] for path in excluded_screen_blocks
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
            "No new depth-42/43 candidate survived holdout, so no additional P,Q path "
            "evaluation was triggered. The depth-25, depth-34, depth-36, and depth-37 exploratory positives "
            "remain open for isolated replay, with their previously charged per-key transfers."
        )
        mapping_cost_row = (
            "| New positive path evaluation on `P` and `Q` | not triggered | "
            "no new holdout-positive candidate |"
        )

    assessment_path = STAGE / "transfer-assessment.json"
    assessment = {
        "schema_version": 1,
        "status": "completed_evidence_assessment",
        "question": "Do depth-42/43 low-degree isogeny transfers from P-256 expose a reproducible Pollard-rho iteration-rate advantage?",
        "typed_correspondence": protocol["typed_transfer"],
        "artifacts": {
            "protocol": source(PROTOCOL),
            "candidate_registry_archive_shards": [
                source(path) for path in delta_archive_shards
            ],
            "candidate_registry_freeze_manifest": source(delta_freeze_path),
            "sharded_storage_qualification": source(STORAGE_QUALIFICATION),
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
            "prior_depth_forty_one_receipt": source(prior_receipt_path),
            "prior_depth_twenty_five_positive_receipt": source(
                prior_positive_receipt_path
            ),
        },
        "obligations": [
            {
                "name": "existence",
                "status": "supported",
                "scope": "1,328 new explicit candidates",
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
                "scope": "all 1,328 additions have exact conductor 1 and level-zero horizontal paths",
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
                "scope": "14,498 retained curves are bounded; exact class-group computation remains separate",
            },
        ],
        "controls": [
            "prospective protocol committed before candidate generation",
            "fresh P-256 baseline in every screening block",
            "identical native implementation for baseline and candidate",
            "complete execution-position rotation within every block",
            "tracked scalar relation verified after every timed trial",
            "fresh 30-by-2-second holdout containing every unadjusted screening hit",
            "candidate IDs deduplicated against the prior 13,170-curve union",
            "deterministic sharded registry archive reproduced and verified against the uncompressed hash",
            "deterministic model, coefficient, and conductor replays",
        ],
        "costs": {
            "measured_seconds": {
                "reusable_depth_42_43_discovery": delta["search"]["elapsed_seconds"],
                "native_screen_blocks": screen_elapsed,
                "excluded_resource_mismatch_native_screen_blocks": excluded_screen_elapsed,
                "fresh_holdout": holdout["elapsed_wall_seconds"],
                "interrupted_exact_class_group": class_interruption[
                    "cumulative_interrupted_lower_bound_seconds"
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
            f"{len(reproduced)} exploratory iteration-rate advantage(s) survived holdout within depths 42 and 43; controlled isolation remains open."
            if reproduced
            else "No reproducible iteration-rate advantage was found within depths 42 and 43 using edge degrees 3, 5, 11, and 13. The separate depth-25, depth-34, depth-36, and depth-37 exploratory positives remain open for isolated replay."
        ),
        "exploration_boundary": {
            "new_curves": 1328,
            "combined_curves_including_p256": 14498,
            "combined_non_root_curves_with_native_measurements": 14497,
            "edge_degrees": [3, 5, 11, 13],
            "maximum_depth": 43,
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
    reproduced_text = "No candidate survived the fresh holdout."
    if reproduced:
        rows = [
            "| Candidate | Holdout ratio | Paired 95% interval |",
            "| --- | ---: | ---: |",
        ]
        for row in reproduced:
            ci = row["paired_relative_iteration_speed_95_percent_ci"]
            rows.append(
                f"| `{row['candidate_id']}` | "
                f"{row['paired_relative_iteration_speed']:.6f}x | "
                f"{ci[0]:.6f}x-{ci[1]:.6f}x |"
            )
        reproduced_text = "\n".join(rows)
    hit_range = "none"
    if hit_speeds:
        hit_range = f"{min(hit_speeds):.4f}x-{max(hit_speeds):.4f}x"
    summary = f"""# P-256 low-degree isogeny search through depth forty-three

## Outcome

The prospectively frozen extension added 656 curves at depth forty-two and 672
at depth forty-three, with no overlap against the prior 13,170-curve union. The
explicit registry now contains P-256 plus 14,497 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator. The oversized working registry is published as three ordered shards
of one deterministic gzip stream whose manifest binds every shard plus the
concatenated compressed and uncompressed hashes and sizes.

All 1,328 additions received matched-native measurements in 222 root-controlled
blocks. {len(hits)} unadjusted short-screen hit(s), with point estimates in
`{hit_range}`, entered the frozen fresh 30-trial, two-second holdout. {len(reproduced)}
candidate(s) reproduced a positive interval. {largest_text}

A container-only launch used CPU 2 after the managed-environment transition made
CPU 0 unavailable inside that container. It was stopped after
{len(excluded_screen_blocks)} complete blocks and {excluded_screen_elapsed:.4f}
seconds because the frozen protocol requires host CPU 0. Those relation-verified
artifacts are preserved but excluded from selection and all accepted aggregates.

{reproduced_text}

{mapping_text}
The local isolation probe failed the repository gate, so every positive rho
timing remains exploratory and requires replay on a qualifying host.

Every new curve records Frobenius-order conductor `1` and exact endomorphism-ring
conductor `1`; all path primes have volcano level zero and all edges are
horizontal. Across all 14,498 retained
curves, 423,858 recorded path-edge occurrences are therefore horizontal at
level zero. The coefficient audit found a
minimum addition-chain lower bound of
`{coefficient['results']['minimum_bit_length_row']['signed_addition_chain_operation_lower_bound']}`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 1,328 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Oversized registry preservation | verified complete | Three deterministic shards, concatenated archive hash, uncompressed hash, and byte-identical repack verified. |
| Frobenius/endomorphism conductors and volcano levels | verified class-wide and per candidate | Both conductors are 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Iteration-rate advantage | {'exploratory holdout-positive for ' + str(len(reproduced)) + ' candidate(s); controlled status unknown' if reproduced else 'not found within this boundary'} | {len(hits)} screen hit(s), {len(reproduced)} holdout reproduction(s); local isolation gate failed. |
| Per-key transfer cost | satisfied for every new holdout-positive candidate | Complete retained path evaluated on both `P` and `Q` when triggered; log relation verified. |
| Dramatic end-to-end ECDLP speedup | not established | Per-key mapping is charged, but controlled host isolation remains open. |
| Entire isogeny class | incomplete | Depth 43 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `{class_status['status']}` after an infrastructure restart. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-42/43 discovery | {delta['search']['elapsed_seconds']:.4f} s | discovery/precomputation |
| Excluded wrong-resource native screen | {excluded_screen_elapsed:.4f} s | protocol-resource mismatch; no trials enter selection |
| Native screening blocks | {screen_elapsed:.4f} s | exploratory per-iteration comparison |
| Fresh holdout | {holdout['elapsed_wall_seconds']:.4f} s | exploratory verification evidence |
{mapping_cost_row}
| Exact class-group attempt | {class_status['status']} | no result counted at this checkpoint |
| Interrupted exact class-group work | {class_interruption['cumulative_interrupted_lower_bound_seconds']:.4f} s | infrastructure loss; no result counted |

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
        ROOT / "scripts" / "assemble_sage_low_degree_depth_forty_three.py",
        ROOT / "scripts" / "freeze_large_json_sharded.py",
        ROOT / "scripts" / "run_native_screen.py",
        ROOT / "scripts" / "run_native_holdout.py",
        ROOT / "scripts" / "benchmark_mapping_sage.py",
        ROOT / "scripts" / "audit_candidate_models.py",
        ROOT / "scripts" / "audit_candidate_coefficients.py",
        ROOT / "scripts" / "audit_candidate_coefficients_depth_forty_three.py",
        ROOT / "scripts" / "audit_candidate_conductors.py",
        ROOT / "scripts" / "audit_candidate_conductors_depth_forty_three.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_eleven.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_forty_three.py",
        ROOT / "scripts" / "compute_class_group_sage.py",
        ROOT / "scripts" / "record_class_group_status.py",
        ROOT / "scripts" / "finalize_sage_low_degree_depth_forty_three.py",
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
        STORAGE_QUALIFICATION,
        prior_receipt_path,
        prior_positive_receipt_path,
        prior_union_path,
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
    artifacts.extend(delta_archive_shards)
    if mapping_rows:
        artifacts.append(mapping_path)
    artifacts.extend(excluded_screen_blocks)
    receipt = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "status": "verified_exploratory_low_degree_depth_forty_three",
        "claim": (
            "The prospectively frozen depth-forty-three extension added 1,328 explicit curves "
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
                "native_screen_and_holdout": "host CPU 0",
                "sage_frontier_extension": "CPU 2",
                "concurrent_default_class_group_process": "CPU 4",
            },
            "host_isolation": protocol["resources"]["host_isolation"],
        },
        "commands": {
            "frozen_commands": protocol["commands"],
            "corrections": [
                "The frozen generic coefficient- and conductor-audit commands produced correct rows but their reusable scripts hard-coded depth-nineteen report labels. Depth-forty-three wrappers replayed the same build_report results and corrected only those metadata labels. All invocations are preserved in attempts.json.",
                "After the environment transition, the persistent Sage container allowed CPUs 2 and 4 but not frozen native CPU 0. Five CPU-2 blocks were preserved and excluded; the accepted screen and holdout use the prospectively frozen host CPU 0."
            ],
            "verify": "python3 scripts/verify_sage_low_degree_depth_forty_three.py",
        },
        "artifacts": {str(path.relative_to(ROOT)): sha256(path) for path in artifacts},
        "registry_storage": {
            "working_path": str(delta_path.relative_to(ROOT)),
            "archive_prefix": str(delta_archive_prefix.relative_to(ROOT)),
            "archive_shards": [
                str(path.relative_to(ROOT)) for path in delta_archive_shards
            ],
            "manifest_path": str(delta_freeze_path.relative_to(ROOT)),
            "verification": registry_verification,
            "deterministic_repack_verified": True,
        },
        "search": {
            "ells": [3, 5, 11, 13],
            "input_depth": 41,
            "target_depth": 43,
            "new_depth_counts": {"42": 656, "43": 672},
            "new_non_root_curves": 1328,
            "overlap_with_prior_union": 0,
            "combined_unique_curves_including_p256": 14498,
            "explicit_paths_verified": True,
            "exceptional_automorphisms_found": False,
        },
        "screening": {
            "new_neighbors": 1328,
            "blocks": 222,
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
            "explicit_curves_including_p256": 14498,
            "non_root_curves_with_matched_native_measurement": 14497,
            "endomorphism_conductor_one": 14498,
            "retained_path_edge_occurrences": 423858,
            "current_extension_reproduced_speedups": len(reproduced),
            "known_exploratory_holdout_positive_candidates": 4 + len(reproduced),
        },
        "prior_positive_followups": protocol["prior_positive_followups"],
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
            "excluded_resource_mismatch_native_screen_wall_seconds": excluded_screen_elapsed,
            "holdout_wall_seconds": holdout["elapsed_wall_seconds"],
            "interrupted_exact_class_group_wall_seconds_lower_bound": (
                class_interruption["cumulative_interrupted_lower_bound_seconds"]
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
            "the traversal stops at depth forty-three and uses only edge degrees 3, 5, 11, and 13",
            "the retained registry is not the entire finite class-group orbit",
            "host-wide CPU isolation was not established",
            "the local isolation probe failed the repository host gate, so the positive timing remains exploratory",
            "screening intervals are unadjusted selection triggers",
            "no full P-256 collision was attempted or required by the protocol",
        ],
        "decision": (
            f"{len(reproduced)} holdout-positive candidate(s) require isolated and end-to-end follow-up."
            if reproduced
            else "No new candidate advances; all depth-42/43 screen hits failed the fresh holdout, while the separate depth-25, depth-34, depth-36, and depth-37 exploratory positives remain open for isolated replay."
        ),
    }
    write_json(RECEIPT, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "new_neighbors": 1328,
                "combined_native_neighbors": 14497,
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
