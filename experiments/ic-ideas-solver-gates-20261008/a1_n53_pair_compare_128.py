#!/usr/bin/env python3
"""Paired 128-query N53 relation yield and rank saturation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from a1_n53_pair_compare import exact_two_sided_discordance

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "a1_n53_pair_comparison_128.json"
    if output.exists():
        raise FileExistsError(output)
    cells = {}
    for policy in ("seed", "closure"):
        prefix = f"a1_n53_pair_{policy}_k600_q128"
        receipt_path = HERE / f"{prefix}.json"
        raw_path = HERE / f"{prefix}_raw.json"
        receipt = json.loads(receipt_path.read_text())
        raw = json.loads(raw_path.read_text())
        assert receipt["status"] == "completed_verified"
        assert receipt["raw_sha256"] == sha(raw_path)
        assert raw["actual_usable_B"] == 63_600 and raw["query_count"] == 128
        cells[policy] = (receipt, raw, receipt_path, raw_path)
    seed = cells["seed"][1]
    closure = cells["closure"][1]
    assert [(row["scalar"], row["target_point"]) for row in seed["rows"]] == [
        (row["scalar"], row["target_point"]) for row in closure["rows"]]
    assert seed["rows"][:64] == json.loads((HERE /
        "a1_n53_pair_seed_k600_q64_raw.json").read_text())["rows"]
    assert closure["rows"][:64] == json.loads((HERE /
        "a1_n53_pair_closure_k600_q64_raw.json").read_text())["rows"]
    both = sum(a["hit"] and b["hit"] for a, b in zip(seed["rows"], closure["rows"]))
    seed_only = sum(a["hit"] and not b["hit"] for a, b in zip(seed["rows"], closure["rows"]))
    closure_only = sum(not a["hit"] and b["hit"] for a, b in zip(seed["rows"], closure["rows"]))
    neither = 128 - both - seed_only - closure_only
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "field_degree": 53, "query_count": 128,
              "query_law": seed["query_law"], "query_seed": seed["query_seed"],
              "equal_geometry_B": 63_600,
              "paired_outcomes": {"both": both, "seed_only": seed_only,
                                  "closure_only": closure_only, "neither": neither},
              "paired_exact_two_sided_p":
                  exact_two_sided_discordance(seed_only, closure_only),
              "cells": [
                  {"policy": policy,
                   "independent_log_columns": raw["independent_log_columns"],
                   "verified_hits": raw["verified_hits"],
                   "novel_rows": raw["novel_rows"],
                   "hit_wilson95": receipt["wilson95"],
                   "query_lookups": raw["lookups"],
                   "raw_sha256": sha(raw_path),
                   "receipt_sha256": sha(receipt_path)}
                  for policy, (receipt, raw, receipt_path, raw_path) in cells.items()],
              "source_sha256": sha(Path(__file__))}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"paired_outcomes": answer["paired_outcomes"],
                      "seed_rank": seed["rank"],
                      "closure_rank": closure["rank"]}))


if __name__ == "__main__":
    main()
