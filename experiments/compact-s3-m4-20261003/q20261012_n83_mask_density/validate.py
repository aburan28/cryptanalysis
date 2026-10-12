#!/usr/bin/env python3
"""Verify Q1491 source, masks, attempts, exact roots, and selection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import sweep

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol, frozen, built, drive, analysis = (load(HERE / n) for n in
        ("protocol.json", "freeze.json", "build_receipt.json",
         "drive_receipt.json", "analysis.json"))
    assert protocol["proposal_id"] == frozen["proposal_id"] == "Q1491"
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert frozen["mask_schedule"] == sweep.schedule(protocol)
    assert built["freeze_sha256"] == drive["freeze_sha256"] == sha(
        HERE / "freeze.json")
    assert built["source_sha256"] == sha(HERE / "sweep.py")
    assert sha(Path(built["patched_source_path"])) == built[
        "patched_source_sha256"]
    assert sha(Path(built["binary_path"])) == built["binary_sha256"]
    assert sha(Path(built["patched_source_path"]).parent / "config.h") == built[
        "config_sha256"]
    assert sha(HERE / "drive_receipt.json") == analysis["drive_sha256"]
    assert sha(HERE / "sweep.py") == analysis["analysis_source_sha256"]
    assert len(drive["rows"]) == drive["selected_attempts"] + drive[
        "holdout_attempts"]
    rows = []
    for item in drive["rows"]:
        folder = HERE / "runs" / f"{item['input']}_phase{item['phase']}"
        path = folder / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = load(path)
        assert row["freeze_sha256"] == drive["freeze_sha256"]
        assert row["binary_sha256"] == built["binary_sha256"]
        assert row["phase"] == item["phase"] and row["input"] == item["input"]
        assert row["flip_count"] == frozen["mask_schedule"][str(row["phase"])][
            "flip_count"]
        stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout) == row["stdout_sha256"]
        assert sha(stderr) == row["stderr_sha256"]
        hits = re.findall(r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$",
                          stderr.read_text(), re.M)
        if row["status"] == "FIRST_PAIR_TERMINATED":
            assert row["marker_ok"] and row["search_started"]
            assert len(hits) == 1
            branch, cnf, xor, bits = hits[0]
            assert row["first_pair_branch"] == int(branch)
            assert row["first_pair_cnf_calls"] == int(cnf)
            assert row["first_pair_xor_calls"] == int(xor)
            assert row["first_pair_combined_calls"] == int(cnf) + int(xor)
            assert row["first_pair_bits"] == bits
            row["root_count"] = sweep.replay(row)["root_count"]
        else:
            assert not hits and row["first_pair_bits"] is None
        rows.append(row)
    selected = [r for r in rows if r["input"] == "selected"]
    holdout = [r for r in rows if r["input"] == "holdout"]
    assert len(selected) == len(protocol["flip_counts"]) * protocol[
        "replicas_per_count"]
    summary = sweep.summarize(selected, protocol)
    assert summary == drive["selected_summary"] == analysis["selected_summary"]
    costs = [(v["combined_cnf_xor_calls_per_two_root_pair"], int(k))
             for k, v in summary.items()
             if v["combined_cnf_xor_calls_per_two_root_pair"] is not None]
    assert drive["selected_count"] == analysis["promoted_flip_count"] == (
        min(costs)[1] if costs else None)
    assert len(holdout) == (protocol["replicas_per_count"] if costs else 0)
    assert all(r["flip_count"] == drive["selected_count"] for r in holdout)
    matched = sum(row["first_pair_bits"] is not None and
                  row["first_pair_bits"] == next(
                      r for r in selected if r["phase"] == row["phase"])[
                          "first_pair_bits"] for row in holdout)
    assert analysis["holdout_pair_matches_selected"] == matched
    assert analysis["holdout_summary"] == sweep.summarize(holdout, protocol)
    assert analysis["complete_n131_solve_work_log2"] is None
    print("PASS Q1491", len(selected), len(holdout), drive["selected_count"])


if __name__ == "__main__":
    main()
