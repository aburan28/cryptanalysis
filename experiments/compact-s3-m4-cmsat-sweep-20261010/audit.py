#!/usr/bin/env python3
"""Audit the frozen bounded SAT cells and any returned group relations."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))

from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
from run_cell import verify_relation  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    frozen = read(HERE / "freeze.json")
    assert frozen["source_sha256"]["audit.py"] == sha(Path(__file__))
    parent = read(PARENT / "q1419_partial_pin/protocol.json")
    assert frozen["parent_q1419_protocol_sha256"] == sha(
        PARENT / "q1419_partial_pin/protocol.json")
    rows = []
    for name, setting in frozen["cell_order"]:
        label = f"{name}__{setting}"
        receipt = read(HERE / "runs" / f"{label}.json")
        out = HERE / "runs" / f"{label}.stdout.gz"
        err = HERE / "runs" / f"{label}.stderr.gz"
        assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
        assert receipt["proposal_id"] == frozen["proposal_id"]
        assert receipt["candidate_id"] is None and receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["input_name"] == name and receipt["setting"] == setting
        assert receipt["stdout_gzip_sha256"] == sha(out)
        assert receipt["stderr_gzip_sha256"] == sha(err)
        stdout = gzip.decompress(out.read_bytes()).decode(errors="replace")
        stderr = gzip.decompress(err.read_bytes()).decode(errors="replace")
        assert receipt["stdout_bytes"] == len(stdout.encode())
        assert receipt["stderr_bytes"] == len(stderr.encode())
        assert receipt["stderr_nonempty"] == bool(stderr.strip())
        expected = ("SAT" if receipt["return_code"] == 10
                    else "UNSAT" if receipt["return_code"] == 20
                    else "BOUNDED_UNKNOWN")
        assert receipt["status"] == expected
        matches = re.findall(r"Conflicts in UIP\s*:\s*([0-9]+)", stdout)
        assert receipt["conflicts_reported"] == (
            int(matches[-1]) if matches else None)
        assert receipt["formula_raw_sha256"] == frozen["inputs"][name][
            "raw_sha256"]
        degree = int(name[1:3])
        profile = dict(parent["profiles"][str(degree)])
        base = frozen["profiles"][str(degree)]
        assert receipt["curve_id"] == base["curve_id"] == profile["curve_id"]
        assert receipt["actual_usable_points_B"] == base[
            "actual_usable_points_B"] == profile["factor_base_actual_B"]
        assert receipt["folded_columns_K"] == base["folded_columns_K"] == (
            profile["folded_columns_K"])
        assert receipt["factor_base_enumerated_set_sha256"] == (
            base["factor_base_enumerated_set_sha256"] ==
            profile["factor_base_enumerated_set_sha256"])
        model_status = None
        if expected == "SAT":
            model = parsed_model(stdout)
            assert model is not None
            raw = gzip.decompress(Path(frozen["inputs"][name]["path"]).read_bytes())
            formula_check = check_serialized_xcnf(raw, model)
            if name == "n83_ordinary":
                parent_receipt = read(PARENT / "runs/n83_q1408_ordinary.json")
                profile["public_target"] = parent_receipt["public_target"]
                target_raw_xs = parent_receipt["raw_preimage_x_coordinates"]
            else:
                parent_receipt = read(ROOT / profile["parent_receipt"]["path"])
                target_raw_xs = parent_receipt["raw_preimage_x_coordinates"]
            assert receipt["formula_raw_sha256"] == (
                parent_receipt["attempts"][0]["xcnf_sha256"])
            _, leaves, _, _, _ = build_balanced(
                degree, profile["normal_basis_weight_bound"], target_raw_xs)
            relation = verify_relation(profile, model, leaves)
            model_status = relation["status"]
            assert model_status == "verified_four_point_relation"
            assert formula_check["variables"] > 0
        else:
            assert parsed_model(stdout) is None
        rows.append({"cell": label, "status": expected,
                     "conflicts": receipt["conflicts_reported"],
                     "wall_seconds_exploratory": receipt[
                         "wall_seconds_exploratory"],
                     "model_status": model_status,
                     "peak_child_rss_ru_maxrss": receipt[
                         "peak_child_rss_ru_maxrss"]})
    assert len(rows) == 18
    output = {
        "schema": "q20261010125300-cmsat-audit-v1",
        "proposal_id": frozen["proposal_id"], "status": "PASS",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)), "rows": rows,
        "ordinary_verified_relations": sum(
            x["model_status"] == "verified_four_point_relation" and
            "ordinary" in x["cell"] for x in rows),
        "n83_new_relation_needs_checked_sage_replay": any(
            x["model_status"] == "verified_four_point_relation" and
            x["cell"].startswith("n83_ordinary") for x in rows),
    }
    path = HERE / "audit.json"
    assert not path.exists()
    path.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "cells": len(rows),
                      "ordinary_relations": output["ordinary_verified_relations"]}))


if __name__ == "__main__":
    main()
