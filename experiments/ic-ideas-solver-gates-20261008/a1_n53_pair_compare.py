#!/usr/bin/env python3
"""Paired ordinary-query comparison for N53 seed and multiplier bases."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_two_sided_discordance(a: int, b: int) -> float:
    total = a + b
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(min(a, b) + 1)) / 2**total
    return min(1.0, 2 * tail)


def main() -> None:
    output = HERE / "a1_n53_pair_comparison.json"
    if output.exists():
        raise FileExistsError(output)
    cells = {}
    for policy in ("seed", "closure"):
        prefix = f"a1_n53_pair_{policy}_k600_q64"
        receipt_path = HERE / f"{prefix}.json"
        raw_path = HERE / f"{prefix}_raw.json"
        receipt = json.loads(receipt_path.read_text())
        raw = json.loads(raw_path.read_text())
        assert receipt["status"] == "completed_verified"
        assert receipt["raw_sha256"] == sha(raw_path)
        assert raw["actual_usable_B"] == 63_600
        assert raw["geometric_columns"] == 600
        assert raw["query_count"] == 64
        assert raw["verified_hits"] == sum(row["hit"] for row in raw["rows"])
        assert raw["rank"] == sum(row["novel_row"] for row in raw["rows"])
        cells[policy] = (receipt, raw, receipt_path, raw_path)
    seed = cells["seed"][1]
    closure = cells["closure"][1]
    assert [(row["scalar"], row["target_point"]) for row in seed["rows"]] == [
        (row["scalar"], row["target_point"]) for row in closure["rows"]]
    paired = [{"query_index": i,
               "seed_hit": seed["rows"][i]["hit"],
               "closure_hit": closure["rows"][i]["hit"],
               "seed_novel": seed["rows"][i]["novel_row"],
               "closure_novel": closure["rows"][i]["novel_row"]}
              for i in range(64)]
    seed_only = sum(row["seed_hit"] and not row["closure_hit"] for row in paired)
    closure_only = sum(row["closure_hit"] and not row["seed_hit"] for row in paired)
    both = sum(row["seed_hit"] and row["closure_hit"] for row in paired)
    neither = sum(not row["seed_hit"] and not row["closure_hit"] for row in paired)
    summary = []
    for policy in ("seed", "closure"):
        receipt, raw, receipt_path, raw_path = cells[policy]
        summary.append({"policy": policy,
                        "actual_usable_B": raw["actual_usable_B"],
                        "geometric_columns": raw["geometric_columns"],
                        "independent_log_columns": raw["independent_log_columns"],
                        "verified_hits": raw["verified_hits"],
                        "novel_rows": raw["novel_rows"],
                        "hit_wilson95": receipt["wilson95"],
                        "pair_sums": raw["pair_sums"],
                        "distinct_pair_x_orbit_keys": raw["distinct_pair_x_orbit_keys"],
                        "query_lookups": raw["lookups"],
                        "lookups_per_verified_hit":
                            raw["lookups"] / raw["verified_hits"]
                            if raw["verified_hits"] else None,
                        "index_build_ms_exploratory":
                            raw["index_build_ms_exploratory"],
                        "query_ms_exploratory": raw["query_ms_exploratory"],
                        "raw_sha256": sha(raw_path),
                        "receipt_sha256": sha(receipt_path)})
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "field_degree": 53, "curve_a": 0,
              "query_count": 64,
              "query_law": seed["query_law"],
              "query_seed": seed["query_seed"],
              "equal_geometry_B": 63_600,
              "paired_outcomes": {"both": both, "seed_only": seed_only,
                                  "closure_only": closure_only,
                                  "neither": neither},
              "paired_exact_two_sided_p":
                  exact_two_sided_discordance(seed_only, closure_only),
              "cells": summary,
              "per_query": paired,
              "source_sha256": sha(Path(__file__))}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"seed_hits": seed["verified_hits"],
                      "closure_hits": closure["verified_hits"],
                      "paired_outcomes": answer["paired_outcomes"],
                      "p": answer["paired_exact_two_sided_p"]}))


if __name__ == "__main__":
    main()
