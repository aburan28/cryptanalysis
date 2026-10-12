#!/usr/bin/env python3
"""Measure the exact target-conditioned middle S3 root continuation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1491 = PARENT / "q20261012_n83_mask_density"
Q1479 = PARENT / "q20261011_n83_distinct_roots"
TARGETS = {
    "selected": PARENT / "q20261011_wdsat_phase_restart/target.json",
    "holdout": PARENT / "q20261011_n83_selector_holdout/target.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def oracle():
    spec = importlib.util.spec_from_file_location("q1479_oracle", Q1479 / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = load(HERE / "protocol.json")
    drive = load(Q1491 / "drive_receipt.json")
    analysis = load(Q1491 / "analysis.json")
    assert drive["proposal_id"] == analysis["proposal_id"] == "Q1491"
    assert analysis["selected_workload_id"] == protocol["selected_workload_id"]
    assert analysis["holdout_workload_id"] == protocol["holdout_workload_id"]
    targets = {}
    for name, path in TARGETS.items():
        target = load(path)
        assert target["curve_id"] == protocol["curve_id"]
        assert target["workload_id"] == protocol[f"{name}_workload_id"]
        assert len(target["raw_preimage_x_coordinates"]) == 4
        assert len(set(target["raw_preimage_x_coordinates"])) == 4
        targets[name] = {"path": str(path), "sha256": sha(path),
                         "workload_id": target["workload_id"]}
    save(HERE / "freeze.json", {
        "proposal_id": "Q1492", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "target_continue.py", "validate.py")},
        "q1491_drive_sha256": sha(Q1491 / "drive_receipt.json"),
        "q1491_analysis_sha256": sha(Q1491 / "analysis.json"),
        "q1479_oracle_source_sha256": sha(Q1479 / "analyze.py"),
        "q1479_s3_source_sha256": sha(PARENT / "s3_root_oracle.py"),
        "targets": targets,
        "pair_receipts": {f"{r['input']}_phase{r['phase']}": r[
            "receipt_sha256"] for r in drive["rows"]},
    })
    print("Q1492 frozen", sha(HERE / "freeze.json")[:12])


def roots(onb, s3_roots, a: int, b: int) -> tuple:
    if not a and not b:
        return ()
    if not a:
        return (onb.inv(b),)
    if not b:
        return (onb.inv(a),)
    return s3_roots(onb, a, b)


def run() -> None:
    assert not (HERE / "result.json").exists()
    protocol, frozen = load(HERE / "protocol.json"), load(HERE / "freeze.json")
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert sha(Q1491 / "drive_receipt.json") == frozen["q1491_drive_sha256"]
    assert sha(Q1491 / "analysis.json") == frozen["q1491_analysis_sha256"]
    assert sha(Q1479 / "analyze.py") == frozen[
        "q1479_oracle_source_sha256"]
    assert sha(PARENT / "s3_root_oracle.py") == frozen[
        "q1479_s3_source_sha256"]
    module = oracle()
    onb = module.CountedOnb(83)
    target_xs = {}
    for name, record in frozen["targets"].items():
        path = Path(record["path"])
        assert sha(path) == record["sha256"]
        target = load(path)
        assert target["workload_id"] == record["workload_id"]
        target_xs[name] = target["raw_preimage_x_coordinates"]
    rows = []
    for key, digest in sorted(frozen["pair_receipts"].items()):
        path = Q1491 / "runs" / key / "receipt.json"
        assert sha(path) == digest
        pair = load(path)
        assert pair["status"] == "FIRST_PAIR_TERMINATED"
        name = pair["input"]
        assert pair["workload_id"] == protocol[f"{name}_workload_id"]
        first = module.replay_pair(onb, pair["first_pair_bits"])
        branches = []
        for root_index, u_coords in enumerate(first["root_coords"]):
            for target_index, t_coords in enumerate(target_xs[name]):
                onb.reset_counts()
                u = onb.fromCoords(u_coords)
                t = onb.fromCoords(t_coords)
                later = roots(onb, module.s3_roots, u, t)
                v_coords = [onb.toCoords(v) for v in later]
                calls = onb.snapshot_counts()
                branches.append({
                    "root_index": root_index,
                    "target_preimage_index": target_index,
                    "u_coords": u_coords, "target_x_coords": t_coords,
                    "v_coords": v_coords, "v_root_count": len(v_coords),
                    "field_api_calls": calls,
                    "field_api_entries": sum(calls.values()),
                })
        rows.append({
            "input": name, "phase": pair["phase"],
            "workload_id": pair["workload_id"],
            "first_pair_receipt_sha256": digest,
            "first_pair_root_count": first["root_count"],
            "target_branches": branches,
            "target_branch_count": len(branches),
            "target_branches_with_v_roots": sum(
                bool(branch["v_root_count"]) for branch in branches),
            "target_total_v_roots": sum(branch["v_root_count"] for branch in branches),
            "target_distinct_v_coords": len({v for branch in branches
                                             for v in branch["v_coords"]}),
            "target_field_api_entries": sum(
                branch["field_api_entries"] for branch in branches),
            "status": "TARGET_ROOT_CONTINUATION_COMPLETE",
        })
    summary = {}
    for name in ("selected", "holdout"):
        sub = [r for r in rows if r["input"] == name]
        summary[name] = {
            "first_pairs": len(sub),
            "pairs_with_first_roots": sum(bool(r["first_pair_root_count"])
                                          for r in sub),
            "target_branches": sum(r["target_branch_count"] for r in sub),
            "target_branches_with_v_roots": sum(
                r["target_branches_with_v_roots"] for r in sub),
            "target_total_v_roots": sum(r["target_total_v_roots"] for r in sub),
            "pairs_with_target_v_roots": sum(bool(r["target_total_v_roots"])
                                             for r in sub),
            "target_field_api_entries": sum(r["target_field_api_entries"]
                                            for r in sub),
        }
    save(HERE / "result.json", {
        "proposal_id": "Q1492", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol[
            "factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "summary": summary, "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    })
    print("Q1492", summary)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run"):
        raise SystemExit("usage: target_continue.py {freeze|run}")
    globals()[sys.argv[1]]()
