#!/usr/bin/env sage -python
"""Time a second independent Sage check outside the native online interval."""

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
    workload = json.loads((HERE / "workload.json").read_text())
    factors = json.loads((HERE / "factor_logs.json").read_text())
    hit = json.loads((HERE / "online_hit.json").read_text())
    native = json.loads((HERE / "online_native.json").read_text())
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def point(pair):
        return curve(*[field(ring([(int(value) >> i) & 1 for i in range(41)]))
                       for value in pair])

    generator = point(workload["generator"])
    target = point(workload["public_target_q"])
    atom_map = {(a["block"], a["mask"], a["sign"]): a for a in workload["atoms"]}
    start = time.perf_counter_ns()
    selected = []
    coefficients = [0] * 26
    for slot, (mask, sign, column) in enumerate(
        zip(hit["masks"], hit["signs"], hit["columns"])
    ):
        atom = atom_map[(slot // 2, mask, sign)]
        assert atom["column"] == column
        selected.append(point(atom["point"]))
        coefficients[column] = (coefficients[column] + atom["coefficient_mod_r"]) % R
    assert sum(selected, curve(0)) == target
    relation_end = time.perf_counter_ns()
    scalar = sum(a * b for a, b in zip(coefficients, factors["logs_mod_r"])) % R
    assert scalar == hit["recovered_scalar"] == native["recovered_scalar"]
    assert scalar * generator == target
    replay_end = time.perf_counter_ns()
    receipt = {
        "status": "PASS_SUPPLEMENTAL_TIMED_INDEPENDENT_SAGE_REPLAY",
        "recovered_scalar": int(scalar),
        "relation_check_ns_outside_online": relation_end - start,
        "scalar_recovery_check_ns_outside_online": replay_end - relation_end,
        "total_check_ns_outside_online": replay_end - start,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "workload": HERE / "workload.json",
            "factors": HERE / "factor_logs.json", "hit": HERE / "online_hit.json",
            "native": HERE / "online_native.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "supplemental_replay.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "total_check_ns": receipt["total_check_ns_outside_online"]}))


if __name__ == "__main__":
    main()
