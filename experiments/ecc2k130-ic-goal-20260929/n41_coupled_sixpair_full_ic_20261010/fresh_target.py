#!/usr/bin/env sage -python
"""Freeze one independent N41 subgroup point outside the setup stream."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
OUT = HERE / "fresh"
R = 549756390943
SEED = "n41-coupled-sixpair-independent-target-20261010-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def main():
    workload = json.loads((HERE / "workload.json").read_text())
    factor_audit = json.loads((HERE / "sage_audit.json").read_text())
    assert factor_audit["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    generator = curve(decode(workload["generator"][0]), decode(workload["generator"][1]))
    scalar = int.from_bytes(hashlib.sha256(SEED.encode()).digest(), "big") % R
    assert scalar != 0
    target = scalar * generator
    encoded = [encode(target[0]), encode(target[1])]
    assert encoded != workload["public_target_q"]
    assert all(encoded != item["point"] for item in workload["setup_targets"])
    assert R * target == curve(0)
    OUT.mkdir(exist_ok=False)
    save(OUT / "fixture.json", {
        "status": "FROZEN_FRESH_TARGET_FIXTURE", "seed": SEED,
        "scalar_kept_out_of_worker_input": int(scalar),
        "target": encoded, "generator": workload["generator"],
        "subgroup_order": R, "excluded_from_online_intervals": True,
        "source_sha256": {"script": sha(__file__),
                          "workload": sha(HERE / "workload.json"),
                          "sage_runtime": sha(HERE / "sage_runtime_info.json")},
    })
    (OUT / "rho_input.txt").write_text(" ".join(str(value) for value in [
        *encoded, *workload["generator"], R,
        workload["frobenius_eigenvalue_mod_r"], 202610101400]) + "\n")
    save(OUT / "protocol.json", {
        "status": "FROZEN_BEFORE_FRESH_ONE_TARGET_PAIR",
        "curve_id": "EC1N41Ckb1h023d9a38bbf7",
        "target": encoded, "target_count": 1, "workers_ic": 1, "workers_rho": 1,
        "ic_max_accepted_probes": 20000000, "ic_online_cap_seconds": 20,
        "rho_online_cap_seconds": 120, "rho_step_cap": 20000000,
        "parent_cap_seconds": 130, "rss_cap_bytes": 4 * 1024**3,
        "ic_rng_seed": 202610101357, "rho_walk_seed": 202610101400,
        "source_sha256": {name: sha(path) for name, path in {
            "fixture": OUT / "fixture.json", "rho_input": OUT / "rho_input.txt",
            "atoms": HERE / "online_atoms.txt", "logs": HERE / "online_logs.txt",
            "ic_worker_source": HERE / "online_worker.cpp",
            "ic_worker_binary": HERE / "online_worker",
            "rho_source": HERE.parent / "n41_signed_frobenius_rho_r3.cpp",
            "rho_binary": HERE / "rho_r3",
            "factor_logs": HERE / "factor_logs.json",
            "factor_audit": HERE / "sage_audit.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    })
    print(json.dumps({"status": "FROZEN_BEFORE_FRESH_ONE_TARGET_PAIR",
                      "target": encoded}))


if __name__ == "__main__":
    main()
