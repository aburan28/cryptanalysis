#!/usr/bin/env python3
"""Independent low-pivot and reversed-column audit for the y gate."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from audit import insert_low, sha

HERE = Path(__file__).resolve().parent


def main() -> None:
    output = HERE / "audit_y.json"
    if output.exists():
        raise FileExistsError("preserve the first y-coordinate audit")
    protocol_path = HERE / "protocol_y.json"
    result_path = HERE / "result_y.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    rows_path = (HERE / protocol["input_rows"]).resolve()
    audit_path = (HERE / protocol["input_sage_audit"]).resolve()
    assert sha(rows_path) == protocol["input_rows_sha256"] == result["source_sha256"]["rows"]
    assert sha(audit_path) == protocol["input_sage_audit_sha256"]
    prior = json.loads(audit_path.read_text())
    assert prior["status"] == "PASS" and prior["sampled_rows_replayed"] == 8192
    assert prior["source_sha256"]["samples"] == sha(rows_path)
    rows = json.loads(rows_path.read_text())["rows"]
    terms = [()] + [(i,) for i in range(53)]
    terms += list(itertools.combinations(range(53), 2))
    terms += [(a, 6 + b, 12 + t)
              for a in range(6) for b in range(6) for t in range(41)]
    assert len(terms) == len(set(terms)) == result["feature_count"] == 2908
    basis: dict[int, int] = {}
    for index in result["pivotal_row_indices"]:
        row = rows[index]
        sums = row["pair_seed_sums"]
        y = row["target"][1]
        active = ({i for i in range(6) if (sums[0] >> i) & 1}
                  | {6 + i for i in range(6) if (sums[1] >> i) & 1}
                  | {12 + i for i in range(41) if (y >> i) & 1})
        vector = 0
        for at, term in enumerate(reversed(terms)):
            if all(i in active for i in term):
                vector |= 1 << at
        assert insert_low(basis, vector)
    assert len(basis) == result["rank"]
    report = {
        "kind": "n41_two_pair_target_y_mixed_cubic_independent_rank_audit",
        "status": "PASS_FULL_RANK" if len(basis) == len(terms) else "PASS_SAMPLE_ONLY",
        "feature_count": len(terms),
        "independent_rank": len(basis),
        "witness_rows_replayed": len(result["pivotal_row_indices"]),
        "prior_exact_group_rows_sage_replayed": prior["sampled_rows_replayed"],
        "source_sha256": {
            "audit_y": sha(Path(__file__)),
            "protocol_y": sha(protocol_path),
            "screen_y_result": sha(result_path),
            "prior_rows": sha(rows_path),
            "prior_sage_audit": sha(audit_path),
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "independent_rank", "witness_rows_replayed")}))


if __name__ == "__main__":
    main()
