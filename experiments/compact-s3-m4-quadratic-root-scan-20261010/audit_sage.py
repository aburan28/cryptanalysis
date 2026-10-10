#!/usr/bin/env python3
"""Rerunnable read-only checked-Sage replay of recorded relation hits."""

from __future__ import annotations

import json

import experiment
import replay_sage


def main() -> None:
    experiment.check_freeze()
    here = experiment.HERE
    saved = json.loads((here / "sage_replay.json").read_text())
    assert saved["sage_runtime_info_sha256"] == experiment.sha(
        here / "sage_runtime_info.json")
    protocol_path = experiment.OLD / "q1419_partial_pin/protocol.json"
    assert saved["protocol_sha256"] == experiment.sha(protocol_path)
    protocol = json.loads(protocol_path.read_text())
    current = [row for n in experiment.DEGREES
               for row in replay_sage.replay_degree(
                   n, protocol["profiles"][str(n)])]
    assert current == saved["rows"]
    print(json.dumps({"status": "PASS", "cells": len(current),
                      "checked_hits": sum(row["recorded_hits_checked"]
                                          for row in current)}))


if __name__ == "__main__":
    main()
