#!/usr/bin/env python3
"""Freeze paired Q1513 and inverse-reuse one-link N83 S3 formulas."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1513 = HERE.parent / "q20261012_fixed_pair_s3_handoff"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


parent = module("q1513_run_for_q1522", Q1513 / "run.py")
leaf = module("q1522_double_leaf", HERE / "double_leaf.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main():
    p = read(HERE / "protocol.json")
    assert sha(Q1513 / "run.py") == p["q1513_source_sha256"]
    assert sha(HERE / "double_leaf.py") == p["double_leaf_source_sha256"]
    assert not (HERE / "build_receipt.json").exists()
    out = HERE / "formulas"
    out.mkdir(exist_ok=False)
    rows = []
    for label in p["inputs"]:
        prior = read(Q1513 / f"{label}.json")
        assert sha(Q1513 / f"{label}.json") == p["inputs"][label]["receipt_sha256"]
        assert prior["complement_x_coords"] == p["inputs"][label]["complement_x_coords"]
        assert prior["pin_raw"] == p["inputs"][label]["pin_raw"]
        baseline, raw, _, _ = parent.build(83, prior["complement_x_coords"])
        for bits, value in zip(raw, prior["pin_raw"]):
            parent.pin_bits(baseline, bits, value)
        old_path = out / f"{label}_baseline.xcnf"
        baseline.write(old_path)
        assert sha(old_path) == prior["formula_sha256"]
        old_leaf = parent.projected_sparse_leaf
        try:
            parent.projected_sparse_leaf = leaf.projected_sparse_leaf_double_reuse
            variant, raw2, _, _ = parent.build(83, prior["complement_x_coords"])
        finally:
            parent.projected_sparse_leaf = old_leaf
        for bits, value in zip(raw2, prior["pin_raw"]):
            parent.pin_bits(variant, bits, value)
        new_path = out / f"{label}_reuse.xcnf"
        variant.write(new_path)
        rows.append({"label": label, "baseline_formula_sha256": sha(old_path),
                     "reuse_formula_sha256": sha(new_path),
                     "baseline_variables": baseline.variables,
                     "reuse_variables": variant.variables,
                     "baseline_cnf_clauses": len(baseline.clauses),
                     "reuse_cnf_clauses": len(variant.clauses),
                     "baseline_xor_rows": len(baseline.xors),
                     "reuse_xor_rows": len(variant.xors)})
    save(HERE / "build_receipt.json", {
        "proposal_id": "Q1522", "candidate_id": None,
        "curve_id": p["curve_id"], "isogeny": "none",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)), "rows": rows})
    for row in rows:
        print(row["label"], row["baseline_variables"], row["reuse_variables"],
              row["baseline_cnf_clauses"], row["reuse_cnf_clauses"], flush=True)


if __name__ == "__main__":
    main()
