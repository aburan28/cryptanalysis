#!/usr/bin/env python3
"""Exhaust all valid mask pairs for the exact compressed column predicate."""

import collections
import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    columns = dict(tuple(map(int, row.split())) for row in SUPPORT.read_text().splitlines())
    groups = collections.defaultdict(list)
    for mask, column in columns.items():
        groups[column].append(mask)
    assert len(columns) == 8220 and len(groups) == 8160
    alias_pairs = {(a, b) for group in groups.values() for a in group for b in group
                   if a != b}
    assert len(alias_pairs) == 124
    masks = list(columns)
    started = time.monotonic()
    checked = 0
    for a in masks:
        column_a = columns[a]
        for b in masks:
            old_forbids = column_a == columns[b]
            compact_forbids = a == b or (a, b) in alias_pairs
            assert old_forbids == compact_forbids
            checked += 1
    receipt = {
        "status": "PASS_EXHAUSTIVE_N131_COLUMN_PREDICATE_EQUIVALENCE",
        "valid_masks": len(masks), "folded_columns": len(groups),
        "ordered_pairs_checked": checked,
        "ordered_distinct_alias_pairs": len(alias_pairs),
        "source_sha256": {"script": sha(__file__), "support": sha(SUPPORT),
                          "circuit": sha(HERE / "circuit.py")},
    }
    with (HERE / "column_equivalence.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "ordered_pairs_checked": checked,
                      "elapsed_seconds": time.monotonic() - started}))


if __name__ == "__main__":
    main()
