#!/usr/bin/env python3
"""Read-only Q1507 identity, capped-work and exact-base replay validation."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BASE_MANIFEST = PARENT / "bases/n83_weight5_full_orbits.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol = read(HERE / "protocol.json")
    build = read(HERE / "build_receipt.json")
    result = read(HERE / "result.json")
    continuation = read(HERE / "continuation_result.json")
    analysis = read(HERE / "analysis.json")
    assert sha(Q1488 / "freeze.json") == protocol["q1488_freeze_sha256"]
    assert sha(Q1488 / "build_receipt.json") == protocol["q1488_build_receipt_sha256"]
    assert sha(HERE / "build.py") == build["source_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    patched = Path(build["patched_source_path"])
    if patched.exists():
        assert sha(patched) == build["patched_source_sha256"]
    order_manifest = PARENT / "q20261011_wdsat_order/order_manifest.json"
    assert sha(order_manifest) == protocol["order_manifest_sha256"] == build["order_manifest_sha256"]
    assert sha(HERE / "run.py") == result["source_sha256"]
    assert sha(HERE / "continuation.py") == continuation["source_sha256"]
    assert sha(HERE / "analyze.py") == analysis["source_sha256"]
    assert sha(HERE / "protocol.json") == result["protocol_sha256"] == continuation["protocol_sha256"] == analysis["protocol_sha256"]
    assert sha(HERE / "result.json") == analysis["result_sha256"]
    assert sha(HERE / "continuation_result.json") == analysis["continuation_result_sha256"]
    assert sha(HERE / "build_receipt.json") == analysis["build_receipt_sha256"]
    assert sha(BASE) == analysis["factor_base_enumerated_set_sha256"]
    assert read(BASE_MANIFEST)["factor_base"]["actual_usable_points_B_before_folding"] == protocol["factor_base_actual_B"]
    assert protocol["candidate_id"] is None and analysis["complete_n131_solve_work_log2"] is None
    assert len(result["rows"]) == 18 and len(continuation["rows"]) == 4
    source_order = read(order_manifest)["cells"]["n83"]
    mids, leaves, selectors = (source_order[key] for key in
                              ("pair_mid_first_ids", "interleaved_leaves_priority",
                               "selector_priority"))
    assert build["priorities"]["q1507_target_mid_first"] == selectors + mids[83:] + mids[:83]
    assert build["priorities"]["q1507_target_leaf_first"] == (
        selectors + [leaves[4 * i + j] for i in range(83) for j in (2, 3)] +
        [leaves[4 * i + j] for i in range(83) for j in (0, 1)])
    for item in result["rows"]:
        folder = HERE / "runs" / f"{item['input']}_phase{item['phase']}_{item['mode']}"
        receipt = folder / "receipt.json"
        assert sha(receipt) == item["receipt_sha256"]
        row = read(receipt)
        log = (folder / "solver.stderr.txt").read_text()
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert row["search_started"] and row["order_marker_ok"] and row["mask_marker_ok"]
        assert row["child_peak_rss_bytes_darwin"] > 0
        if row["status"] == "FIRST_PAIR_TERMINATED":
            marker = re.findall(r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$", log, re.M)
            assert len(marker) == 1
            assert row["first_pair_bits"] == marker[0][3]
            assert row["first_pair_combined_calls"] == int(marker[0][1]) + int(marker[0][2])
        else:
            assert row["status"] == "BRANCH_CAP_SEARCH_STARTED"
            assert "Q1464_BRANCH_CAP 1048576" in log
            assert row["first_pair_bits"] is None
    for item in continuation["rows"]:
        folder = HERE / "continuation" / f"{item['input']}_{item['mode']}"
        receipt = folder / "receipt.json"
        assert sha(receipt) == item["receipt_sha256"]
        row = read(receipt)
        assert row["status"] == "BRANCH_CAP_SEARCH_STARTED"
        assert row["last_work_checkpoint"][0] == 1048576
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
    assert analysis["full_continuation_identical_cap_work_between_leaf_orders"]
    for label in ("selected", "holdout"):
        sub = [r for r in analysis["full_continuation_rows"] if r["input"] == label]
        assert len(sub) == 2 and sub[0]["last_work_checkpoint"] == sub[1]["last_work_checkpoint"]
        assert all(r["distinct_first_pairs_at_cap"] == 1 for r in sub)
    spec = importlib.util.spec_from_file_location("q1507_analyze", HERE / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = BASE.read_bytes()
    keys = {int.from_bytes(raw[i:i + 21], "little") for i in range(0, len(raw), 21)}
    onb = module.CountedOnb(83)
    curve, orbit = module.Curve(onb), module.OrbitKey(onb)
    order = int(read(BASE_MANIFEST)["curve"]["subgroup_order"])
    for row in analysis["rows"]:
        if row["pair_replay"] is None:
            continue
        receipt = read(HERE / "runs" /
                       f"{row['input']}_phase{row['phase']}_{row['mode']}" /
                       "receipt.json")
        replay = module.replay(receipt["first_pair_bits"], onb, curve, orbit, keys, order)
        assert replay == row["pair_replay"]
    assert all(r["pair_replay"]["both_exact_base_usable"]
               for r in analysis["rows"] if r["phase"] == 2 and
               r["mode"] == "q1507_target_leaf_first")
    print("PASS Q1507 ordinary N83 first-pair and complete-cap replay")


if __name__ == "__main__":
    main()
