#!/usr/bin/env python3
"""Independently rebuild the feature order and rank from pivotal rows."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def monomials() -> list[tuple[int, ...]]:
    items = [()] + [(i,) for i in range(52)]
    items += list(itertools.combinations(range(52), 2))
    items += [(a, 6 + b, 12 + t)
              for a in range(6) for b in range(6) for t in range(40)]
    assert len(items) == len(set(items)) == 2819
    return items


def row_values(row: dict) -> set[int]:
    sums = row["pair_seed_sums"]
    x = row["target"][0]
    assert x & 1 == 0
    return ({i for i in range(6) if (sums[0] >> i) & 1}
            | {6 + i for i in range(6) if (sums[1] >> i) & 1}
            | {12 + i for i in range(40) if (x >> (i + 1)) & 1})


def feature_vector_reverse(row: dict, terms: list[tuple[int, ...]]) -> int:
    active = row_values(row)
    result = 0
    for index, term in enumerate(reversed(terms)):
        if all(i in active for i in term):
            result |= 1 << index
    return result


def insert_low(basis: dict[int, int], value: int) -> bool:
    while value:
        pivot = (value & -value).bit_length() - 1
        old = basis.get(pivot)
        if old is None:
            basis[pivot] = value
            return True
        value ^= old
    return False


def main() -> None:
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve the first independent audit")
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    rows_path = (HERE / protocol["input_rows"]).resolve()
    prior_audit_path = (HERE / protocol["input_sage_audit"]).resolve()
    assert sha(rows_path) == protocol["input_rows_sha256"] == result["source_sha256"]["rows"]
    assert sha(prior_audit_path) == protocol["input_sage_audit_sha256"]
    prior_audit = json.loads(prior_audit_path.read_text())
    assert prior_audit["status"] == "PASS" and prior_audit["sampled_rows_replayed"] == 8192
    assert prior_audit["source_sha256"]["samples"] == sha(rows_path)
    rows = json.loads(rows_path.read_text())["rows"]
    terms = monomials()
    basis: dict[int, int] = {}
    witness_indices = result["pivotal_row_indices"]
    assert len(witness_indices) == result["rank"]
    assert all(0 <= i < result["sample_rows_consumed"] for i in witness_indices)
    for index in witness_indices:
        assert insert_low(basis, feature_vector_reverse(rows[index], terms))
    assert len(basis) == result["rank"]
    status = "PASS_FULL_RANK" if len(basis) == len(terms) else "PASS_SAMPLE_ONLY"
    report = {
        "kind": "n41_two_pair_target_mixed_cubic_independent_rank_audit",
        "status": status,
        "feature_count": len(terms),
        "independent_rank": len(basis),
        "witness_rows_replayed": len(witness_indices),
        "prior_exact_group_rows_sage_replayed": prior_audit["sampled_rows_replayed"],
        "source_sha256": {
            "audit": sha(Path(__file__)),
            "protocol": sha(protocol_path),
            "screen_result": sha(result_path),
            "prior_rows": sha(rows_path),
            "prior_sage_audit": sha(prior_audit_path),
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "independent_rank", "witness_rows_replayed")}))


if __name__ == "__main__":
    main()
