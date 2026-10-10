#!/usr/bin/env python3
"""Freeze warm target inputs and executable hashes before the online run."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_upper_xor_projection_20261010/w6_input.txt"
HELPER = HERE.parent / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    workload = json.loads((HERE / "workload.json").read_text())
    factors = json.loads((HERE / "factor_logs.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    assert factors["curve_id"] == workload["curve_id"]
    assert len(factors["logs_mod_r"]) == 26
    lines = SOURCE.read_text().splitlines()
    assert len(lines) == 391
    rendered = [f"0 0 {R} 6"]
    offset = 1
    for block in range(6):
        header = lines[offset]
        assert header == f"{block * 5} 64"
        rendered.append(header)
        offset += 1
        for index in range(64):
            source = [int(value) for value in lines[offset].split()]
            assert len(source) == 5
            atom = workload["atoms"][block * 64 + index]
            assert atom["block"] == block
            assert atom["index"] == index
            assert source == [*atom["point"], atom["mask"], atom["sign"], atom["column"]]
            rendered.append(lines[offset] + f" {atom['coefficient_mod_r']}")
            offset += 1
    assert offset == len(lines)
    (HERE / "online_atoms.txt").write_text("\n".join(rendered) + "\n")
    (HERE / "online_logs.txt").write_text(
        "\n".join(str(value) for value in factors["logs_mod_r"]) + "\n")
    protocol = {
        "status": "FROZEN_BEFORE_WARM_ONE_TARGET_RUN", "curve_id": workload["curve_id"],
        "target": workload["public_target_q"], "target_count": 1, "workers": 1,
        "subgroup_order": R, "max_accepted_probes": 20000000,
        "native_online_cap_seconds": 20, "parent_process_cap_seconds": 30,
        "rss_cap_bytes": 4 * 1024**3, "rng_seed": 202610100743,
        "online_boundary": "after warmed index and logs, from first target-dependent subgroup validation to native scalar multiplication replay",
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "atoms": HERE / "online_atoms.txt",
            "logs": HERE / "online_logs.txt", "worker_source": HERE / "online_worker.cpp",
            "worker_binary": HERE / "online_worker", "helper": HELPER,
            "workload": HERE / "workload.json", "factor_logs": HERE / "factor_logs.json",
            "sage_audit": HERE / "sage_audit.json", "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "online_protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"], "target": protocol["target"]}))


if __name__ == "__main__":
    main()
