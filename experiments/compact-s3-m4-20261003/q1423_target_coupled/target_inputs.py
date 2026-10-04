"""Reconstruct the exact Q1420 target-preimage order for external roots."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
sys.path.insert(0, str(EXPERIMENT))
sys.path.insert(0, str(EXPERIMENT / "q1419_partial_pin"))

from q1420_root_theory.build_formula import (  # noqa: E402
    CONTROL_PROTOCOL, ORDINARY_PARENT, ROOT)
from run_cell import read_profile  # noqa: E402
from run_probe import sha  # noqa: E402


def target_source(n, cell):
    control = json.loads(CONTROL_PROTOCOL.read_text())
    profile, _, _ = read_profile(control, n)
    if cell == "ordinary":
        source = ORDINARY_PARENT[n]
    else:
        assert cell == "free_mids"
        source = Path(profile["parent_receipt"]["path"])
        if not source.is_absolute():
            source = ROOT / source
    return source


def target_list(n, cell, q1420_workload):
    source = target_source(n, cell)
    assert sha(source) == q1420_workload["parent_receipt_sha256"]
    receipt = json.loads(source.read_text())
    assert receipt["curve_id"] == q1420_workload["curve_id"]
    values = [int(x) for x in receipt["raw_preimage_x_coordinates"]]
    assert values and len(set(values)) == len(values)
    assert all(0 < x < 1 << n for x in values)
    return values


def encode_targets(n, values):
    return (f"Q1423TARGETS1 {n} {len(values)}\n" +
            "".join(f"{x:x}\n" for x in values)).encode("ascii")
