#!/usr/bin/env python3
"""Verify frozen evidence, capped states, and the fixed-sum transfer bound."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    core = read(HERE / "protocol.json")
    base = read(HERE / "baseline_protocol.json")
    assert core["status"] == base["status"] == "FROZEN"
    core_paths = {
        "freeze": HERE / "freeze.py", "solver": HERE / "solve.py",
        "supervisor": HERE / "run_cases.py", "audit": HERE / "audit.py",
        "row": GOAL / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json",
        "input": GOAL / "n131_w18_four_pairs/native_join/native_input.txt",
        "runtime": HERE / "sage_runtime_info.json",
    }
    assert all(core["sha256"][name] == sha(path)
               for name, path in core_paths.items())
    base_paths = {
        "source": HERE / "exact_baseline.py", "audit": HERE / "baseline_audit.py",
        "core_protocol": HERE / "protocol.json", "core_audit": HERE / "audit.json",
        "row": core_paths["row"], "input": core_paths["input"],
        "runtime": core_paths["runtime"],
    }
    assert all(base["sha256"][name] == sha(path)
               for name, path in base_paths.items())
    assert read(HERE / "audit.json")["status"] == "PASS_INDEPENDENT_SAGE_REPLAY"
    assert read(HERE / "baseline_audit.json")["status"] == \
        "PASS_INDEPENDENT_SAGE_BASELINE_REPLAY"
    first = read(HERE / "attempt1_failure.json")
    assert first["status"] == "PRODUCER_FAILURE"
    assert first["protocol_sha256"] == sha(HERE / "protocol_v1.json")
    assert first["solve_source_sha256"] == sha(HERE / "attempt1_sources/solve.py")
    assert first["supervisor_source_sha256"] == sha(HERE / "attempt1_sources/run_cases.py")
    assert first["stdout_sha256"] == sha(HERE / "attempt1_positive/stdout.txt")
    assert first["stderr_sha256"] == sha(HERE / "attempt1_positive/stderr.txt")
    statuses = {}
    for case in ("positive", "negative"):
        folder = HERE / case
        f4 = read(folder / "terminal.json")
        exact = read(folder / "exact_result.json")
        assert f4["case"] == exact["case"] == case
        assert f4["protocol_sha256"] == sha(HERE / "protocol.json")
        assert f4["status"] == "WALL_CAP"
        assert f4["result_sha256"] is None
        assert not (folder / "result.json").exists()
        assert f4["stdout_sha256"] == sha(folder / "stdout.txt")
        assert f4["stderr_sha256"] == sha(folder / "stderr.txt")
        started = read_text_line(folder / "stdout.txt")
        assert started["status"] == "START_GROEBNER"
        assert started["variables"] == 16 and started["equations"] == 17
        assert f4["peak_sampled_family_rss_bytes"] < 4 * 1024**3
        assert exact["baseline_protocol_sha256"] == sha(HERE / "baseline_protocol.json")
        assert exact["online_ns"] == sum(exact[name] for name in
               ("leaf_build_ns", "pair_build_ns", "target_lookup_ns",
                "interval_overhead_ns"))
        assert exact["online_ns"] < 45 * 10**9
        assert exact["peak_self_rss_bytes"] < 4 * 1024**3
        statuses[case] = (f4["status"], exact["status"])
    assert statuses == {"positive": ("WALL_CAP", "VERIFIED_RAW_ROW"),
                        "negative": ("WALL_CAP", "EXACT_DOMAIN_EMPTY")}
    r = 680564733841876926932320129493409985129
    m = 2**19
    support = m*m
    floor = (r-1 + 2*support-1) // (2*support)
    assert floor == 1237940039285380274909257659
    print(json.dumps({"status": "PASS_FROZEN_EVIDENCE", "cases": statuses,
                      "fixed_sum_pair_bound": m,
                      "two_pair_support_bound": support,
                      "uniform_target_50pct_prefix_floor": floor},
                     sort_keys=True))


def read_text_line(path):
    return json.loads(Path(path).read_text().splitlines()[0])


if __name__ == "__main__":
    main()
