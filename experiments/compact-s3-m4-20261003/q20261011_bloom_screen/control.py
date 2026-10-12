#!/usr/bin/env python3
"""Replay the archived Q1401 first-descriptor control with Q1446 Bloom."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_pair_budget_screen"
spec = importlib.util.spec_from_file_location("q1445_runner", PRIOR / "run.py")
assert spec is not None and spec.loader is not None
parent_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_runner)
BASE, BINARY, command = (parent_runner.BASE, parent_runner.BINARY,
                         parent_runner.command)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "control_protocol.json").read_text())
    parent = json.loads((PRIOR / "protocol.json").read_text())
    fixture_path = HERE.parent / "runs/n83_q1401_pair_planted_fixture.json"
    prior_replay_path = HERE.parent / "runs/n83_q1401_pair_planted_independent_replay.json"
    fixture = json.loads(fixture_path.read_text())
    prior_replay = json.loads(prior_replay_path.read_text())
    assert protocol["curve_id"] == fixture["curve_id"]
    assert prior_replay["status"] == "PASS"
    assert protocol["workload_id"] == fixture["workload_id"]
    argv = command(1, parent, {"public_target_onb_hex": fixture[
        "target_onb_coordinate_hex"]})
    argv[5] = "1"
    argv[11] = str(protocol["bloom_bits_per_key"])
    argv[12] = str(protocol["bloom_hashes"])
    result = subprocess.run(argv, capture_output=True, text=True,
                            timeout=protocol["external_wall_seconds"], check=False)
    assert result.returncode == 0, result.stderr
    native = json.loads(result.stdout)
    assert native["exact_hit_keys"] == 1
    assert native["hits"][0]["x_key_hex"] == protocol["expected_x_key_hex"]
    assert native["hits"][0]["query_representative_position"] == 0
    assert native["hits"][0]["table_position"] == 0
    out = HERE / "control.json"
    assert not out.exists()
    out.write_text(json.dumps({
        "status": "PASS",
        "proposal_id": "Q1446",
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "isogeny": "none",
        "control_protocol_sha256": sha(HERE / "control_protocol.json"),
        "fixture_sha256": sha(fixture_path),
        "prior_independent_replay_sha256": sha(prior_replay_path),
        "binary_sha256": sha(BINARY),
        "base_sha256": sha(BASE),
        "source_sha256": sha(Path(__file__)),
        "argv": argv,
        "native": native,
    }, indent=2, sort_keys=True) + "\n")
    print("PASS Q1446 first-descriptor positive control")


if __name__ == "__main__":
    main()
