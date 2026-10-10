#!/usr/bin/env python3
"""Freeze the held-out published point and a one-query recovery attempt."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_upper_xor_projection_20261010/w6_input.txt"
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    workload = json.loads((HERE / "workload.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    target = workload["public_target_q"]
    assert all(target != row["point"] for row in workload["setup_targets"])
    lines = SOURCE.read_text().splitlines(keepends=True)
    assert len(lines) == 391
    assert lines[0].split()[:2] == [str(target[0]), str(target[1])]
    input_path = HERE / "heldout_input.txt"
    input_path.write_text(f"{target[0]} {target[1]} {R} 6\n" + "".join(lines[1:]))
    receipt = {
        "status": "FROZEN_BEFORE_HELDOUT_QUERY", "curve_id": workload["curve_id"],
        "target": target, "subgroup_order": R, "target_count": 1, "workers": 1,
        "max_accepted_probes": 20000000, "native_online_cap_seconds": 20,
        "parent_wall_cap_seconds": 30, "rss_cap_bytes": 4 * 1024**3,
        "rng_seed": 202610100743,
        "source_sha256": {name: sha(path) for name, path in {
            "input": input_path, "template": SOURCE, "join_source": HERE / "join.cpp",
            "join_binary": HERE / "join", "workload": HERE / "workload.json",
            "factor_logs": HERE / "factor_logs.json", "sage_audit": HERE / "sage_audit.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "heldout_protocol.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "target": target}))


if __name__ == "__main__":
    main()
