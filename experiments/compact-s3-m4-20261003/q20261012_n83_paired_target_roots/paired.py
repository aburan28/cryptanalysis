#!/usr/bin/env python3
"""Continue one frozen first-pair set against two ordinary N83 targets."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1491 = PARENT / "q20261012_n83_mask_density"
Q1492 = PARENT / "q20261012_n83_target_continuation"
sys.path.insert(0, str(Q1492))
import target_continue as prior  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = load(HERE / "protocol.json")
    drive = load(Q1491 / "drive_receipt.json")
    selected = [r for r in drive["rows"] if r["input"] == "selected"]
    assert len(selected) == 40
    targets = {}
    for name, path in prior.TARGETS.items():
        target = load(path)
        assert target["curve_id"] == protocol["curve_id"]
        assert target["workload_id"] == protocol[f"{name}_workload_id"]
        assert len(target["raw_preimage_x_coordinates"]) == 4
        targets[name] = {"path": str(path), "sha256": sha(path)}
    save(HERE / "freeze.json", {
        "proposal_id": "Q1493", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "paired.py", "validate.py")},
        "q1491_drive_sha256": sha(Q1491 / "drive_receipt.json"),
        "q1492_result_sha256": sha(Q1492 / "result.json"),
        "q1492_source_sha256": sha(Q1492 / "target_continue.py"),
        "pair_receipts": {str(r["phase"]): r["receipt_sha256"]
                          for r in selected},
        "targets": targets,
    })
    print("Q1493 frozen", sha(HERE / "freeze.json")[:12])


def run() -> None:
    assert not (HERE / "result.json").exists()
    protocol, frozen = load(HERE / "protocol.json"), load(HERE / "freeze.json")
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert sha(Q1491 / "drive_receipt.json") == frozen["q1491_drive_sha256"]
    assert sha(Q1492 / "result.json") == frozen["q1492_result_sha256"]
    assert sha(Q1492 / "target_continue.py") == frozen[
        "q1492_source_sha256"]
    module = prior.oracle()
    onb = module.CountedOnb(83)
    target_xs = {}
    for name, record in frozen["targets"].items():
        path = Path(record["path"])
        assert sha(path) == record["sha256"]
        target_xs[name] = load(path)["raw_preimage_x_coordinates"]
    rows = []
    for phase, digest in sorted(frozen["pair_receipts"].items(),
                                key=lambda item: int(item[0])):
        path = Q1491 / "runs" / f"selected_phase{phase}" / "receipt.json"
        assert sha(path) == digest
        pair = load(path)
        assert pair["status"] == "FIRST_PAIR_TERMINATED"
        first = module.replay_pair(onb, pair["first_pair_bits"])
        for target_name in ("selected", "holdout"):
            branches = []
            for u_index, u_coords in enumerate(first["root_coords"]):
                for t_index, t_coords in enumerate(target_xs[target_name]):
                    onb.reset_counts()
                    u = onb.fromCoords(u_coords)
                    t = onb.fromCoords(t_coords)
                    vs = prior.roots(onb, module.s3_roots, u, t)
                    v_coords = [onb.toCoords(v) for v in vs]
                    calls = onb.snapshot_counts()
                    branches.append({
                        "u_index": u_index, "target_preimage_index": t_index,
                        "u_coords": u_coords, "target_x_coords": t_coords,
                        "v_coords": v_coords, "field_api_calls": calls,
                        "field_api_entries": sum(calls.values()),
                    })
            rows.append({
                "phase": int(phase), "flip_count": pair["flip_count"],
                "target": target_name,
                "target_workload_id": protocol[f"{target_name}_workload_id"],
                "first_pair_receipt_sha256": digest,
                "first_pair_cnf_xor_calls": pair["first_pair_combined_calls"],
                "first_pair_root_count": first["root_count"],
                "target_branches": branches,
                "target_v_root_count": sum(len(b["v_coords"]) for b in branches),
                "target_field_api_entries": sum(b["field_api_entries"]
                                                for b in branches),
                "status": "TARGET_ROOT_CONTINUATION_COMPLETE",
            })
    previous = load(Q1492 / "result.json")
    old_selected = {(r["phase"], r["input"]): r for r in previous["rows"]
                    if r["input"] == "selected"}
    for row in rows:
        if row["target"] == "selected":
            old = old_selected[(row["phase"], "selected")]
            assert row["target_v_root_count"] == old["target_total_v_roots"]
            assert row["target_field_api_entries"] == old[
                "target_field_api_entries"]
            assert [b["v_coords"] for b in row["target_branches"]] == [
                b["v_coords"] for b in old["target_branches"]]
    summary = {}
    for target_name in ("selected", "holdout"):
        for count in protocol["flip_counts"]:
            sub = [r for r in rows if r["target"] == target_name and
                   r["flip_count"] == count]
            assert len(sub) == 8
            survivors = sum(bool(r["target_v_root_count"]) for r in sub)
            cnf = sum(r["first_pair_cnf_xor_calls"] for r in sub)
            field = sum(r["target_field_api_entries"] for r in sub)
            summary[f"{target_name}_{count}"] = {
                "first_pairs": len(sub),
                "pairs_with_first_roots": sum(bool(r["first_pair_root_count"])
                                              for r in sub),
                "pairs_with_target_v_roots": survivors,
                "first_pair_cnf_xor_calls": cnf,
                "target_field_api_entries": field,
                "first_pair_cnf_xor_calls_per_survivor":
                    cnf / survivors if survivors else None,
                "target_field_api_entries_per_survivor":
                    field / survivors if survivors else None,
            }
    save(HERE / "result.json", {
        "proposal_id": "Q1493", "candidate_id": None, "run_id": None,
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
    print("Q1493", summary)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run"):
        raise SystemExit("usage: paired.py {freeze|run}")
    globals()[sys.argv[1]]()
