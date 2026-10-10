#!/usr/bin/env python3
"""Rerunnable read-only audit of the eight frozen native results."""

from __future__ import annotations

import json

import analysis
import experiment
import verify


def main() -> None:
    frozen = experiment.check_freeze()
    rows = [verify.one(experiment.cell_name(n, kind, window), frozen)
            for n in experiment.DEGREES for kind in experiment.KINDS
            for window in experiment.WINDOWS]
    saved = json.loads((experiment.HERE / "verification.json").read_text())
    assert saved["rows"] == rows
    output = json.loads((experiment.HERE / "analysis.json").read_text())
    assert output["conditional_n131_screen"] == analysis.model()
    assert output["freeze_sha256"] == saved["freeze_sha256"]
    assert output["verification_sha256"] == experiment.sha(
        experiment.HERE / "verification.json")
    sage = experiment.HERE / "sage_replay.json"
    assert output["sage_replay_sha256"] == experiment.sha(sage)
    replay = json.loads(sage.read_text())
    assert [row["cell"] for row in replay["rows"]] == [
        row["cell"] for row in rows]
    for row, checked in zip(rows, replay["rows"]):
        assert row["recorded_hits"] == checked["recorded_hits_checked"]
        if row["cell"].split("_")[1] == "control":
            assert len(checked["hits"]) == 1
            assert checked["hits"][0]["status"] == (
                "verified_four_point_relation")
        else:
            assert checked["hits"] == []
    print(json.dumps({"status": "PASS", "cells": len(rows),
                      "full_scans": sum(row["scanned_masks"] ==
                                        row["eligible_masks"] for row in rows),
                      "conditional_min_root_calls_log2": output[
                          "conditional_n131_screen"][
                              "minimum_s3_root_calls_log2"]}))


if __name__ == "__main__":
    main()
