#!/usr/bin/env sage -python
"""Independent Sage replay of the warm worker's held-out DLP result."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "online_protocol.json").read_text())
    run = json.loads((HERE / "online_run.json").read_text())
    native = json.loads((HERE / "online_native.json").read_text())
    hit = json.loads((HERE / "online_hit.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    factors = json.loads((HERE / "factor_logs.json").read_text())
    assert run["source_sha256"]["native_result"] == sha(HERE / "online_native.json")
    assert run["source_sha256"]["hit"] == sha(HERE / "online_hit.json")
    assert run["online_ns"] == native["online_ns"]
    assert sum(native["exclusive_phase_ns"].values()) == native["online_ns"]
    assert hit["status"] == "NATIVE_SCALAR_VERIFIED"
    assert hit["raw_sum"] == protocol["target"] == workload["public_target_q"]
    assert native["status"] == "VERIFIED_SCALAR"
    assert native["recovered_scalar"] == hit["recovered_scalar"]
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

    generator = point(workload["generator"])
    target = point(protocol["target"])
    zero = curve(0)
    assert R * generator == zero and R * target == zero
    lam = workload["frobenius_eigenvalue_mod_r"]
    assert lam * generator == curve(generator[0]**2, generator[1]**2)
    atom_map = {(a["block"], a["mask"], a["sign"]): a for a in workload["atoms"]}
    selected = []
    vector = [0] * 26
    for slot, (mask, sign, column) in enumerate(
        zip(hit["masks"], hit["signs"], hit["columns"])
    ):
        atom = atom_map[(slot // 2, mask, sign)]
        assert atom["column"] == column
        p = point(atom["point"])
        representative = point(workload["representatives"][column])
        # The frozen bootstrap and the setup audit establish the coefficient;
        # check the resulting equality independently in this online replay.
        assert atom["coefficient_mod_r"] * representative == p
        selected.append(p)
        vector[column] = (vector[column] + atom["coefficient_mod_r"]) % R
    assert sum(selected, zero) == target
    scalar = sum(a * b for a, b in zip(vector, factors["logs_mod_r"])) % R
    assert scalar == native["recovered_scalar"]
    assert scalar * generator == target
    receipt = {
        "status": "PASS_INDEPENDENT_SAGE_WARM_ONE_TARGET_DLP",
        "curve_id": workload["curve_id"], "target": protocol["target"],
        "recovered_scalar": int(scalar), "online_ns": native["online_ns"],
        "exclusive_phase_ns": native["exclusive_phase_ns"],
        "verified_relation_points": 12, "factor_base_points_B": workload["actual_factor_base_points_B"],
        "folded_columns_K": workload["folded_columns_K"],
        "scalar_group_replay_verified": True,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "online_protocol.json",
            "run": HERE / "online_run.json", "native": HERE / "online_native.json",
            "hit": HERE / "online_hit.json", "workload": HERE / "workload.json",
            "factors": HERE / "factor_logs.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "online_sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "scalar": int(scalar),
                      "online_ns": receipt["online_ns"]}))


if __name__ == "__main__":
    main()
