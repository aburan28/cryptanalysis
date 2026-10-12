#!/usr/bin/env python3
"""Freeze exact ordinary Q1410/Q1408 XCNFs under Q1460 shared-prefix encoding."""
from __future__ import annotations
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ADAPTER = PARENT / "q20261011_wdsat_shared_prefix"
sys.path.insert(0, str(ADAPTER))
from prepare import transform  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sizes(raw: bytes) -> dict:
    lines = raw.splitlines()
    head = lines[0].split()
    assert head[:2] == [b"p", b"cnf"] and len(head) == 4
    variables, rows = map(int, head[2:])
    cnf = xor = cnf_occ = xor_occ = implication_slots = max_cnf = max_xor = 0
    for line in lines[1:]:
        tokens = line.split()
        assert tokens[-1] == b"0"
        width = len(tokens) - 1
        if tokens[0].startswith(b"x"):
            xor += 1; xor_occ += width; max_xor = max(max_xor, width)
        else:
            assert 1 <= width <= 4
            cnf += 1; cnf_occ += width; max_cnf = max(max_cnf, width)
            implication_slots += width * (width - 1)
    assert cnf + xor == rows
    return {"variables": variables, "rows": rows, "cnf_clauses": cnf,
            "xor_rows": xor, "cnf_occurrences": cnf_occ,
            "xor_occurrences": xor_occ,
            "cnf_implication_slots": implication_slots,
            "max_cnf_width": max_cnf, "max_xor_width": max_xor}


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol_bytes = (HERE / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    builder_bytes = (ADAPTER / "build_receipt.json").read_bytes()
    builder = json.loads(builder_bytes)
    assert builder["proposal_id"] == "Q1460"
    cells = {}
    for degree, parent_id in ((53, "Q1410"), (83, "Q1408")):
        name = f"n{degree}"
        source = PARENT / "runs" / f"n{degree}_q{parent_id[1:]}_ordinary"
        receipt_file = source.with_suffix(".json")
        archive_file = source.with_suffix(".xcnf.gz")
        receipt = json.loads(receipt_file.read_text())
        archive = archive_file.read_bytes()
        raw = gzip.decompress(archive)
        assert receipt["proposal_id"] == parent_id
        assert receipt["curve_id"] == protocol["inputs"][name]["curve_id"]
        assert receipt["factor_base_actual_B"] == protocol["inputs"][name]["factor_base_actual_B"]
        assert receipt["factor_base_enumerated_set_sha256"] == protocol["inputs"][name]["factor_base_enumerated_set_sha256"]
        assert receipt["workload_id"] == protocol["inputs"][name]["workload_id"]
        assert receipt["isogeny"] == "none"
        assert sha(raw) == receipt["attempts"][0]["xcnf_sha256"]
        assert len(raw) == receipt["attempts"][0]["xcnf_bytes"]
        derived, _, stats = transform(raw)
        dimensions = sizes(derived)
        assert dimensions["variables"] == stats["derived_variables"]
        assert dimensions["rows"] == stats["derived_rows"]
        caps = builder["per_degree"][name]["config"]
        assert dimensions["variables"] <= caps["MAX_ID"]
        assert dimensions["rows"] < caps["MAX_EQ"]
        assert dimensions["xor_rows"] < caps["MAX_XEQ"]
        assert dimensions["max_cnf_width"] < caps["MAX_EQ_SIZE"]
        assert dimensions["max_xor_width"] < caps["MAX_XEQ_SIZE"]
        assert dimensions["cnf_occurrences"] + dimensions["xor_occurrences"] < caps["MAX_BUFFER_SIZE"]
        assert dimensions["cnf_implication_slots"] < caps["MAX_BUFFER_SIZE"]
        encoded = gzip.compress(derived, mtime=0)
        (HERE / f"{name}_ordinary.xcnf.gz").write_bytes(encoded)
        cells[name] = {"curve_id": receipt["curve_id"],
                       "workload_id": receipt["workload_id"],
                       "factor_base_actual_B": receipt["factor_base_actual_B"],
                       "factor_base_folded_columns_K": protocol["inputs"][name]["factor_base_folded_columns_K"],
                       "factor_base_enumerated_set_sha256": receipt["factor_base_enumerated_set_sha256"],
                       "public_target": receipt["public_target"],
                       "source_receipt_sha256": sha(receipt_file.read_bytes()),
                       "source_archive_sha256": sha(archive),
                       "source_raw_sha256": sha(raw),
                       "derived_archive_sha256": sha(encoded),
                       "derived_raw_sha256": sha(derived),
                       "transform_stats": stats, "dimensions": dimensions}
        print(name, stats["auxiliary_variables"], dimensions["rows"])
    freeze = {"proposal_id": "Q1463", "candidate_id": None,
              "protocol_sha256": sha(protocol_bytes),
              "prepare_source_sha256": sha(Path(__file__).read_bytes()),
              "adapter_source_sha256": sha((ADAPTER / "prepare.py").read_bytes()),
              "adapter_equivalence_check_sha256": sha((ADAPTER / "equivalence_check.json").read_bytes()),
              "builder_receipt_sha256": sha(builder_bytes),
              "cells": cells}
    (HERE / "freeze.json").write_text(json.dumps(freeze, indent=2,
                                                  sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
