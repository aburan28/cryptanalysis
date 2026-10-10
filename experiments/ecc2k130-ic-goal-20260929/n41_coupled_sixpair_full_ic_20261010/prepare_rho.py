#!/usr/bin/env python3
"""Freeze same-point one-worker signed-Frobenius rho input and source."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RHO_SOURCE = HERE.parent / "n41_signed_frobenius_rho_r3.cpp"
RHO_HELPER = HERE.parent.parent / "koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    workload = json.loads((HERE / "workload.json").read_text())
    ic = json.loads((HERE / "online_sage_audit.json").read_text())
    assert ic["status"] == "PASS_INDEPENDENT_SAGE_WARM_ONE_TARGET_DLP"
    assert ic["target"] == workload["public_target_q"]
    seed = 202610100743
    target, generator = workload["public_target_q"], workload["generator"]
    fields = [*target, *generator, workload["subgroup_order"],
              workload["frobenius_eigenvalue_mod_r"], seed]
    input_path = HERE / "rho_input.txt"
    input_path.write_text(" ".join(str(value) for value in fields) + "\n")
    protocol = {
        "status": "FROZEN_BEFORE_SAME_POINT_RHO", "curve_id": workload["curve_id"],
        "target": target, "generator": generator, "target_count": 1,
        "workers": 1, "walk_policy": "signed_Frobenius_16_jump_random_walk",
        "collision_policy": "exact_canonical_point_collision",
        "seed": seed, "step_cap": 20000000, "online_wall_cap_seconds": 120,
        "rss_cap_bytes": 4 * 1024**3,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "input": input_path, "source": RHO_SOURCE,
            "helper": RHO_HELPER, "binary": HERE / "rho_r3",
            "workload": HERE / "workload.json", "ic_audit": HERE / "online_sage_audit.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "rho_protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"], "target": target}))


if __name__ == "__main__":
    main()
