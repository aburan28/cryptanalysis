#!/usr/bin/env python3
"""Freeze reports and a receipt from the completed depth-seventeen raw evidence."""

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
STAGE = RESULTS / "sage-low-degree-depth-seventeen-20261006"
CLASS_STATUS = RESULTS / "sage-class-group-20261006" / "status-depth-seventeen.json"
MODEL_DIR = RESULTS / "model-eligibility-20261006"
MANIFEST = ROOT / "source-sage-low-degree-depth-seventeen-20261006.sha256"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-seventeen-20261006.json"


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-parent-remote-commit", required=True)
    args = parser.parse_args()

    delta_path = STAGE / "candidates-delta.json"
    union_path = STAGE / "retained-union.json"
    screen_path = STAGE / "native-screen" / "screening-summary.json"
    holdout_path = STAGE / "holdout.json"
    attempts_path = STAGE / "attempts.json"
    model_path = MODEL_DIR / "model-eligibility.json"
    model_summary_path = MODEL_DIR / "summary.md"
    candidate_model_path = STAGE / "candidate-model-audit.json"

    delta = load(delta_path)
    union = load(union_path)
    screen = load(screen_path)
    holdout = load(holdout_path)
    class_status = load(CLASS_STATUS)
    model = load(model_path)
    candidate_model = load(candidate_model_path)
    attempts = load(attempts_path)

    hits = screen["unadjusted_screening_hits"]
    holdout_candidates = holdout["results"][1:]
    reproduced = [row for row in holdout_candidates if row["paired_speedup_significant_at_95_percent"]]
    all_screen_relations = all(row["linear_relation_verified_every_trial"] for row in screen["results"])
    all_holdout_relations = all(row["linear_relation_verified_every_trial"] for row in holdout["results"])
    screen_elapsed = sum(
        load(ROOT / block["artifact"])["elapsed_wall_seconds"] for block in screen["blocks"]
    )
    largest = max(holdout_candidates, key=lambda row: row["paired_relative_iteration_speed"], default=None)
    hit_speeds = [row["paired_relative_iteration_speed"] for row in hits]

    assessment_path = STAGE / "transfer-assessment.json"
    assessment = {
        "schema_version": 1,
        "status": "draft_evidence_assessment",
        "question": "Do depth-16/17 low-degree isogeny transfers from P-256 expose a reproducible Pollard-rho iteration-rate advantage?",
        "typed_correspondence": {
            "source": "E_0(F_p)[n] for NIST P-256",
            "destination": "E_i(F_p)[n] in short-Weierstrass form",
            "edges": "explicit F_p-rational separable isogenies",
            "edge_degrees": [3, 5, 11, 13],
            "path_depths_added": [16, 17],
            "kernel_intersection": "trivial because n is prime and differs from every edge degree",
            "log_transport": "Q = kP implies phi(Q) = k phi(P)",
            "recovery": "the destination logarithm is the same scalar modulo n",
        },
        "artifacts": {
            "candidates": source(delta_path),
            "retained_union": source(union_path),
            "native_screen": source(screen_path),
            "holdout": source(holdout_path),
            "model_eligibility": source(model_path),
            "candidate_model_audit": source(candidate_model_path),
        },
        "obligations": [
            {"name": "existence", "status": "supported", "scope": "496 new explicit candidates"},
            {"name": "executable_construction", "status": "supported", "scope": "all edge kernels, maps, isomorphisms, and transported generators retained"},
            {"name": "map_correctness", "status": "supported", "scope": "Sage checks plus path continuity and degree-product verification"},
            {"name": "subgroup_preservation", "status": "supported", "scope": "same prime order, trivial kernel intersection, generator transport, and scalar-relation checks"},
            {
                "name": "measured_iteration_rate_advantage",
                "status": "supported" if reproduced else "refuted",
                "scope": f"{len(hits)} screen hits; {len(reproduced)} fresh-holdout reproductions",
            },
            {"name": "dramatic_speedup", "status": "unknown", "scope": "the requested adjective has no supplied numerical acceptance threshold"},
            {"name": "host_isolated_speedup", "status": "unknown", "scope": "CPU affinity is not an isolation-service receipt"},
            {"name": "per_key_transfer_cost", "status": "unknown", "scope": "new path evaluation on both ECDLP points was not timed"},
            {"name": "end_to_end_attack_advantage", "status": "unknown", "scope": "no full P-256 collision and no charged new transfer timing"},
            {"name": "full_class_coverage", "status": "unknown", "scope": "2,226 curves are bounded; exact class-number computation remains separate"},
            {"name": "exceptional_automorphism", "status": "refuted", "scope": "exact class-wide CM exclusion and automorphism-order-two records"},
            {"name": "low_norm_non_scalar_endomorphism", "status": "refuted", "scope": "exact fundamental-discriminant norm bound"},
            {"name": "montgomery_or_edwards_model", "status": "refuted", "scope": "class-wide odd prime order excludes rational two-torsion"},
            {"name": "neighbor_only_small_a_shortcut", "status": "refuted", "scope": "P-256 itself has a certified F_p-isomorphic a=1 model"},
        ],
        "controls": [
            "fresh P-256 baseline in every screening block",
            "identical unchanged native implementation for baseline and candidate",
            "complete execution-position rotation within every block",
            "tracked scalar relation verified after every timed trial",
            "fresh 30-by-2-second holdout containing every unadjusted screening hit",
            "candidate IDs deduplicated against the prior 1,730-curve union",
            "deterministic class-wide model-eligibility replay",
        ],
        "costs": {
            "measured_seconds": {
                "reusable_depth_16_17_discovery": delta["search"]["elapsed_seconds"],
                "native_screen_blocks": screen_elapsed,
                "fresh_holdout": holdout["elapsed_wall_seconds"],
            },
            "per_key_mapping": None,
            "default_exact_class_group": class_status["status"],
            "modeled_costs": None,
        },
        "finding": (
            f"{len(reproduced)} reproducible iteration-rate advantage(s) survived holdout within "
            "depths 16 and 17."
            if reproduced
            else "No reproducible iteration-rate advantage was found within depths 16 and 17 using edge degrees 3, 5, 11, and 13."
        ),
        "exploration_boundary": {
            "new_curves": 496,
            "combined_curves_including_p256": 2226,
            "combined_non_root_curves_with_native_measurements": 2225,
            "edge_degrees": [3, 5, 11, 13],
            "maximum_depth": 17,
            "claim": "measured candidate found within this boundary" if reproduced else "not found within this family and boundary",
        },
        "open_obligations": [
            "finish and independently check the exact class-number calculation",
            "measure evaluation of each retained path on both ECDLP points before an end-to-end claim",
            "rerun any holdout-positive timing candidate under the repository host-isolation service",
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
    summary = f"""# P-256 low-degree isogeny search through depth seventeen

## Outcome

The resumed search added 240 curves at depth sixteen and 256 at depth seventeen,
with no overlap against the prior 1,730-curve union. The explicit registry now
contains P-256 plus 2,225 distinct neighbors. Every new record retains its ordered
path, edge maps, short-model isomorphisms, and transported generator.

All 496 additions received matched-native measurements in 83 root-controlled
blocks. {len(hits)} unadjusted short-screen hit(s), with point estimates in
`{hit_range}`, entered a fresh 30-trial, two-second holdout. {len(reproduced)}
candidate(s) reproduced a positive interval. {largest_text}

The deterministic [model-eligibility audit](../model-eligibility-20261006/summary.md)
also shows that Montgomery/Edwards shortcuts are unavailable class-wide and
small-`a` normalization is available to P-256 itself. The unchanged native
backend uses the same candidate-independent operation schedule for every curve.
An explicit replay over all 497 delta records verified 245 maps to `a=1` and
252 maps to `a=3`, including every transported generator.

## Requirement status

| Requirement | Status | Evidence |
| --- | --- | --- |
| Frobenius order classification | verified complete | `D_pi` is fundamental, so every curve has the same maximal endomorphism order. |
| Explicit paths and log transport | verified for this boundary | 496 new paths; degrees are coprime to prime `n`; transported generators pass order checks. |
| Exceptional automorphisms or low-norm endomorphisms | refuted class-wide | Exact CM discriminant and norm bound. |
| Unusually cheap standard curve models | refuted class-wide | Odd prime order excludes Montgomery/Edwards; P-256 itself normalizes to `a=1`. |
| Reproducible iteration-rate advantage | {'supported for ' + str(len(reproduced)) + ' holdout candidate(s)' if reproduced else 'not found within this boundary'} | {len(hits)} screen hit(s), {len(reproduced)} fresh-holdout reproduction(s). |
| Dramatic end-to-end ECDLP speedup | not established | No numerical threshold supplied; mapping and full-collision costs remain open. |
| Entire isogeny class | incomplete | Depth 17 over degrees 3, 5, 11, and 13 is bounded; exact class-number work is `{class_status['status']}`. |

## Cost accounting

| Cost | Measured wall time | Accounting role |
| --- | ---: | --- |
| Reusable depth-16/17 discovery | {delta['search']['elapsed_seconds']:.4f} s | discovery/precomputation |
| Native screening blocks | {screen_elapsed:.4f} s | exploratory per-iteration comparison |
| Fresh holdout | {holdout['elapsed_wall_seconds']:.4f} s | exploratory verification evidence |
| New path evaluation on `P` and `Q` | not measured | per-key cost remains open |
| Exact class-group attempt | running separately | no result counted at this checkpoint |

CPU affinity separated the native benchmark, traversal, and class-group process,
but the host does not satisfy the repository isolation gate. These timing results
remain exploratory. Screening intervals are unadjusted selection triggers; only
the fresh holdout is used for reproduction.

## Failures and limits

The first depth-17 launch failed before Sage import because a second container
under Docker's `vfs` driver exhausted the writable layer. Its exact command and
traceback summary are retained in [`attempts.json`](attempts.json); the successful
rerun reused the existing Sage container with separate CPU affinity.

This result is `not found within this family and boundary` unless a positive
holdout is listed above. It is not a universal nonexistence result and does not
complete a P-256 collision experiment.
"""
    summary_path = STAGE / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    source_paths = [
        ROOT / "scripts" / "explore_sage.py",
        ROOT / "scripts" / "extend_sage_low_degree.py",
        ROOT / "scripts" / "assemble_sage_low_degree_depth_seventeen.py",
        ROOT / "scripts" / "run_native_screen.py",
        ROOT / "scripts" / "run_native_holdout.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_eleven.py",
        ROOT / "scripts" / "verify_sage_low_degree_depth_seventeen.py",
        ROOT / "scripts" / "compute_class_group_sage.py",
        ROOT / "scripts" / "record_class_group_status.py",
        ROOT / "scripts" / "analyze_model_eligibility.py",
        ROOT / "scripts" / "verify_model_eligibility.py",
        ROOT / "scripts" / "audit_candidate_models.py",
        ROOT / "scripts" / "finalize_sage_low_degree_depth_seventeen.py",
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
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True, capture_output=True, text=True
    ).stdout.strip()
    native_binary = REPOSITORY / "suite" / "target" / "release" / "examples" / "p256_isogeny_native_bench"
    artifacts = [
        RESULTS / "sage-low-degree-depth-fifteen-20261006" / "retained-union.json",
        delta_path,
        screen_path,
        holdout_path,
        union_path,
        attempts_path,
        assessment_path,
        summary_path,
        model_path,
        model_summary_path,
        candidate_model_path,
        CLASS_STATUS,
    ]
    receipt = {
        "schema_version": 1,
        "protocol_id": "p256-isogeny-search-exploratory-v1",
        "status": "verified_exploratory_low_degree_depth_seventeen",
        "claim": (
            f"Resuming the low-degree frontier through depth seventeen added 496 explicit curves with no overlap against the prior 1,730-curve union. "
            f"All additions received a CPU-separated matched-native screen; {len(reproduced)} of {len(hits)} exploratory hits reproduced in a fresh holdout."
        ),
        "run_completed_at": iso_utc_now(),
        "source": {
            "pr_parent_remote_commit": args.pr_parent_remote_commit,
            "local_parent_commit": local_parent,
            "manifest": MANIFEST.name,
            "manifest_sha256": sha256(MANIFEST),
        },
        "runtime": {
            "sage_image": "sagemath/sagemath:10.6",
            "sage_image_digest": "sha256:19995db6194f4a4bab18ce9a88556fd15b9ed5e916b4504fefe618a7796ddbdb",
            "native_release_binary_sha256": sha256(native_binary),
            "cpu_affinity": {
                "native_screen_and_holdout": "CPU 0 via taskset -c 0; inherited by child benchmark processes",
                "concurrent_default_class_group_process": "CPU 4 via taskset inside the Sage container",
                "sage_frontier_extension": "CPU 2 via Docker exec and taskset",
                "frequency_stability": "not independently verified",
            },
            "host_isolation": "unverified; all wall-time comparisons remain exploratory under repository policy",
        },
        "commands": {
            "search": "docker exec p256-classgroup-default taskset -c 2 sage -python scripts/extend_sage_low_degree.py --input results/sage-low-degree-depth-fifteen-20261006/candidates-delta.json --ells 3,5,11,13 --target-depth 17 --max-new-nodes 2000 --output results/sage-low-degree-depth-seventeen-20261006/candidates-delta.json",
            "assemble": "python3 scripts/assemble_sage_low_degree_depth_seventeen.py",
            "native_screen": "taskset -c 0 python3 scripts/run_native_screen.py --binary NATIVE_BINARY --candidates results/sage-low-degree-depth-seventeen-20261006/candidates-delta.json --block-size 6 --seconds 0.5 --rotations 1 --warmup-seconds 0.05 --output-dir results/sage-low-degree-depth-seventeen-20261006/native-screen",
            "holdout": "taskset -c 0 python3 scripts/run_native_holdout.py --binary NATIVE_BINARY --candidates DELTA --screening SCREENING_SUMMARY --seconds 2 --trials 30 --warmup-seconds 0.2 --output results/sage-low-degree-depth-seventeen-20261006/holdout.json",
            "verify": "python3 scripts/verify_sage_low_degree_depth_seventeen.py",
        },
        "artifacts": {str(path.relative_to(ROOT)): sha256(path) for path in artifacts},
        "search": {
            "ells": [3, 5, 11, 13],
            "input_depth": 15,
            "target_depth": 17,
            "new_depth_counts": {"16": 240, "17": 256},
            "new_non_root_curves": 496,
            "overlap_with_prior_union": 0,
            "combined_unique_curves_including_p256": 2226,
            "explicit_paths_verified": True,
            "exceptional_automorphisms_found": False,
        },
        "screening": {
            "new_neighbors": 496,
            "blocks": 83,
            "seconds_per_trial": 0.5,
            "complete_position_rotations_per_block": 1,
            "candidate_trials": sum(block["trials_per_candidate"] * len(block["candidate_ids"]) for block in screen["blocks"]),
            "all_linear_relations_verified": all_screen_relations,
            "unadjusted_screening_hits": len(hits),
            "screening_point_estimate_range": [min(hit_speeds), max(hit_speeds)] if hit_speeds else None,
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
                    "paired_relative_iteration_speed": largest["paired_relative_iteration_speed"],
                    "paired_relative_iteration_speed_95_percent_ci": largest["paired_relative_iteration_speed_95_percent_ci"],
                }
                if largest is not None
                else None
            ),
        },
        "combined_native_coverage": {
            "explicit_curves_including_p256": 2226,
            "non_root_curves_with_matched_native_measurement": 2225,
            "reproducible_speedups": len(reproduced),
        },
        "model_eligibility": {
            "artifact": str(model_path.relative_to(ROOT)),
            "dramatic_speedup_found": model["assessment"]["dramatic_speedup_found"],
            "montgomery_edwards_shortcut": "refuted class-wide over F_p",
            "small_a_neighbor_only_advantage": "refuted; P-256 maps to a=1",
            "candidate_target_a_counts": candidate_model["target_a_counts"],
            "all_candidate_normalizations_verified": (
                candidate_model["all_fourth_root_certificates_verified"]
                and candidate_model["all_transported_generators_on_target"]
            ),
        },
        "cost_accounting": {
            "discovery_and_reusable_precomputation_seconds": delta["search"]["elapsed_seconds"],
            "native_screen_block_wall_seconds_total": screen_elapsed,
            "holdout_wall_seconds": holdout["elapsed_wall_seconds"],
            "default_exact_class_group_attempt": f"{class_status['status']} after at least {class_status['elapsed_lower_bound_seconds']:.1f} seconds; no result counted",
            "per_instance_mapping": "explicit formulas retained for P and Q; evaluation was not timed for the 496 additions",
            "amortization": "no end-to-end estimate because per-key mapping for the added paths was not measured",
        },
        "failures": attempts["attempts"],
        "limitations": [
            "the traversal stops at depth seventeen and uses only edge degrees 3, 5, 11, and 13",
            "the 2,226-curve explicit registry is not the entire P-256 isogeny class",
            "CPU affinity was separated but the repository host-isolation gate and frequency stability were not independently verified",
            "the screens measure generic rho iteration cost rather than completing a full P-256 collision",
            "per-key mapping cost was not measured for the 496 additions",
            "the exact class-number computation had not completed when this bounded result was frozen",
            "the word dramatic has no user-supplied numerical acceptance threshold",
        ],
        "decision": (
            f"{len(reproduced)} holdout-positive candidate(s) require isolated and end-to-end follow-up."
            if reproduced
            else f"No candidate advances. All {len(hits)} unadjusted screening hit(s) failed the fresh holdout; all 2,225 retained non-root curves have matched native measurements and zero reproducible iteration-rate improvements."
        ),
    }
    write_json(RECEIPT, receipt)
    print(json.dumps({
        "receipt": str(RECEIPT.relative_to(ROOT)),
        "screening_hits": len(hits),
        "reproduced_speedups": len(reproduced),
        "screen_wall_seconds": screen_elapsed,
        "holdout_wall_seconds": holdout["elapsed_wall_seconds"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
