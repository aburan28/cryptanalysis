#!/usr/bin/env python3
"""Read-only replay of all prospective radix-27 panel rows and gates."""

import hashlib
import json
from pathlib import Path

from check_tau3_atlas_panel import fields
from check_tau3_radix27_panel import MODES, pair_result


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    panel = json.loads((ROOT / "tau3-radix27-panel.json").read_text())
    fixture_path = ROOT / "tau3-radix27-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert panel["status"] == "prospective_radix27_operation_gate"
    assert panel["protocol"] == "TAU3_RADIX27_PATH.md"
    assert fixture["status"] == "frozen_tau3_radix27_disjoint_fixture"
    assert panel["runner_sha256"] == sha256(ROOT / "check_tau3_radix27_panel.py")
    assert panel["arm_runner_sha256"] == sha256(ROOT / "check_tau3_atlas_panel.py")
    assert panel["fixture_sha256"] == sha256(fixture_path)
    assert panel["bench_source_sha256"] == sha256(ROOT / "bench.c")
    assert panel["ec_tau_source_sha256"] == sha256(ROOT.parents[1] / "src/ec_tau.c")
    assert panel["map_header_sha256"] == sha256(ROOT.parents[1] / "src/generated/tau3_radix27.h")
    assert panel["isolated_receipt"] is None and panel["cpu_timing_claim"] is None
    assert len(fixture["cases"]) == 8
    assert len(panel["rows"]) == 16 and len(panel["pairs"]) == 8
    for index, (case, pair) in enumerate(zip(fixture["cases"], panel["pairs"])):
        rows = panel["rows"][2 * index:2 * index + 2]
        order = MODES if index % 2 == 0 else tuple(reversed(MODES))
        assert [row["mode"] for row in rows] == list(order)
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
    print(f"tau3 radix-27 panel audit: PASS (16 raw arms, {gates}/8 operation gates)")


if __name__ == "__main__":
    main()
