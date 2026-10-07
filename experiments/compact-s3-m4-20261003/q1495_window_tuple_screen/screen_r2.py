#!/usr/bin/env python3
"""Run the frozen Q1495 theorem with the corrected R2 N53 control."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import screen

HERE = Path(__file__).resolve().parent
RECOVERY = HERE / "recovery_protocol.json"
OUT = HERE / "screen_result_r2.json"


def snapshot() -> dict:
    screen.PROTOCOL = RECOVERY
    screen.CONTROL = HERE / "n53_direct_window_control_r2.json"
    result = screen.snapshot()
    protocol = json.loads(RECOVERY.read_text())
    assert protocol["screen_r2_source_sha256"] == screen.sha(Path(__file__))
    assert protocol["r1_failure_sha256"] == screen.sha(
        HERE / "runs/r1/failure.json")
    result["kind"] = "q1495_exact_fixed_window_tuple_support_screen_r2"
    result["attempt_id"] = "Q1495R2"
    result["screen_r2_source_sha256"] = screen.sha(Path(__file__))
    result["r1_failure_sha256"] = protocol["r1_failure_sha256"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = snapshot()
    if args.check:
        assert json.loads(OUT.read_text()) == result
        print("Q1495 R2 fixed-window support screen PASS (archived)")
    else:
        assert not OUT.exists(), "refusing to replace R2 screen"
        OUT.write_text(json.dumps(result, indent=2,
                                  sort_keys=True) + "\n")
        print("Q1495 R2 fixed-window support screen written")


if __name__ == "__main__":
    main()
