#!/usr/bin/env sage -python
"""Independent curve, column, Frobenius, and logarithm replay of the orbit hit."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "n41_coupled_sixpair_full_ic_20261010"
R = 549756390943
LAMBDA = 256851699273


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    native = json.loads((HERE / "native.json").read_text())
    hit = json.loads((HERE / "hit.json").read_text())
    run = json.loads((HERE / "run_receipt.json").read_text())
    workload = json.loads((PRIOR / "workload.json").read_text())
    factors = json.loads((PRIOR / "factor_logs.json").read_text())
    for key, path in protocol["source_paths"].items():
        assert protocol["source_sha256"][key] == digest(path), key
    for name in ("protocol", "hit", "native", "stdout", "stderr"):
        assert run[f"{name}_sha256"] == digest(HERE / (name + ".json" if name in ("protocol", "hit", "native") else name + ".txt"))
    assert native["status"] == "VERIFIED_SCALAR"
    assert native["orbit_size"] == 41 and 0 <= native["orbit_index"] < 41
    assert native["orbit_index"] == hit["orbit_index"]
    assert sum(native["exclusive_phase_ns"].values()) == native["online_ns"]
    assert run["online_ns"] == native["online_ns"]
    assert run["orbit_lookups"] == native["orbit_lookups"]
    assert native["orbit_lookups"] <= 41 * native["accepted_probes"]
    assert hit["original_target"] == protocol["target"] == run["target"]
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

    def encoded(p):
        return [sum(int(bit) << i for i, bit in enumerate(p[j].polynomial().list()))
                for j in (0, 1)]

    def tau(p):
        return curve(p[0]**2, p[1]**2)

    generator = point(workload["generator"])
    target = point(protocol["target"])
    assert R * generator == curve(0) and R * target == curve(0)
    assert tau(generator) == LAMBDA * generator
    orbit = [target]
    for _ in range(40):
        orbit.append(tau(orbit[-1]))
    assert tau(orbit[-1]) == target and len(set(orbit)) == 41
    index = hit["orbit_index"]
    assert encoded(orbit[index]) == hit["rotated_target"]
    assert orbit[index] == pow(LAMBDA, index, R) * target

    atom_map = {(a["block"], a["mask"], a["sign"]): a for a in workload["atoms"]}
    selected = []
    rotated_scalar = 0
    for slot, (mask, sign, column) in enumerate(zip(hit["masks"], hit["signs"], hit["columns"])):
        atom = atom_map[(slot // 2, mask, sign)]
        assert atom["column"] == column
        p = point(atom["point"])
        representative = point(workload["representatives"][column])
        assert atom["coefficient_mod_r"] * representative == p
        selected.append(p)
        rotated_scalar = (rotated_scalar + atom["coefficient_mod_r"] * factors["logs_mod_r"][column]) % R
    assert sum(selected, curve(0)) == orbit[index]
    recovered = (rotated_scalar * pow(LAMBDA, -index, R)) % R
    assert recovered == hit["recovered_scalar"] == native["recovered_scalar"]
    assert recovered * generator == target

    receipt = {
        "status": "PASS_INDEPENDENT_ORBIT_RELATION_AND_SCALAR",
        "target": protocol["target"],
        "orbit_index": index,
        "rotated_scalar": int(rotated_scalar),
        "recovered_scalar": int(recovered),
        "verified_relation_points": len(selected),
        "source_sha256": {name: digest(path) for name, path in {
            "script": __file__, "protocol": HERE / "protocol.json",
            "run_receipt": HERE / "run_receipt.json", "native": HERE / "native.json",
            "hit": HERE / "hit.json", "workload": PRIOR / "workload.json",
            "factor_logs": PRIOR / "factor_logs.json",
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "orbit_index": index,
                      "recovered_scalar": int(recovered)}))


if __name__ == "__main__":
    main()
