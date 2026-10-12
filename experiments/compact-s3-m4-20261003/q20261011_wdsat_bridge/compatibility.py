#!/usr/bin/env python3
"""Count clause widths that WDSat's pinned CNF implication loader handles."""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
UPSTREAM = Path("/private/tmp/wdsat-q1458")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    freeze = json.loads((HERE / "freeze.json").read_text())
    source = (UPSTREAM / "src/cnf.c").read_bytes()
    marker = b"switch (_dimacs_size_of_equations[i]) {"
    assert source.count(marker) == 1
    block = source[source.index(marker):source.index(b"/// from temporary to static structures")]
    assert all(b"case " + str(i).encode() + b":" in block for i in (1, 2, 3, 4))
    assert b"case 5:" not in block and b"default:" not in block
    cells = {}
    for cell, frozen in freeze["cells"].items():
        archive = (PARENT / "q1419_partial_pin/runs" / cell / "system.xcnf.gz").read_bytes()
        assert sha(archive) == frozen["formula_archive_sha256"]
        raw = gzip.decompress(archive)
        assert sha(raw) == frozen["formula_raw_sha256"]
        widths = collections.Counter()
        for line in raw.splitlines()[1:]:
            tokens = line.split()
            if tokens[0].startswith(b"x"):
                continue
            widths[len(tokens) - 1] += 1
        cells[cell] = {"cnf_clause_width_counts": dict(sorted(widths.items())),
                       "cnf_clauses_gt4": sum(count for width, count in widths.items()
                                               if width > 4),
                       "direct_input_supported": not any(width > 4 for width in widths)}
    output = {"proposal_id": "Q1458", "status": "DIRECT_INPUT_UNSUPPORTED",
              "upstream_commit": freeze["upstream_commit"],
              "cnf_source_sha256": sha(source), "handled_clause_widths": [1, 2, 3, 4],
              "freeze_sha256": sha((HERE / "freeze.json").read_bytes()),
              "cells": cells, "authoritative_solver_comparison": False}
    (HERE / "compatibility.json").write_text(json.dumps(output, indent=2,
                                                         sort_keys=True) + "\n")
    print(json.dumps({name: cell["cnf_clauses_gt4"] for name, cell in cells.items()}))


if __name__ == "__main__":
    main()
