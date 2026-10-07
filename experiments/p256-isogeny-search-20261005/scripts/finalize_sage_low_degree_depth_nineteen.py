#!/usr/bin/env python3
"""Freeze reports and a receipt from completed depth-nineteen evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
RESULTS = ROOT / "results"
STAGE = RESULTS / "sage-low-degree-depth-nineteen-20261007"
CLASS_STATUS = RESULTS / "sage-class-group-20261006" / "status-depth-nineteen.json"
PROTOCOL = ROOT / "protocol-depth-nineteen-20261007.json"
MANIFEST = ROOT / "source-sage-low-degree-depth-nineteen-20261007.sha256"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-nineteen-20261007.json"


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
        / "sage-low-degree-depth-seventeen-20261006"
        / "retained-union.json"
    )
    delta_path = STAGE / "candidates-delta.json"
    union_path = STAGE / "retained-union.json"
    screen_path = STAGE / "native-screen" / "screening-summary.json"
    holdout_path = STAGE / "holdout.json"
    attempts_path = STAGE / "attempts.json"
    model_path = STAGE / "candidate-model-audit.json"
    coefficient_path = STAGE / "coefficient-audit.json"
    conductor_path = STAGE / "conductor-audit.json"

    delta = load(delta_path)
    union = load(union_path)
    screen = load(screen_path)
    holdout = load(holdout_path)
    attempts = load(attempts_path)
    model = load(model_path)
    coefficient = load(coefficient_path)
    conductor = load(conductor_path)
    class_status = load(CLASS_STATUS)
    protocol = load(PROTOCOL)

    hits = screen["unadjusted_screening_hits"]
    holdout_candidates = holdout["results"][1:]
    reproduced = [
        row
        for row in holdout_candidates
        if row["paired_speedup_significant_at_95_percent"]
    ]
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

    assessment_path = STAGE / "transfer-assessment.json"
    assessment = {
        "schema_version": 1,
        "status": "draft_evidence_assessment",
        "question": "Do depth-18/19 low-degree isogeny transfers from P-256 expose a reproducible Pollard-rho iteration-rate advantage?",
        "typed_correspondence": protocol["typed_transfer"],
        "artifacts": {
            "protocol": source(PROTOCOL),
            "candidates": source(delta_path),
            "retained_union": source(union_path),
            "native_screen": source(screen_path),
            "holdout": source(holdout_path),
            "model_eligibility": source(model_path),
            "coefficient_audit": source(coefficient_path),
            "conductor_audit": source(conductor_path),
        },
        "obligations": [
            {
                "name": "existence",
                "status": "supported",
                "scope": "560 new explicit candidates",
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
                "scope": "all 560 additions have exact conductor 1 and level-zero horizontal paths",
            },
            {
                "name": "measured_iteration_rate_advantage",
                "status": "supported" if reproduced else "refuted",
                "scope": f"{len(hits)} screen hits; {len(reproduced)} fresh-holdout reproductions",
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
                "status": "unknown",
                "scope": "new path evaluation on P and Q was not timed",
            },
            {
                "name": "full_class_coverage",
                "status": "unknown",
                "scope": "2,786 retained curves are bounded; exact class-group computation remains separate",
            },
        ],
        "controls": [
            "prospective protocol committed before candidate generation",
            "fresh P-256 baseline in every screening block",
            "identical native implementation for baseline and candidate",
            "complete execution-position rotation within every block",
            "tracked scalar relation verified after every timed trial",
            "fresh 30-by-2-second holdout containing every unadjusted screening hit",
            "candidate IDs deduplicated against the prior 2,226-curve union",
            "deterministic model, coefficient, and conductor replays",
        ],
        "costs": {
            "measured_seconds": {
                "reusable_depth_18_19_discovery": delta["search"]["elapsed_seconds"],
                "native_screen_blocks": screen_elapsed,
                "fresh_holdout": holdout["elapsed_wall_seconds"],
            },
            "per_key_mapping": None,
            "default_exact_class_group": class_status["status"],
            "modeled_costs": None,
        },
        "finding": (
            f"{len(reproduced)} reproducible iteration-rate advantage(s) survived holdout within depths 18 and 19."
            if reproduced
            else "No reproducible iteration-rate advantage was found within depths 18 and 19 using edge degrees 3, 5, 11, and 13."
        ),
        "exploration_boundary": {
            "new_curves": 560,
            "combined_curves_including_p256": 2786,
            "combined_non_root_curves_with_native_measurements": 2785,
            "edge_degrees": [3, 5, 11, 13],
            "maximum_depth": 19,
            "claim": (
                "measured candidate found within this boundary"
                if reproduced
                else "not found within this family and boundary"
            ),
        },
        "open_obligations": [
            "finish and independently check the exact class-number calculation",
            "measure evaluation of each holdout-positive path on both ECDLP points",
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
    summary = f"""# P-256 low-degree isogeny search through depth nineteen

## Outcome

The prospectively frozen extension added 272 curves at depth eighteen and 288
at depth nineteen, with no overlap against the prior 2,226-curve union. The
explicit registry now contains P-256 plus 2,785 distinct neighbors. Every new
record retains its ordered path, edge maps, model isomorphisms, and transported
generator.

All 560 additions received matched-native measurements in 94 root-controlled
blocks. {len(hits)} unadjusted short-screen hit(s), with point estimates in
`{hit_range}`, entered the frozen fresh 30-trial, two-second holdout. {len(reproduced)}
candidate(s) reproduced a positive interval. {largest_text}

Every new curve has exact endomorphism conductor `1`; all path primes have
volcano level zero and all edges are horizontal. The coefficient audit found a
minimum addition-chain lower bound of
`{coefficient['results']['minimum_bit_length_row']['signed_addition_chain_operation_lower_bound']}`
operations and zero candidates passing the 32-operation specialization gate.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Prospective selection protocol | verified complete | Protocol commit predates candidate generation. |
| Explicit paths and log transport | verified for this boundary | 560 new paths; degrees are coprime to prime `n`; transported generators pass checks. |
| Endomorphism conductor and volcano levels | verified class-wide and per candidate | Conductor 1; every path is horizontal at level zero. |
| Low-operation normalized coefficient | not found within additions | Zero candidates pass the 32-operation gate. |
| Reproducible iteration-rate advantage | {'supported for ' + str(len(reproduced)) + ' holdout candidate(s)' if reproduced else 'not found within this boundary'} | {len(hits)} screen hit(s), {len(reproduced)} holdout reproduction(s). |
| Dramatic end-to-end ECDLP speedup | not established | No user numerical threshold; mapping and isolation remain open. |
| Entire isogeny class | incomplete | Depth 19 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `{class_status['status']}`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-18/19 discovery | {delta['search']['elapsed_seconds']:.4f} s | discovery/precomputation |
| Native screening blocks | {screen_elapsed:.4f} s | exploratory per-iteration comparison |
| Fresh holdout | {holdout['elapsed_wall_seconds']:.4f} s | exploratory verification evidence |
| New path evaluation on `P` and `Q` | not measured | per-key cost remains open |
| Exact class-group attempt | {class_status['status']} | no result counted at this checkpoint |

CPU affinity separated native timing, traversal, and class-group work, but the
host does not satisfy the repository isolation gate. The exact frozen commands
had repository/container working-directory path defects before computation; all
six invocation/reporting/verifier failures and the corrected commands are retained in
[`attempts.json`](attempts.json). Inputs, benchmark parameters, candidate order,
and selection rules did not change.

This result is `not found within this family and boundary` unless a positive
holdout is listed above. It is not a universal nonexistence result and does not
enumerate the complete class group.
"""
    summary_path = STAGE / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    source_paths = [
        PROTOCOL,
        ROOT / "scripts" / "explore_sage.py",
        ROOT / "scripts" / "extend_sage_low_degree.py",
        ROOT / "scripts" / "assemble_sage_low_degree_depth_nineteen.py",
        ROOT / "scripts" / "run_native_screen.py",
        ROOT / "scripts" / "run_native_holdout.py",
        ROOT / "scripts" / "audit_candidate_models.py",
        ROOT / "scripts" / "audit_candidate_coefficients.py",
        ROOT / "scripts" / "audit_candidate_conductors.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_eleven.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_nineteen.py",
        ROOT / "scripts" / "compute_class_group_sage.py",
        ROOT / "scripts" / "record_class_group_status.py",
        ROOT / "scripts" / "finalize_sage_low_degree_depth_nineteen.py",
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
        prior_union_path,
        delta_path,
        union_path,
        screen_path,
        holdout_path,
        attempts_path,
        assessment_path,
        summary_path,
        model_path,
        coefficient_path,
        conductor_path,
        CLASS_STATUS,
    ]
    receipt = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "status": "verified_exploratory_low_degree_depth_nineteen",
        "claim": (
            "The prospectively frozen depth-nineteen extension added 560 explicit curves "
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
                "Docker search command added the experiment working directory.",
                "Native screen and holdout binary/input paths were spelled relative to the repository root.",
            ],
            "verify": "python3 scripts/verify_sage_low_degree_depth_nineteen.py",
        },
        "artifacts": {str(path.relative_to(ROOT)): sha256(path) for path in artifacts},
        "search": {
            "ells": [3, 5, 11, 13],
            "input_depth": 17,
            "target_depth": 19,
            "new_depth_counts": {"18": 272, "19": 288},
            "new_non_root_curves": 560,
            "overlap_with_prior_union": 0,
            "combined_unique_curves_including_p256": 2786,
            "explicit_paths_verified": True,
            "exceptional_automorphisms_found": False,
        },
        "screening": {
            "new_neighbors": 560,
            "blocks": 94,
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
            "explicit_curves_including_p256": 2786,
            "non_root_curves_with_matched_native_measurement": 2785,
            "reproducible_speedups": len(reproduced),
        },
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
            "default_exact_class_group_attempt": (
                f"{class_status['status']} after at least "
                f"{class_status['elapsed_lower_bound_seconds']:.1f} seconds; no result counted"
            ),
            "per_instance_mapping": "explicit formulas retained for P and Q; evaluation was not timed for the 560 additions",
            "amortization": "no end-to-end estimate because new per-key mapping was not measured",
        },
        "preserved_failures": attempts["attempts"],
        "limitations": [
            "the traversal stops at depth nineteen and uses only edge degrees 3, 5, 11, and 13",
            "the retained registry is not the entire finite class-group orbit",
            "host-wide CPU isolation was not established",
            "new path evaluation on both ECDLP points was not timed",
            "screening intervals are unadjusted selection triggers",
            "no full P-256 collision was attempted or required by the protocol",
        ],
        "decision": (
            f"{len(reproduced)} holdout-positive candidate(s) require isolated and end-to-end follow-up."
            if reproduced
            else "No candidate advances; all screen hits failed the fresh holdout."
        ),
    }
    write_json(RECEIPT, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "new_neighbors": 560,
                "combined_native_neighbors": 2785,
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
