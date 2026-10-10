#!/usr/bin/env sage -python
"""Independently derive and replay the held-out scalar from the native witness."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "heldout_protocol.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    factors = json.loads((HERE / "factor_logs.json").read_text())
    hit = json.loads((HERE / "heldout_hit.json").read_text())
    native = json.loads((HERE / "heldout_native.json").read_text())
    assert protocol["source_sha256"]["input"] == sha(HERE / "heldout_input.txt")
    assert protocol["source_sha256"]["join_binary"] == sha(HERE / "join")
    assert protocol["source_sha256"]["factor_logs"] == sha(HERE / "factor_logs.json")
    assert native["status"] == "FOUND_PENDING_SAGE_REPLAY"
    assert hit["status"] == "NATIVE_RELATION_PENDING_SAGE"
    assert hit["raw_sum"] == protocol["target"] == workload["public_target_q"]
    assert len(hit["masks"]) == len(hit["signs"]) == len(hit["columns"]) == 12
    assert len(set(hit["columns"])) == 12
    assert hit["seed_sums"][2] == hit["seed_sums"][3]
    assert hit["seed_sums"][4] == hit["seed_sums"][5]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def point(pair):
        return curve(*[field(ring([(int(value) >> i) & 1 for i in range(41)]))
                       for value in pair])

    t0 = time.perf_counter_ns()
    generator = point(workload["generator"])
    target = point(protocol["target"])
    zero = curve(0)
    assert R * generator == zero and R * target == zero
    atom_map = {(a["block"], a["mask"], a["sign"]): a for a in workload["atoms"]}
    selected = []
    vector = [0] * workload["folded_columns_K"]
    for slot, (mask, sign, column) in enumerate(
        zip(hit["masks"], hit["signs"], hit["columns"])
    ):
        atom = atom_map[(slot // 2, mask, sign)]
        assert atom["column"] == column
        selected.append(point(atom["point"]))
        vector[column] = (vector[column] + atom["coefficient_mod_r"]) % R
    assert sum(selected, zero) == target
    t_relation_check = time.perf_counter_ns()
    scalar = sum(a * b for a, b in zip(vector, factors["logs_mod_r"])) % R
    assert scalar * generator == target
    t_replay = time.perf_counter_ns()
    receipt = {
        "status": "PASS_HELDOUT_SINGLE_TARGET_SCALAR_REPLAY",
        "curve_id": workload["curve_id"], "candidate_id": None,
        "target": protocol["target"], "recovered_scalar": int(scalar),
        "subgroup_order": R, "factor_base_points_B": workload["actual_factor_base_points_B"],
        "folded_columns_K": workload["folded_columns_K"],
        "selected_columns": hit["columns"], "relation_coefficients_mod_r": vector,
        "native_accepted_probes": native["accepted_probes"],
        "native_setup_ns": native["setup_ns"], "native_query_ns": native["online_ns"],
        "separate_sage_relation_check_ns": t_relation_check - t0,
        "separate_sage_scalar_replay_ns": t_replay - t_relation_check,
        "scalar_group_replay_verified": True,
        "timing_note": "Native query and Sage replay were separate processes; their durations are stage diagnostics, not a continuous single-target online wall interval.",
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "heldout_protocol.json",
            "hit": HERE / "heldout_hit.json", "native": HERE / "heldout_native.json",
            "factor_logs": HERE / "factor_logs.json", "workload": HERE / "workload.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "heldout_sage_replay.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "scalar": int(scalar)}))


if __name__ == "__main__":
    main()
