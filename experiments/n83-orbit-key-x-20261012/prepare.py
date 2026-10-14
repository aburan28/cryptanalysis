#!/usr/bin/env python3
"""Freeze the full width-16 canonical x lookup comparison."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEYS = ROOT / "experiments/n83-geometric-width15-16-20261012/d16_gamma82_keys.bin"
FRONTIER = ROOT / "experiments/n83-geometric-width15-16-20261012/frontier.json"
SAGE_REPLAY = ROOT / "experiments/n83-geometric-width15-16-20261012/independent_sage_replay.json"
RUNTIME = HERE / "sage_runtime_info.json"
ORBIT = ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"
REFERENCE = ROOT / "experiments/m5-s3-gate-20261004/build_m5.py"
FIELD = ROOT / "ecc2k130/runner/codegen/field.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    frontier = json.loads(FRONTIER.read_text())
    replay = json.loads(SAGE_REPLAY.read_text())
    assert replay["status"] == "PASS"
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    row = next(row for row in frontier["rows"] if row["dimension"] == 16)
    assert row["canonical_key_sha256"] == sha(KEYS)
    assert row["folded_columns_K"] == 32648
    assert KEYS.stat().st_size == 21 * row["folded_columns_K"]
    sources = [Path(__file__), HERE / "run.py", HERE / "fast_x.py",
               ORBIT, REFERENCE, FIELD]
    protocol = {
        "kind": "n83_full_base_canonical_x_lookup_protocol",
        "proposal_id": "Q2026101248",
        "curve_id": frontier["curve_id"],
        "K": row["folded_columns_K"],
        "B": row["actual_usable_points_B_before_folding"],
        "key_file": str(KEYS.relative_to(ROOT)),
        "key_sha256": sha(KEYS),
        "parent_frontier_sha256": sha(FRONTIER),
        "parent_sage_replay_sha256": sha(SAGE_REPLAY),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in sources},
        "run_order": ["reference", "cycle_table"],
        "timing_tier": "exploratory_local_unisolated",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "frozen", "K": protocol["K"]}))


if __name__ == "__main__":
    main()
