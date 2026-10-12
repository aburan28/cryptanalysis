#!/usr/bin/env python3
"""Confirm Q1480's archived pre-search mask-schedule incompatibility."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert drive["proposal_id"] == frozen["proposal_id"] == "Q1480"
    assert [(r["input"], r["phase"], r["status"]) for r in drive["rows"]] == [
        (name, phase, "CHECKPOINT_TERMINATED" if phase == 0 else "PRODUCER_FAILURE")
        for name in ("selected", "holdout") for phase in (0, 1)]
    assert len(frozen["phase_schedule"]["1"]["flip_ids"]) == 250
    source = Path("/Volumes/SSD990/llm/tmp/q1479_distinct_build/n83/src/wdsat.c")
    assert sha(source) == json.loads((HERE.parent /
        "q20261011_n83_distinct_roots/build_receipt.json").read_text())[
            "patched_wdsat_c_sha256"]
    text = source.read_text()
    assert "static const int_t q1472_phase_1[] = {2140};" in text
    assert "Q1473_BAD_SELECTOR_ORDER" in text
    for name in ("selected", "holdout"):
        folder = HERE / "runs" / f"{name}_phase1"
        row = json.loads((folder / "receipt.json").read_text())
        assert row["status"] == "PRODUCER_FAILURE" and not row["search_started"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        log = (folder / "solver.stderr.txt").read_text()
        assert "Q1472_PHASE 1 1\nQ1473_BAD_SELECTOR_ORDER\n" in log
    print("PASS Q1480 preflight", "intended 250 flips; binary phase 1 flips 2140")


if __name__ == "__main__":
    main()
