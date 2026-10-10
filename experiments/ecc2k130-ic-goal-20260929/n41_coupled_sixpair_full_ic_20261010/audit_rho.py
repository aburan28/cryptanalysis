#!/usr/bin/env sage -python
"""Independently verify the paired rho scalar on the held-out point."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "rho_protocol.json").read_text())
    run = json.loads((HERE / "rho_run.json").read_text())
    rho = json.loads((HERE / "rho_native.json").read_text())
    ic = json.loads((HERE / "online_sage_audit.json").read_text())
    assert run["source_sha256"]["native"] == sha(HERE / "rho_native.json")
    assert rho["status"] == "VERIFIED_ONE_TARGET_RHO"
    assert rho["target"] == protocol["target"] == ic["target"]
    assert rho["generator"] == protocol["generator"]
    assert rho["subgroup_order"] == R
    assert rho["recovered_scalar"] == ic["recovered_scalar"]
    assert sum(rho["exclusive_stage_phase_ns"].values()) == rho["rho_online_wall_ns"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def point(pair):
        return curve(*[field(ring([(int(value) >> i) & 1 for i in range(41)]))
                       for value in pair])

    generator = point(protocol["generator"])
    target = point(protocol["target"])
    assert R * generator == curve(0)
    assert R * target == curve(0)
    assert rho["recovered_scalar"] * generator == target
    receipt = {
        "status": "PASS_INDEPENDENT_SAGE_SAME_POINT_RHO",
        "curve_id": protocol["curve_id"], "target": protocol["target"],
        "recovered_scalar": rho["recovered_scalar"],
        "rho_online_ns": rho["rho_online_wall_ns"],
        "walk_steps": rho["walk_steps"], "scalar_group_replay_verified": True,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "rho_protocol.json",
            "run": HERE / "rho_run.json", "native": HERE / "rho_native.json",
            "ic_audit": HERE / "online_sage_audit.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "rho_sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "scalar": receipt["recovered_scalar"]}))


if __name__ == "__main__":
    main()
