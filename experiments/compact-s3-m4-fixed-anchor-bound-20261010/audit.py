#!/usr/bin/env python3
"""Independent integer and identity replay of fixed-anchor bounds."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((HERE / "freeze.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert frozen["source_sha256"]["audit.py"] == sha(Path(__file__))
    assert result["proposal_id"] == frozen["proposal_id"]
    rows = []
    for profile in result["profiles"]:
        n = profile["field_degree_n"]
        b = profile["actual_usable_points_B"]
        k = profile["folded_columns_K"]
        d = profile["rational_raw_x_masks_D"]
        r = profile["subgroup_order_r"]
        assert d * 2 == b and d == n * k
        m = math.comb(b + 1, 2)
        assert m == int(profile["right_unordered_pairs_including_repeats"])
        for row in profile["fanout_rows"]:
            h = row["maximum_fixed_left_sums_per_scan_h"]
            scans = int(row["necessary_complete_scans_for_95pct_rank"])
            assert int(row["necessary_rational_root_visits"]) == scans * d
            threshold = Fraction(19 * k, 20)
            expected_at_s = Fraction(scans * h * m, r - 1)
            expected_before = Fraction((scans - 1) * h * m, r - 1)
            assert expected_before < threshold <= expected_at_s
            assert scans >= 1
            rows.append({"label": profile["label"], "h": h,
                         "scans": str(scans), "root_visits": str(scans*d),
                         "minimality_verified": True})
    assert len(rows) == 12
    by_key = {(p["label"], row["maximum_fixed_left_sums_per_scan_h"]):
              int(row["necessary_rational_root_visits"])
              for p in result["profiles"] for row in p["fanout_rows"]}
    for h in (1, 2, 8):
        a = by_key[("N131_W5", h)]
        b = by_key[("N131_W6", h)]
        assert abs(a - b) * 1_000_000 < max(a, b)
    output = {"schema": "q20261010123500-independent-audit-v2",
              "proposal_id": result["proposal_id"], "status": "PASS",
              "freeze_sha256": sha(HERE / "freeze.json"),
              "result_sha256": sha(HERE / "result.json"),
              "source_sha256": sha(Path(__file__)),
              "exact_minimality_rows": rows,
              "n131_w5_w6_root_bound_relative_difference_lt_1ppm": True}
    path = HERE / "audit.json"
    assert not path.exists()
    path.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "rows": len(rows)}))


if __name__ == "__main__":
    main()
