#!/usr/bin/env python3
"""Exact bilinear-vs-generic N41 six-block circuit preflight."""

import hashlib
import json
from pathlib import Path

import run
from karatsuba_circuit import KaratsubaCircuit

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profile(geometry, target_us, raw_targets, pair_method):
    previous = run.method.pair_product
    run.method.pair_product = pair_method
    try:
        circuit = KaratsubaCircuit(41, [0, 3])
        wires = run.method.build(circuit, geometry, target_us)
        pins = run.control_pins(circuit, wires, geometry, raw_targets)
        return {"variables": circuit.next_var - 1,
                "cnf_clauses": len(circuit.clauses),
                "xor_rows": len(circuit.xors),
                "and_gates": circuit.and_count,
                "primary_variables": wires["primary_variables"],
                "saved_witness_target_flag": pins["target_flag"]}
    finally:
        run.method.pair_product = previous


def generic_product(circuit, z, masks, product_basis, sum_code):
    q = circuit.linear_element(masks, product_basis)
    return circuit.mul(circuit.add(circuit.square(z), z), q)


def check_exact_maps(field, geometry):
    count = 0
    for block in geometry["blocks"][:6]:
        product_basis = block["product_basis"]
        kernel = 0
        for bit in (3, 4, 5):
            kernel ^= product_basis[bit]
        if kernel:
            raise ValueError("fixed-sum product map kernel changed")
        for value in product_basis:
            for bit in range(41):
                x = value << bit
                while x.bit_length() > 41:
                    x ^= ((1 << 41) | (1 << 3) | 1) << (x.bit_length() - 42)
                if x != field.mul(value, 1 << bit):
                    raise ValueError("constant multiplication map disagrees with field")
                count += 1
        for state in block["states"]:
            a, z, s = state["a"], state["z"], block["s"]
            q = 0
            for bit, value in enumerate(product_basis):
                if a & (1 << bit):
                    q ^= value
            az = field.mul(z, z) ^ z
            if field.mul(az, q) != field.mul(s ^ z, s ^ z):
                raise ValueError("saved pair state violates bilinear equation")
            count += 1
    return count


def main():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError(output)
    geometry = json.loads((HERE / "geometry.json").read_text())
    field = run.base.Field(41, [0, 3])
    curve = run.base.Curve(field, 0)
    q, raw, target_us = run.target_data(field, curve, geometry, "control")
    checks = check_exact_maps(field, geometry)
    bilinear = profile(geometry, target_us, raw, run.method.pair_product)
    generic = profile(geometry, target_us, raw, generic_product)
    for key in ("variables", "cnf_clauses", "xor_rows", "and_gates"):
        if bilinear[key] >= generic[key]:
            raise ValueError(f"bilinear formula failed to reduce {key}")
    result = {"status": "PASS_EXACT_BILINEAR_PREFLIGHT",
              "proposal_id": run.PROPOSAL_ID,
              "candidate_id": None, "target_q": q,
              "checked_field_and_state_equalities": checks,
              "bilinear": bilinear, "generic_same_topology": generic,
              "source_sha256": {name: sha(HERE / name) for name in
                                ("preflight.py", "circuit.py", "run.py", "geometry.json")}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "checked_field_and_state_equalities",
                       "bilinear", "generic_same_topology")}, sort_keys=True))


if __name__ == "__main__":
    main()
