#!/usr/bin/env python3
"""Read-only audit of every raw arm in the prospective sparse-tau3 panel."""

import hashlib
import json
from pathlib import Path
import subprocess

from check_tau3_atlas_panel import fields
from check_tau3_sparse_panel import MODES, ORDERS, pair_result


ROOT = Path(__file__).resolve().parent
SPARSE_PANEL_COMMIT = "d952227e91e67a50516eb63fbe56a09ff6aeb7f2"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sparse_source_sha256(path):
    repository = ROOT.parents[1]
    subprocess.run(["git", "merge-base", "--is-ancestor", SPARSE_PANEL_COMMIT, "HEAD"],
                   cwd=repository, check=True, capture_output=True)
    content = subprocess.check_output(["git", "show", f"{SPARSE_PANEL_COMMIT}:{path}"],
                                      cwd=repository)
    return hashlib.sha256(content).hexdigest()


def audit():
    panel = json.loads((ROOT / "tau3-sparse-panel.json").read_text())
    fixture_path = ROOT / "tau3-sparse-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert panel["status"] == "prospective_sparse_operation_gate"
    assert panel["protocol"] == "TAU3_SPARSE_HOT.md"
    assert fixture["status"] == "frozen_tau3_sparse_disjoint_fixture"
    assert panel["runner_sha256"] == sha256(ROOT / "check_tau3_sparse_panel.py")
    assert panel["arm_runner_sha256"] == sha256(ROOT / "check_tau3_atlas_panel.py")
    assert panel["fixture_sha256"] == sha256(fixture_path)
    assert panel["bench_source_sha256"] == sparse_source_sha256(
        "experiments/prime-j0-cost-aware-chain/bench.c")
    assert panel["ec_tau_source_sha256"] == sparse_source_sha256("src/ec_tau.c")
    assert panel["atlas_header_sha256"] == sha256(
        ROOT.parents[1] / "src/generated/tau3_atlas.h")
    assert panel["sparse_header_sha256"] == sha256(
        ROOT.parents[1] / "src/generated/tau3_sparse.h")
    assert panel["isolated_receipt"] is None and panel["cpu_timing_claim"] is None
    assert len(fixture["cases"]) == 8
    assert len(panel["rows"]) == 24 and len(panel["pairs"]) == 8
    for index, (case, pair) in enumerate(zip(fixture["cases"], panel["pairs"])):
        rows = panel["rows"][3 * index:3 * index + 3]
        assert [row["mode"] for row in rows] == list(ORDERS[index % len(ORDERS)])
        assert all(row["case_id"] == case["id"] for row in rows)
        arms = {row["mode"]: row for row in rows}
        assert set(arms) == set(MODES)
        for row in rows:
            if row["exit_code"] == 0 and not row["timed_out"] and "parse_error" not in row:
                assert row["fields"] == fields(row["stdout"])
                f = row["fields"]
                verified = (f.get("verified") == "1"
                            and f.get("curve") == case["curve"]["name"]
                            and f.get("point_index") == str(case["point_index"])
                            and f.get("count") == "4096"
                            and f.get("input_digest") == case["input_digest"]
                            and f.get("output_digest") == case["expected_output_digest"]
                            and f.get("base_x") == case["base_x"]
                            and f.get("base_y") == case["base_y"])
            else:
                verified = False
            assert row["verified"] == verified
        assert pair == pair_result(case, arms)
    gates = sum(pair["gate_pass"] for pair in panel["pairs"])
    print(f"tau3 sparse panel audit: PASS (24 raw arms, {gates}/8 operation gates)")


if __name__ == "__main__":
    audit()
