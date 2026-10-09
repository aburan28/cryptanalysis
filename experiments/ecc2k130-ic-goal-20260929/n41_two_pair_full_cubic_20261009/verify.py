#!/usr/bin/env python3
"""Verify frozen N41 mixed-cubic rank, independent replay, and controls."""

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str):
    return json.loads((HERE / name).read_text())


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_local_hashes(protocol_name: str) -> None:
    protocol = load(protocol_name)
    for name, expected in protocol.get("input_sha256", {}).items():
        if protocol_name == "protocol.json":
            path = Path(protocol["inputs"][name])
        else:
            path = HERE / name
        ensure(digest(path) == expected, f"{protocol_name}: input {name} changed")
    sources = protocol.get("source_sha256", {})
    if isinstance(sources, str):
        name = {
            "evaluation_protocol.json": "evaluate.py",
            "public_probe_protocol.json": "public_residual_probe.py",
            "subgroup_protocol.json": "subgroup_coordinate_rank.py",
            "combined_protocol.json": "combined_coordinate_rank.py",
            "public_span_protocol.json": "public_coordinate_span.py",
        }[protocol_name]
        sources = {name: sources}
    for name, expected in sources.items():
        ensure(digest(HERE / name) == expected, f"{protocol_name}: source {name} changed")


def pair_keys(raw: bytes) -> set[tuple[int, int]]:
    ensure(len(raw) % 18 == 0, "binary pair row width changed")
    keys = set()
    for offset in range(0, len(raw), 18):
        i = int.from_bytes(raw[offset + 14:offset + 16], "little")
        j = int.from_bytes(raw[offset + 16:offset + 18], "little")
        ensure(0 <= i < 1956 and 0 <= j < 1956, "binary pair index outside domain")
        keys.add((i, j))
    ensure(len(keys) == len(raw) // 18, "duplicate pair-pair index record")
    return keys


def main() -> None:
    for name in ("protocol.json", "extract_protocol.json", "holdout_protocol.json",
                 "evaluation_protocol.json", "public_probe_protocol.json",
                 "subgroup_protocol.json", "combined_protocol.json",
                 "public_span_protocol.json"):
        check_local_hashes(name)
    protocol = load("protocol.json")
    production = load("production.json")
    rank = load("rank.json")
    rank_control = load("rank_control.json")
    audit = load("sage_audit.json")
    extraction = load("equations.json")
    extract_control = load("extract_control.json")
    holdout = load("holdout_production.json")
    validation = load("holdout_validation.json")
    public = load("public_residual_probe.json")
    subgroup = load("subgroup_coordinate_rank.json")
    combined = load("combined_coordinate_rank.json")
    public_span = load("public_coordinate_span.json")

    ensure(production["status"] == "EXACT_ROWS_WRITTEN", "training production failed")
    ensure(production["rows"] == 80000 and
           production["counts"]["source_accepted"] +
           production["counts"]["random_accepted"] == 80000,
           "training row counts differ")
    ensure(digest(HERE / "rows.bin") == production["rows_sha256"], "training rows changed")
    ensure(rank_control["status"] == "EXIT_SUCCESS" and rank_control["exit_code"] == 0,
           "rank process did not complete")
    ensure(rank_control["rank_result_sha256"] == digest(HERE / "rank.json") and
           rank_control["binary_sha256"] == digest(HERE / "rank") and
           rank_control["rows_sha256"] == production["rows_sha256"],
           "rank process input/result digest differs")
    ensure(rank["feature_count"] == 48818 and rank["rank"] == 47206 and
           rank["coordinate_feature_count"] == 3322 and rank["coordinate_rank"] == 3198,
           "mixed or coordinate rank differs")
    coordinate_nullity = rank["coordinate_feature_count"] - rank["coordinate_rank"]
    full_nullity = rank["feature_count"] - rank["rank"]
    ensure(coordinate_nullity == 124 and full_nullity == 13 * coordinate_nullity and
           rank["mixed_excess_nullity"] == 12 * coordinate_nullity,
           "seed-multiple nullspace dimension identity fails")
    ensure(audit["status"] == "PASS_INDEPENDENT_SAGE_GROUP_REPLAY" and
           audit["source_subgroup_points_checked"] == 128 and
           audit["exact_group_sums_replayed"] >= 256 and
           audit["rows_sha256"] == production["rows_sha256"] and
           audit["rank_sha256"] == digest(HERE / "rank.json") and
           audit["runtime_sha256"] == digest(HERE / "sage_runtime_info.json") and
           load("sage_runtime_info.json")["status"] == "verified",
           "independent checked-Sage audit differs")
    ensure(extract_control["status"] == "EXIT_SUCCESS" and
           extract_control["equations_sha256"] == digest(HERE / "equations.json"),
           "equation extraction did not complete")
    ensure(extraction["rank"] == rank["rank"] and
           extraction["nullity"] == full_nullity and
           extraction["mixed_candidates"] == 1488 and
           len(extraction["equations"]) == 8 and
           all(eq["support_size"] == 24 and eq["training_violations"] == 0
               for eq in extraction["equations"]),
           "RREF equation result differs")
    terms = [()]
    terms.extend((i,) for i in range(93))
    terms.extend(itertools.combinations(range(93), 2))
    terms.extend(term for term in itertools.combinations(range(93), 3) if term[0] < 12)
    ensure(len(terms) == 48818, "feature family changed")
    common = None
    for seed, equation in enumerate(extraction["equations"]):
        factor = []
        for feature in equation["support"]:
            term = terms[feature]
            ensure(seed in term, "selected equation is not seed-divisible")
            stripped = tuple(bit - 12 for bit in term if bit != seed)
            ensure(all(0 <= bit < 81 for bit in stripped), "seed factor has another seed bit")
            factor.append(stripped)
        factor = tuple(sorted(factor))
        if common is None:
            common = factor
        ensure(factor == common, "shortest equations have different coordinate factors")

    ensure(holdout["status"] == "EXACT_UNSEEN_ROWS_WRITTEN" and
           holdout["rows"] == 50000 and
           holdout["rows_sha256"] == digest(HERE / "holdout.bin"),
           "fresh held-out production differs")
    training_keys = pair_keys((HERE / "rows.bin").read_bytes())
    holdout_keys = pair_keys((HERE / "holdout.bin").read_bytes())
    ensure(len(training_keys) == 80000 and len(holdout_keys) == 50000 and
           not (training_keys & holdout_keys), "held-out pair indices overlap training")
    ensure(validation["checked_rows"] == 50000 and
           validation["all_selected_equations_hold"] and
           len(validation["results"]) == 8 and
           all(row["holdout_violations"] == 0 for row in validation["results"]) and
           validation["equations_sha256"] == digest(HERE / "equations.json") and
           validation["holdout_sha256"] == digest(HERE / "holdout.bin"),
           "held-out equation check differs")
    ensure(public["status"] == "PUBLIC_RESIDUALS_EVALUATED" and
           public["public_target_q"] == protocol["public_target_q"] and
           public["valid_prefix_residuals"] == 8192 and
           public["nonidentity_coordinate_factor_zero"] == 8192 and
           public["nonidentity_coordinate_factor_one"] == 0 and
           not public["identity_prefix_indices"] and
           tuple(tuple(t) for t in public["coordinate_factor_terms"]) == common,
           "public-target residual probe differs")
    ensure(subgroup["status"] == "POINT_CAP_REACHED" and
           subgroup["points_sampled"] == 6000 and
           subgroup["subgroup_coordinate_rank"] == 3198,
           "random subgroup coordinate rank differs")
    ensure(combined["status"] == "COMPLETE_COMBINED_RANK" and
           combined["pair_rows_processed"] == 80000 and
           combined["subgroup_rows_processed"] == 6000 and
           combined["pair_rank_low_pivot"] == 3198 and
           combined["combined_rank_low_pivot"] == 3198 and
           combined["novel_rank_from_subgroup"] == 0,
           "combined low-pivot rank differs")
    ensure(public_span["status"] == "COMPLETE_PUBLIC_SPAN" and
           public_span["public_target_q"] == protocol["public_target_q"] and
           public_span["pair_training_rows"] == 80000 and
           public_span["pair_coordinate_rank_low_pivot"] == 3198 and
           public_span["public_residuals_processed"] == 8192 and
           public_span["novel_rank_from_public_residuals"] == 0 and
           public_span["combined_coordinate_rank"] == 3198,
           "public residual coordinate span differs")
    print(json.dumps({"status": "PASS", "curve_id": protocol["curve_id"],
                      "proposal_id": protocol["proposal_id"],
                      "training_rows": 80000, "feature_rank": rank["rank"],
                      "feature_count": rank["feature_count"],
                      "coordinate_nullity": coordinate_nullity,
                      "full_nullity": full_nullity,
                      "fresh_holdout_rows": 50000,
                      "public_residuals": 8192,
                      "public_residual_novel_rank": public_span["novel_rank_from_public_residuals"],
                      "combined_coordinate_rank": combined["combined_rank_low_pivot"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
