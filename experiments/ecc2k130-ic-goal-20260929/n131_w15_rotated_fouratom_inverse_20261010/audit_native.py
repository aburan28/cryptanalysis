#!/usr/bin/env sage -python
"""Independent field replay of the native rotated product-space GCD hits."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combine(limbs):
    assert len(limbs) == 3
    return int(limbs[0]) + (int(limbs[1]) << 64) + (int(limbs[2]) << 128)


freeze = json.loads((HERE / "audit_protocol.json").read_text())
assert freeze["status"] == "FROZEN_BEFORE_INDEPENDENT_NATIVE_SAGE_AUDIT"
assert freeze["sha256"] == {name: sha(HERE / name) for name in freeze["sha256"]}
assert not (HERE / "native_audit.json").exists()
control = json.loads((HERE / "control_result.json").read_text())
resultant = json.loads((HERE / "resultant.json").read_text())
native_protocol = json.loads((HERE / "native_protocol.json").read_text())
terms = resultant["terms"]
results = []
for label,n,d in (("n41",41,6),("n131",131,15)):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**41+t**3+1 if n == 41 else t**131+t**13+t**2+t+1
    field = GF(2**n, "t", modulus=modulus)

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(n)]))

    def encode(value):
        return sum(int(bit) << i for i,bit in enumerate(value.polynomial().list()))

    def evaluate(a,b,p,q,z):
        ap,bp,pp,qp,zp = ([base**i for i in range(9)] for base in (a,b,p,q,z))
        return sum((ap[ea]*bp[eb]*pp[ep]*qp[eq]*zp[ez]
                    for ea,eb,ep,eq,ez in terms), field.zero())

    case = control[label]
    known_p,known_q = map(decode, case["rotated_pair_products"])
    for kind in ("positive", "field_control"):
        name = f"{label}_{kind}"
        receipt = json.loads((HERE / f"receipt_{name}.json").read_text())
        native = json.loads((HERE / f"native_{name}.json").read_text())
        assert receipt["status"] == "PROCESS_COMPLETE" and receipt["exit_code"] == 0
        assert receipt["result_sha256"] == sha(HERE / f"native_{name}.json")
        assert receipt["protocol_sha256"] == sha(HERE / "native_protocol.json")
        assert native["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        assert native["field_degree"] == n and native["source_dimension"] == d
        assert native["rotations"] == case["pair_rotations"]
        assert native["processed_product_states"] == native["total_product_states"] == 1 << (d-1)
        assert native["query_ns"] <= native_protocol["native_query_cap_seconds_each"]*10**9
        assert native["peak_rss_bytes"] <= native_protocol["rss_cap_bytes"]
        assert combine(native["seed_sum"]) == case["seed_mask"] << 1
        assert [combine(x) for x in native["rotated_seeds"]] == case["rotated_seed_coordinates"]
        expected_z = case["four_atom_reciprocal_output"] if kind == "positive" else case["independent_field_control_z"]
        assert combine(native["output_z"]) == expected_z
        a,b = map(decode, case["rotated_seed_coordinates"])
        z = decode(expected_z)
        validated = []
        for hit in native["hits"]:
            p = decode(combine(hit["p"]))
            coefficients = [decode(combine(value)) for value in hit["gcd_coefficients"]]
            assert hit["gcd_degree"] == len(coefficients)-1 and coefficients[-1] != 0
            assert hit["gcd_degree"] == 1
            root = coefficients[0]/coefficients[1]
            assert evaluate(a,b,p,root,z) == 0
            validated.append([encode(p),encode(root)])
        if kind == "positive":
            assert validated == [[encode(known_p),encode(known_q)]]
        else:
            assert validated == []
            assert evaluate(a,b,known_p,known_q,z) != 0
        results.append({"case": name, "processed_first_products": native["processed_product_states"],
                        "algebraic_hits": len(validated), "verified_product_roots": validated,
                        "query_ns": native["query_ns"], "peak_rss_bytes": native["peak_rss_bytes"]})

record = {"status": "PASS_INDEPENDENT_NATIVE_ROTATED_GCD_SAGE_REPLAY",
          "cases": results, "protocol_sha256": sha(HERE / "audit_protocol.json")}
with (HERE / "native_audit.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
print({"status": record["status"], "cases": [(x["case"],x["algebraic_hits"]) for x in results]})
