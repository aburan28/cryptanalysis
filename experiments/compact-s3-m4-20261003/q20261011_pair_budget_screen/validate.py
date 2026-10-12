#!/usr/bin/env python3
"""Check frozen Q1445 identities, raw outputs, and charged pair-state totals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    from run import fixed_inputs

    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    data = json.loads((HERE / "measurements.json").read_text())
    assert freeze == fixed_inputs()
    assert data["freeze_sha256"] == sha(HERE / "freeze.json")
    assert data["runner_sha256"] == sha(HERE / "run.py")
    for name in ("curve_id", "workload_id", "isogeny", "factor_base_actual_B",
                 "factor_base_folded_columns_K", "factor_base_enumerated_set_sha256"):
        assert data[name] == protocol[name]
    assert data["candidate_id"] is data["run_id"] is None
    assert data["complete_solve_work_log2"] is None
    assert data["degree131_challenge_gap_bits"] is None
    assert [r["table_descriptors"] for r in data["rows"]] == protocol[
        "point_decomposition"]["table_descriptors"]
    for row in data["rows"]:
        table = row["table_descriptors"]
        assert row["stdout_sha256"] == sha(HERE / f"table_{table}.stdout.json")
        assert row["stderr_sha256"] == sha(HERE / f"table_{table}.stderr.txt")
        native = json.loads((HERE / f"table_{table}.stdout.json").read_text())
        assert row["native"] == native
        assert row["status"] == "no_exact_hit_at_cap"
        assert native["exact_hit_keys"] == native["exact_hit_queries"] == 0
        assert native["bloom_positive_queries"] == native["false_positive_queries"]
        assert native["actual_B"] == protocol["factor_base_actual_B"]
        assert row["charged_table_pair_sums"] == table
        assert row["charged_query_representative_pair_sums"] == 65536
        assert row["charged_target_signed_x_complements"] == 2 * 83 * 65536
        assert row["charged_exact_replay_table_pair_sums"] == table
        assert native["peak_rss_bytes"] <= 4096 * 1048576
    print("PASS Q1445 frozen pair-budget screen")


if __name__ == "__main__":
    main()
