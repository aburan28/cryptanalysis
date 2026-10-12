#!/usr/bin/env python3
"""Audit sampled N83 S3 leaves against the enumerated usable base."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
Q1491 = PARENT / "q20261012_n83_mask_density"
Q1493 = PARENT / "q20261012_n83_paired_target_roots"
BASE = PARENT / "bases/n83_weight5_full_orbits.json"
KEYS = PARENT / "bases/n83_weight5_full_point_orbits.bin"
ORBIT_SOURCE = ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q20261011_operation_account"))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ORBIT_SOURCE.parent))
from counted_onb import CountedOnb  # noqa: E402
from curves import Curve  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = load(HERE / "protocol.json")
    base = load(BASE)
    assert base["curve"]["curve_id"] == protocol["curve_id"]
    assert base["factor_base"]["actual_usable_points_B_before_folding"] == protocol[
        "factor_base_actual_B"]
    assert base["factor_base"]["signed_frobenius_columns"] == protocol[
        "factor_base_folded_columns_K"]
    assert base["factor_base"]["enumerated_set_sha256"] == sha(KEYS)
    drive = load(Q1491 / "drive_receipt.json")
    selected = [r for r in drive["rows"] if r["input"] == "selected"]
    assert len(selected) == 40
    save(HERE / "freeze.json", {
        "proposal_id": "Q1494", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "audit.py", "validate.py")},
        "q1491_drive_sha256": sha(Q1491 / "drive_receipt.json"),
        "q1493_result_sha256": sha(Q1493 / "result.json"),
        "base_receipt_sha256": sha(BASE), "base_key_file_sha256": sha(KEYS),
        "orbit_source_sha256": sha(ORBIT_SOURCE),
        "pair_receipts": {str(r["phase"]): r["receipt_sha256"]
                          for r in selected},
    })
    print("Q1494 frozen", sha(HERE / "freeze.json")[:12])


def run() -> None:
    assert not (HERE / "result.json").exists()
    protocol, frozen = load(HERE / "protocol.json"), load(HERE / "freeze.json")
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert sha(KEYS) == frozen["base_key_file_sha256"]
    assert sha(BASE) == frozen["base_receipt_sha256"]
    assert sha(Q1493 / "result.json") == frozen["q1493_result_sha256"]
    raw_keys = KEYS.read_bytes()
    assert len(raw_keys) == 21 * protocol["factor_base_folded_columns_K"]
    keys = {int.from_bytes(raw_keys[i:i + 21], "little")
            for i in range(0, len(raw_keys), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = CountedOnb(83)
    curve = Curve(onb)
    orbit = OrbitKey(onb)
    subgroup_order = int(load(BASE)["curve"]["subgroup_order"])
    paired = load(Q1493 / "result.json")
    survival = {(r["target"], r["phase"]): bool(r["target_v_root_count"])
                for r in paired["rows"]}
    rows = []
    for phase, digest in sorted(frozen["pair_receipts"].items(),
                                key=lambda item: int(item[0])):
        path = Q1491 / "runs" / f"selected_phase{phase}" / "receipt.json"
        assert sha(path) == digest
        pair = load(path)
        assert pair["status"] == "FIRST_PAIR_TERMINATED"
        bits = pair["first_pair_bits"]
        leaves = []
        for position in (0, 1):
            leaf_bits = bits[position * 83:(position + 1) * 83]
            coords = int(leaf_bits[::-1], 2)
            onb.reset_counts()
            x = onb.fromCoords(coords)
            raw = curve.pointFromX(x) if x else None
            projected = curve.mul(raw, 4) if raw is not None else None
            key = orbit.canonical(projected)[0] if projected is not None else None
            filter_calls = onb.snapshot_counts()
            onb.reset_counts()
            if projected is not None:
                assert curve.onCurve(projected)
                assert curve.mul(projected, subgroup_order) is None
            replay_calls = onb.snapshot_counts()
            leaves.append({
                "coords": coords, "weight": coords.bit_count(),
                "rational_lift": raw is not None,
                "projected_identity": raw is not None and projected is None,
                "projected_orbit_key": key,
                "exact_base_member": key in keys if key is not None else False,
                "filter_field_api_calls": filter_calls,
                "filter_field_api_entries": sum(filter_calls.values()),
                "subgroup_replay_field_api_calls": replay_calls,
                "subgroup_replay_field_api_entries": sum(
                    replay_calls.values()),
            })
        usable = all(leaf["exact_base_member"] for leaf in leaves)
        rows.append({
            "phase": int(phase), "flip_count": pair["flip_count"],
            "pair_receipt_sha256": digest,
            "first_pair_cnf_xor_calls": pair["first_pair_combined_calls"],
            "leaves": leaves,
            "both_rational": all(leaf["rational_lift"] for leaf in leaves),
            "both_usable": usable,
            "selected_target_v_root": survival[("selected", int(phase))],
            "holdout_target_v_root": survival[("holdout", int(phase))],
            "field_api_entries_for_base_filter": sum(
                leaf["filter_field_api_entries"] for leaf in leaves),
            "field_api_entries_for_subgroup_replay": sum(
                leaf["subgroup_replay_field_api_entries"] for leaf in leaves),
        })
    summary = {}
    for count in (17, 42, 83, 166, 249):
        sub = [r for r in rows if r["flip_count"] == count]
        assert len(sub) == 8
        usable = sum(r["both_usable"] for r in sub)
        cnf = sum(r["first_pair_cnf_xor_calls"] for r in sub)
        field = sum(r["field_api_entries_for_base_filter"] for r in sub)
        summary[str(count)] = {
            "sampled_pairs": len(sub),
            "both_rational": sum(r["both_rational"] for r in sub),
            "both_exact_base_usable": usable,
            "first_pair_cnf_xor_calls": cnf,
            "first_pair_cnf_xor_calls_per_usable_pair":
                cnf / usable if usable else None,
            "base_filter_field_api_entries": field,
            "base_filter_field_api_entries_per_usable_pair":
                field / usable if usable else None,
        }
    save(HERE / "result.json", {
        "proposal_id": "Q1494", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol[
            "factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "rows": rows, "summary": summary,
        "all_usable_match_selected_target_v_root": all(
            r["both_usable"] == r["selected_target_v_root"] for r in rows),
        "all_usable_match_holdout_target_v_root": all(
            r["both_usable"] == r["holdout_target_v_root"] for r in rows),
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })
    print("Q1494", summary)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run"):
        raise SystemExit("usage: audit.py {freeze|run}")
    globals()[sys.argv[1]]()
