#!/usr/bin/env python3
"""Check frozen Q1495 membership/count and paired operation receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import filter as rationality

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol, frozen, result = (load(HERE / n) for n in
                                ("protocol.json", "freeze.json", "result.json"))
    assert protocol["proposal_id"] == frozen["proposal_id"] == result[
        "proposal_id"] == "Q1495"
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["source_sha256"] == sha(HERE / "filter.py")
    assert sha(rationality.BASE53) == frozen["base53_sha256"]
    assert sha(rationality.BASE83) == frozen["base83_sha256"]
    assert sha(rationality.KEYS83) == frozen["base83_keys_sha256"]
    assert sha(rationality.Q1494) == frozen["q1494_result_sha256"]
    base53, base83 = rationality.load(rationality.BASE53), rationality.load(
        rationality.BASE83)
    assert result["n53"]["rational_x_masks"] == base53["factor_base"][
        "geometric_rational_x_count"] == 12_031
    assert result["n53"]["predicate_equals_curve_lift_for_all_masks"]
    assert result["n83"]["rational_x_orbits"] == base83["factor_base"][
        "rational_raw_x_orbits"] == 186_612
    assert result["n83"][
        "all_rational_orbits_project_to_distinct_usable_columns"]
    stage = result["n83_pair_stage_cost"]
    assert stage["pairs"] == len(stage["rows"]) == 40
    assert stage["usable_pairs"] == 8
    old = rationality.load(rationality.Q1494)
    old_rows = {r["phase"]: r for r in old["rows"]}
    onb = rationality.CountedOnb(83)
    for row in stage["rows"]:
        source = old_rows[row["phase"]]
        onb.reset_counts()
        observed = True
        checked = 0
        for leaf in source["leaves"]:
            observed = rationality.exact_predicate(onb, leaf["coords"])
            checked += 1
            if not observed:
                break
        assert observed == source["both_usable"] == row["both_usable"]
        assert checked == row["leaves_checked"]
        assert onb.snapshot_counts() == row["short_filter_field_api_calls"]
        assert sum(onb.snapshot_counts().values()) == row[
            "short_filter_field_api_entries"]
        assert source["field_api_entries_for_base_filter"] == row[
            "exact_full_filter_field_api_entries"]
    assert sum(r["short_filter_field_api_entries"] for r in stage["rows"]) == 427
    assert sum(r["exact_full_filter_field_api_entries"] for r in
               stage["rows"]) == 5_948
    assert result["complete_n131_solve_work_log2"] is None
    print("PASS Q1495", result["n53"]["x_masks"],
          result["n83"]["x_orbits"], stage["full_over_short_field_api_ratio"])


if __name__ == "__main__":
    main()
