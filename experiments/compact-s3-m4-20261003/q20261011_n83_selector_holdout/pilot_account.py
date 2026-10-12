#!/usr/bin/env python3
"""Posthoc fixed-depth cost of two-mask pilot then full solver restart."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1475 = PARENT / "q20261011_n83_polarity_depth"
PILOT = 32768
FULL = 262144


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def work_at(folder: Path, phase: int) -> tuple[dict[int, tuple[int, int]], str]:
    receipt_path = folder / "runs" / f"phase{phase}" / "implementation_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "CHECKPOINT_TERMINATED"
    assert receipt["phase"] == phase
    values = {row[0]: (row[1], row[2]) for row in receipt["work_checkpoints"]}
    assert PILOT in values and FULL in values
    return values, sha(receipt_path)


def main() -> None:
    assert not (HERE / "pilot_analysis.json").exists()
    targets = []
    totals = {kind: {policy: 0 for policy in ("plain", "flip2140",
                                             "pilot_both_then_restart_best")}
              for kind in ("cnf_set_true_calls", "xor_set_true_calls")}
    for label, folder in (("selected_target", Q1475), ("unseen_holdout", HERE)):
        report = json.loads((folder / "analysis.json").read_text())
        phase0, hash0 = work_at(folder, 0)
        phase1, hash1 = work_at(folder, 1)
        point = {"label": label, "workload_id": report["workload_id"],
                 "phase0_impl_receipt_sha256": hash0,
                 "phase1_impl_receipt_sha256": hash1,
                 "analysis_sha256": sha(folder / "analysis.json"),
                 "units": {}}
        for index, name in enumerate(("cnf_set_true_calls", "xor_set_true_calls")):
            p0, p1 = phase0[PILOT][index], phase1[PILOT][index]
            f0, f1 = phase0[FULL][index], phase1[FULL][index]
            winner = 0 if p0 <= p1 else 1
            strategies = {"plain": f0, "flip2140": f1,
                          "pilot_both_then_restart_best": p0 + p1 + (f0 if winner == 0 else f1)}
            point["units"][name] = {
                "pilot_phase0": p0, "pilot_phase1": p1,
                "full_phase0": f0, "full_phase1": f1,
                "pilot_winner": winner,
                "strategies": strategies,
                "pilot_over_plain": strategies["pilot_both_then_restart_best"] / f0}
            for policy, cost in strategies.items():
                totals[name][policy] += cost
        assert point["units"]["cnf_set_true_calls"]["pilot_winner"] == point[
            "units"]["xor_set_true_calls"]["pilot_winner"]
        targets.append(point)
    assert targets[0]["workload_id"] != targets[1]["workload_id"]
    result = {
        "proposal_id": "Q1476", "analysis_kind": "posthoc_two_target_pilot_restart_account",
        "pilot_left_branches": PILOT, "full_left_branches": FULL,
        "targets": targets, "two_target_totals_by_separate_unit": totals,
        "two_target_pilot_over_plain": {
            kind: costs["pilot_both_then_restart_best"] / costs["plain"]
            for kind, costs in totals.items()},
        "assumptions": [
            "both pilot masks run from fresh solver state to the 32768 checkpoint",
            "the chosen mask restarts from fresh solver state and runs to the 262144 checkpoint",
            "counter values are deterministic for the archived binary and input",
            "only these two frozen targets are represented; no distribution or solve-yield inference"],
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "source_sha256": sha(Path(__file__))}
    (HERE / "pilot_analysis.json").write_text(json.dumps(result, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1476 pilot/plain", {k: round(v, 4) for k, v in result[
        "two_target_pilot_over_plain"].items()})


if __name__ == "__main__":
    main()
