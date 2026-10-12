#!/usr/bin/env python3
"""Read-only formula, raw SAT-status, and curve-doubling audit for Q1522."""
import itertools
import json
import math
import re
import sys
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent
Q1513 = HERE.parent / "q20261012_fixed_pair_s3_handoff"


def check():
    p = build.read(HERE / "protocol.json")
    direct_p = build.read(HERE / "direct_protocol.json")
    prior = build.read(Q1513 / "n83_planted_pinned.json")
    assert prior["status"] == "SAT_VERIFIED"
    assert prior["check"]["s3_and_group_relation_checked"]
    assert build.sha(Q1513 / "run.py") == p["q1513_source_sha256"]
    assert build.sha(HERE / "double_leaf.py") == p["double_leaf_source_sha256"]
    assert build.sha(HERE / "direct_leaf.py") == direct_p["direct_leaf_source_sha256"]
    assert build.sha(HERE / "build_receipt.json") == direct_p["inverse_variant_build_sha256"]
    assert build.sha(Path(p["solver_binary"])) == p["solver_binary_sha256"]
    receipts = (build.read(HERE / "build_receipt.json"),
                build.read(HERE / "direct_build_receipt.json"))
    results = (build.read(HERE / "result.json"),
               build.read(HERE / "direct_result.json"))
    assert receipts[0]["protocol_sha256"] == build.sha(HERE / "protocol.json")
    assert receipts[1]["protocol_sha256"] == build.sha(HERE / "direct_protocol.json")
    variants = {}
    for name, protocol, receipt, result, formulas, runs in (
        ("inverse_two_product", p, receipts[0], results[0], "formulas", "runs"),
        ("direct_two_product", direct_p, receipts[1], results[1],
         "direct_formulas", "direct_runs")):
        proto_path = HERE / ("protocol.json" if name == "inverse_two_product"
                             else "direct_protocol.json")
        source = HERE / ("run.py" if name == "inverse_two_product" else "direct_run.py")
        assert result["protocol_sha256"] == build.sha(proto_path)
        assert result["source_sha256"] == build.sha(source)
        assert [r["label"] for r in result["rows"]] == protocol["measurement_order"]
        cells = []
        for shape, row in zip(receipt["rows"], sorted(result["rows"], key=lambda r:r["label"])):
            label = row["label"]
            assert shape["label"] == label
            formula = HERE / formulas / (f"{label}_reuse.xcnf" if name == "inverse_two_product"
                                          else f"{label}.xcnf")
            digest = (shape["reuse_formula_sha256"] if name == "inverse_two_product"
                      else shape["formula_sha256"])
            assert build.sha(formula) == row["formula_sha256"] == digest
            folder = HERE / runs / label
            assert build.read(folder / "receipt.json") == row
            assert build.sha(folder / "stdout.txt") == row["stdout_sha256"]
            assert build.sha(folder / "stderr.txt") == row["stderr_sha256"]
            output = (folder / "stdout.txt").read_text(errors="replace")
            conflicts = re.findall(r"^c\s*conflicts\s*:\s*([0-9]+)", output, re.M)
            assert row["exact_conflicts_if_reported"] == (
                int(conflicts[-1]) if conflicts else None)
            assert row["status"] in ("INDETERMINATE", "CPU_CAP", "WALL_CAP",
                                     "SAT_VERIFIED")
            if row["status"] == "SAT_VERIFIED":
                assert row["check"] and row["check"]["s3_and_group_relation_checked"]
            else:
                assert row["check"] is None
            cells.append({"label": label, "status": row["status"],
                          "reported_conflicts": row["exact_conflicts_if_reported"],
                          "child_user_cpu_seconds": row["child_user_cpu_seconds"],
                          "peak_rss_bytes_darwin": row["child_peak_rss_bytes_darwin"]})
        planted = next(r for r in cells if r["label"] == "n83_planted_pinned")
        ordinary = next(r for r in receipt["rows"] if r["label"] == "n83_ordinary_selected")
        variants[name] = {"variables": ordinary.get("reuse_variables", ordinary.get("variables")),
                          "cnf_clauses": ordinary.get("reuse_cnf_clauses", ordinary.get("cnf_clauses")),
                          "xor_rows": ordinary.get("reuse_xor_rows", ordinary.get("xor_rows")),
                          "planted_control_status": planted["status"], "cells": cells}
    baseline = next(r for r in receipts[0]["rows"] if r["label"] == "n83_ordinary_selected")
    onb = build.parent.field.Onb(83)
    curve = build.parent.curves.Curve(onb)
    checked = 0
    for weight in (1, 2, 3):
        for support in itertools.islice(itertools.combinations(range(83), weight), 50):
            x = onb.fromCoords(sum(1 << bit for bit in support))
            point = curve.pointFromX(x)
            if point is None:
                continue
            inv = onb.inv(x)
            x2 = onb.add(onb.sqr(x), onb.sqr(inv))
            twice = curve.mul(point, 2)
            if twice is None:
                continue
            assert x2 == twice[0]
            four = curve.mul(point, 4)
            if four is None:
                continue
            x4 = onb.add(onb.sqr(x2), onb.sqr(onb.inv(x2)))
            assert x4 == four[0]
            assert onb.mul(x4, onb.sqr(x2)) == onb.add(
                onb.sqr(onb.sqr(x2)), onb.one())
            old_denominator = onb.add(onb.pow(x, 12), onb.pow(x, 4))
            old_numerator = onb.add(onb.add(onb.pow(x, 16),
                                            onb.pow(x, 8)), onb.one())
            assert onb.mul(x4, old_denominator) == old_numerator
            checked += 1
    assert checked > 0
    return {"proposal_id": "Q1522", "candidate_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "baseline_variables": baseline["baseline_variables"],
            "baseline_cnf_clauses": baseline["baseline_cnf_clauses"],
            "baseline_xor_rows": baseline["baseline_xor_rows"],
            "baseline_planted_control_status": prior["status"],
            "characteristic_two_curve_doubling_samples_checked": checked,
            "variants": variants,
            "ordinary_verified_relations": 0,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2,
                                                       sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert analysis == build.read(HERE / "analysis.json")
    print("PASS Q1522 formula-size, capped-SAT, and curve-doubling audit")
