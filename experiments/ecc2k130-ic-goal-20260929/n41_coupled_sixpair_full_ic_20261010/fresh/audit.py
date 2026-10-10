#!/usr/bin/env sage -python
"""Independent Sage replay of the fresh IC witness and paired rho scalar."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    fixture = json.loads((HERE / "fixture.json").read_text())
    ic_run = json.loads((HERE / "ic_run.json").read_text())
    rho_run = json.loads((HERE / "rho_run.json").read_text())
    ic = json.loads((HERE / "ic_native.json").read_text())
    rho = json.loads((HERE / "rho_native.json").read_text())
    hit = json.loads((HERE / "ic_hit.json").read_text())
    workload = json.loads((ROOT / "workload.json").read_text())
    factors = json.loads((ROOT / "factor_logs.json").read_text())
    assert protocol["source_sha256"]["fixture"] == sha(HERE / "fixture.json")
    assert ic_run["source_sha256"]["native"] == sha(HERE / "ic_native.json")
    assert rho_run["source_sha256"]["native"] == sha(HERE / "rho_native.json")
    assert ic["status"] == "VERIFIED_SCALAR"
    assert rho["status"] == "VERIFIED_ONE_TARGET_RHO"
    target_xy = protocol["target"]
    assert target_xy == fixture["target"] == rho["target"] == hit["raw_sum"]
    assert target_xy != workload["public_target_q"]
    assert all(target_xy != item["point"] for item in workload["setup_targets"])
    assert len(set(hit["columns"])) == 12
    assert hit["seed_sums"][2] == hit["seed_sums"][3]
    assert hit["seed_sums"][4] == hit["seed_sums"][5]
    assert sum(ic["exclusive_phase_ns"].values()) == ic["online_ns"]
    assert sum(rho["exclusive_stage_phase_ns"].values()) == rho["rho_online_wall_ns"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def point(pair):
        return curve(*[field(ring([(int(value) >> i) & 1 for i in range(41)]))
                       for value in pair])

    generator = point(workload["generator"])
    target = point(target_xy)
    assert R * generator == curve(0) and R * target == curve(0)
    atom_map = {(a["block"], a["mask"], a["sign"]): a for a in workload["atoms"]}
    start = time.perf_counter_ns()
    selected = []
    coefficients = [0] * 26
    for slot, (mask, sign, column) in enumerate(
        zip(hit["masks"], hit["signs"], hit["columns"])
    ):
        atom = atom_map[(slot // 2, mask, sign)]
        assert atom["column"] == column
        p = point(atom["point"])
        representative = point(workload["representatives"][column])
        assert atom["coefficient_mod_r"] * representative == p
        selected.append(p)
        coefficients[column] = (coefficients[column] + atom["coefficient_mod_r"]) % R
    assert sum(selected, curve(0)) == target
    relation_end = time.perf_counter_ns()
    scalar = sum(a * b for a, b in zip(coefficients, factors["logs_mod_r"])) % R
    assert scalar == ic["recovered_scalar"] == rho["recovered_scalar"]
    assert scalar * generator == target
    assert fixture["scalar_kept_out_of_worker_input"] == scalar
    replay_end = time.perf_counter_ns()
    receipt = {
        "status": "PASS_FRESH_ONE_TARGET_IC_AND_RHO_INDEPENDENT_SAGE",
        "target": target_xy, "recovered_scalar": int(scalar),
        "verified_relation_points": 12,
        "ic_online_ns": ic["online_ns"], "rho_online_ns": rho["rho_online_wall_ns"],
        "relation_check_ns_outside_online": relation_end - start,
        "scalar_recovery_check_ns_outside_online": replay_end - relation_end,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "protocol.json",
            "fixture": HERE / "fixture.json", "ic_run": HERE / "ic_run.json",
            "rho_run": HERE / "rho_run.json", "ic_native": HERE / "ic_native.json",
            "rho_native": HERE / "rho_native.json", "ic_hit": HERE / "ic_hit.json",
            "workload": ROOT / "workload.json", "factor_logs": ROOT / "factor_logs.json",
            "sage_runtime": ROOT / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "scalar": int(scalar),
                      "ic_online_ns": ic["online_ns"],
                      "rho_online_ns": rho["rho_online_wall_ns"]}))


if __name__ == "__main__":
    main()
