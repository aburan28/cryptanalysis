#!/usr/bin/env python3
"""Lower the exact Q1513 direct handoff XCNF to WDSat width-four input."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1513 = PARENT / "q20261012_fixed_pair_s3_handoff"
Q1459 = PARENT / "q20261011_wdsat_width_lift"
sys.path.insert(0, str(Q1459))
from prepare import evaluate, parse_model, transform, true  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main():
    cells = {}
    for label in ("n53_known_pair_pinned", "n53_known_complement_unpinned",
                  "n83_planted_pinned", "n83_ordinary_selected", "n83_ordinary_holdout"):
        source_path = Q1513 / f"{label}.xcnf"
        original = source_path.read_bytes()
        source_receipt = json.loads((Q1513 / f"{label}.json").read_text())
        assert sha(original) == source_receipt["formula_sha256"]
        derived, rules, stats = transform(original)
        target = HERE / f"{label}.width4.xcnf"
        target.write_bytes(derived)
        replay = None
        if source_receipt["status"] == "SAT_VERIFIED":
            model = parse_model(Q1513 / f"{label}.stdout.txt", stats["original_variables"])
            original_check = evaluate(original, model)
            for auxiliary, prefix in rules:
                model[auxiliary] = not any(true(literal, model) for literal in prefix)
            derived_check = evaluate(derived, model)
            assert derived_check["max_cnf_width"] <= 4
            replay = {"original": original_check, "derived": derived_check}
        cells[label] = {"source_sha256": sha(original), "derived_sha256": sha(derived),
                        "source_receipt_sha256": sha((Q1513 / f"{label}.json").read_bytes()),
                        "lifted_witness_replay": replay, **stats}
    result = {"proposal_id": "Q1514", "candidate_id": None, "run_id": None,
              "isogeny": "none", "classification": "retrospective_exploratory",
              "width_lift_source_sha256": sha((Q1459 / "prepare.py").read_bytes()),
              "cells": cells}
    (HERE / "prepare_receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: {"vars": row["derived_variables"],
                             "rows": row["derived_rows"], "xor": row["xor_rows"]}
                      for name, row in cells.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
