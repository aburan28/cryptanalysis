#!/usr/bin/env python3
"""Profile exact S3 leaf-link encodings on the frozen N131 W14 field."""
import hashlib
import json
from pathlib import Path

from audit import GATE, HERE, PARENT, gate, method, sha

SUPPORT = PARENT / "n131_w14_ten_source_gate_20261009"
N = 131
WIDTH = 14
LOW_TERMS = [0, 1, 2, 13]


def half_trace(field, value):
    result = 0
    current = value
    for _ in range((N + 1) // 2):
        result ^= current
        current = field.mul(current, current)
        current = field.mul(current, current)
    assert field.mul(result, result) ^ result == value
    return result


def build(field, rotations, variant):
    circuit = gate.old.base.KaratsubaCircuit(N, LOW_TERMS)
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(2)]
    output = [circuit.variable() for _ in range(N)]
    frame = rotations[0] if variant == "local_frame" else 0
    relative = [(rotation - frame) % N for rotation in rotations]
    bases_w = [[gate.old.frob(field, 1 << i, rotation)
                for i in range(1, WIDTH + 1)] for rotation in rotations]
    link_bases_w = [[gate.old.frob(field, 1 << i, rotation)
                     for i in range(1, WIDTH + 1)] for rotation in relative]
    bases_u = [[half_trace(field, value) for value in row]
               for row in (link_bases_w if variant == "local_frame" else bases_w)]
    u = [circuit.linear_element(masks[i], bases_u[i]) for i in range(2)]
    link_output = (circuit.linear_element(
        output, [gate.old.frob(field, 1 << bit, (N - frame) % N)
                 for bit in range(N)]) if frame else output)
    if variant == "generic":
        method.generic_link(circuit, u[0], u[1], link_output)
    else:
        method.low_product_link(circuit, masks[0], masks[1],
                                link_bases_w[0], link_bases_w[1],
                                u[0], u[1], link_output)
    nonzero_w = [sum(any(value >> bit & 1 for value in bases_w[i])
                     for bit in range(N))
                 for i in range(2)]
    return {"variables": circuit.next_var - 1,
            "clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "nonzero_w_coordinates": nonzero_w}


def main():
    support = json.loads((SUPPORT / "support_protocol.json").read_text())
    receipt = json.loads((SUPPORT / "sage_support_audit.json").read_text())
    assert receipt["status"] == "PASS_FULL_MASKS_ORBITS_AND_TEN_WINDOW_BASE"
    assert support["curve_id"] == "EC1N131Ckb1heb5f1998f20b"
    field = gate.old.base.Field(N, LOW_TERMS)
    cases = {}
    rotations_of_policy = support["rotations"]
    assert rotations_of_policy == list(range(0, 130, 13))
    for rotations in ([tuple(rotations_of_policy[i:i + 2])
                       for i in range(0, 10, 2)] + [(0, 0)]):
        key = "_".join(map(str, rotations))
        cases[key] = {variant: build(field, rotations, variant)
                      for variant in ("generic", "low_product", "local_frame")}
    result = {"status": "PASS_EXACT_N131_W14_LEAF_PROFILE",
              "candidate_id": None, "curve_id": support["curve_id"],
              "factor_base_policy": "W14 polynomial source with ten distinct rotations",
              "actual_rotation_pairs": [rotations_of_policy[i:i + 2]
                                        for i in range(0, 10, 2)],
              "profile_boundary": "one S3 leaf link, no rationality, distinct-column, or target constraints",
              "cases": cases,
              "source_sha256": {"script": sha(__file__),
                                "circuit": sha(HERE / "circuit.py"),
                                "support_protocol": sha(SUPPORT / "support_protocol.json"),
                                "support_audit": sha(SUPPORT / "sage_support_audit.json"),
                                "gate_run": sha(GATE / "run.py")}}
    with (HERE / "n131_leaf_profile.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "cases": cases}, sort_keys=True))


if __name__ == "__main__":
    main()
