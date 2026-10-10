#!/usr/bin/env python3
"""Bind the native resultant oracle, all inputs, and its resource envelope."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    export = json.loads((HERE / "native_export.json").read_text())
    header = json.loads((HERE / "terms_header_receipt.json").read_text())
    sage41 = [json.loads((HERE / f"result_n41_{kind}.json").read_text())
              for kind in ("positive", "trace_zero_control")]
    sage131 = json.loads((HERE / "result_n131_positive.json").read_text())
    assert export["status"] == "PASS_NATIVE_PANEL_EXPORT"
    assert header["status"] == "PASS_RESULTANT_TERM_HEADER"
    assert header["source_sha256"]["header"] == sha(HERE / "resultant_terms.hpp")
    assert [row["status"] for row in sage41] == ["COMPLETE_ALGEBRAIC_SCAN"] * 2
    assert len(sage41[0]["algebraic_hits"]) == 2
    assert len(sage41[1]["algebraic_hits"]) == 0
    assert sage131["status"] == "CENSORED_TIME" and sage131["processed_product_states"] == 512
    paths = {"freeze": Path(__file__), "native_source": HERE / "native.cpp",
             "native_binary": HERE / "native", "terms_header": HERE / "resultant_terms.hpp",
             "terms": HERE / "resultant_terms.json", "inputs": HERE / "inputs.json",
             "export_script": HERE / "export_native.py", "export_receipt": HERE / "native_export.json",
             "header_receipt": HERE / "terms_header_receipt.json",
             "sage_runtime": HERE / "sage_runtime_info.json",
             "sage_n41_positive": HERE / "result_n41_positive.json",
             "sage_n41_control": HERE / "result_n41_trace_zero_control.json",
             "sage_n131_censored": HERE / "result_n131_positive.json",
             "runner": HERE / "run_native.py"}
    for n in (41, 131):
        for kind in ("positive", "trace_zero_control"):
            paths[f"native_input_n{n}_{kind}"] = HERE / f"native_n{n}_{kind}.txt"
    record = {
        "status": "FROZEN_BEFORE_NATIVE_FOUR_ATOM_PANEL",
        "kind": "native_degree_eight_same_seed_four_atom_oracle",
        "candidate_id": None, "target_count": 0,
        "curve_ids": ["EC1N41Ckb1h7d5e80d3c4d0", "EC1N131Ckb1heb5f1998f20b"],
        "workers": 1, "rss_cap_bytes": 4 * 1024**3,
        "parent_caps_seconds": {"41": 30, "131": 120},
        "internal_caps_seconds": {"41": 28, "131": 118},
        "run_order": ["n41_positive", "n41_trace_zero_control",
                      "n131_positive", "n131_trace_zero_control"],
        "promotion_gate": "native N41 positives and control reproduce the frozen complete Sage rows before N131",
        "source_sha256": {name: sha(path) for name, path in paths.items()},
    }
    with (HERE / "native_protocol.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": record["status"],
                      "binary_sha256": record["source_sha256"]["native_binary"]}))


if __name__ == "__main__":
    main()
