#!/usr/bin/env python3
"""Validate Q1446 same-point Bloom screen and the positive control."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    prior = HERE.parent / "q20261011_pair_budget_screen"
    spec = importlib.util.spec_from_file_location("q1445_runner", prior / "run.py")
    assert spec is not None and spec.loader is not None
    parent_runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent_runner)
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    row = json.loads((HERE / "measurement.json").read_text())
    native = json.loads((HERE / "native.stdout.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    assert freeze == {
        "protocol_sha256": sha(HERE / "protocol.json"),
        "parent_protocol_sha256": sha(prior / "protocol.json"),
        "parent_measurements_sha256": sha(prior / "measurements.json"),
        "parent_freeze_sha256": sha(prior / "freeze.json"),
        "binary_sha256": sha(parent_runner.BINARY),
        "base_sha256": sha(parent_runner.BASE),
        "public_target_onb_hex": parent_runner.fixed_inputs()[
            "public_target_onb_hex"],
    }
    assert row["freeze_sha256"] == sha(HERE / "freeze.json")
    assert row["runner_sha256"] == sha(HERE / "run.py")
    assert row["stdout_sha256"] == sha(HERE / "native.stdout.json")
    assert row["stderr_sha256"] == sha(HERE / "native.stderr.txt")
    assert row["native"] == native
    assert row["status"] == "no_exact_hit_at_cap"
    assert native["bloom_bits_per_key"] == 40
    assert native["bloom_hashes"] == 20
    assert native["bloom_positive_queries"] == 0
    assert native["exact_hit_keys"] == 0
    assert native["table_descriptors"] == 8000000
    assert native["query_representatives"] == 65536
    assert native["peak_rss_bytes"] < protocol["limits"]["peak_rss_mib"] * 1048576
    assert row["charged_exact_replay_table_pair_sums"] == 0
    assert row["charged_table_pair_sums"] == 8000000
    assert row["charged_target_signed_x_complements"] == 10878976
    for key in ("curve_id", "workload_id", "isogeny"):
        assert row[key] == protocol[key]
    assert row["candidate_id"] is row["run_id"] is None
    assert row["complete_solve_work_log2"] is None
    assert row["degree131_challenge_gap_bits"] is None
    assert control["status"] == "PASS"
    assert control["control_protocol_sha256"] == sha(HERE / "control_protocol.json")
    assert control["source_sha256"] == sha(HERE / "control.py")
    assert control["native"]["exact_hit_keys"] == 1
    assert control["native"]["hits"][0]["x_key_hex"] == "145376b70583ec992f77"
    print("PASS Q1446 same-point screen and positive control")


if __name__ == "__main__":
    main()
