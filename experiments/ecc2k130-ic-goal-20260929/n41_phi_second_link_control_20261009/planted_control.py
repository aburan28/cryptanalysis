#!/usr/bin/env sage -python
"""Check the N41 phi-chain specialization with a separately planted relation."""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
TEMPLATE = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/"
            "m16_static")
sys.path.insert(0, str(TEMPLATE))
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as template

N, DIM, M = 41, 6, 12
SEED = 202610091331


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_at(onb, curve, basis, code, position):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("planted code lost a curve point")
    return point


def phi_mask(onb, point):
    if point is None or point[0] == onb.one():
        raise ValueError("nonfinite planted chain point")
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    output = HERE / "planted_control.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, table_path, ready_path = (HERE / name for name in
                                             ("protocol.json", "table.json", "preflight.json"))
    protocol = json.loads(protocol_path.read_text())
    table = json.loads(table_path.read_text())
    ready = json.loads(ready_path.read_text())
    if (ready["status"] != "PASS_EXACT_GROUP_AND_XCNF" or
            ready["source_sha256"]["protocol"] != sha(protocol_path) or
            table["selected_first_link_root"] != protocol["first_root_mask"]):
        raise ValueError("frozen N41 control changed")
    template.N, template.DIM, template.M = N, DIM, M
    onb = template.field.Onb(N)
    curve = template.curves.Curve(onb)
    basis = table["basis_coordinate_masks"]
    valid = table["valid_codes"]
    fixed = table["first_link_leaf_codes"]
    p0 = point_at(onb, curve, basis, fixed[0], 0)
    p1 = point_at(onb, curve, basis, fixed[1], 1)
    if phi_mask(onb, curve.add(p0, p1)) == protocol["first_root_mask"]:
        first_sign = 0
    elif phi_mask(onb, curve.add(p0, curve.neg(p1))) == protocol["first_root_mask"]:
        first_sign = 1
    else:
        raise ValueError("fixed first root has no signed point realization")
    rng = random.Random(SEED)
    for trial in range(1, 1001):
        codes = list(fixed)
        signs = [0, first_sign]
        running = curve.add(p0, p1 if first_sign == 0 else curve.neg(p1))
        partials = [phi_mask(onb, running)]
        try:
            for position in range(2, M):
                code = rng.choice(valid)
                sign = rng.randrange(2)
                point = point_at(onb, curve, basis, code, position)
                running = curve.add(running, point if sign == 0 else curve.neg(point))
                codes.append(code)
                signs.append(sign)
                if position < M - 1:
                    partials.append(phi_mask(onb, running))
            endpoint_mask = phi_mask(onb, running)
        except ValueError:
            continue
        if len(partials) == M - 2:
            break
    else:
        raise ValueError("could not construct finite planted chain")
    row = next(item for item in table["rows"] if item[0] == codes[2])
    if partials[1] not in row[1:]:
        raise ValueError("planted second-link output escapes lookup table")
    root_choice = 0 if partials[1] == row[1] else 1
    formula, primary, roots, prog, node_lits, linear = template.build_formula(
        onb, basis, valid, [endpoint_mask] * 4)
    pins = {f"leaf{position}": [(codes[position] >> bit) & 1
                                for bit in range(DIM)]
            for position in range(M)}
    pins.update({f"partial{index}": [(mask >> bit) & 1 for bit in range(N)]
                 for index, mask in enumerate(partials)})
    pins["endpoint"] = [0, 0]
    assignment = template.evaluate_and_check(formula, primary, pins, prog,
                                             node_lits, linear)
    if len(roots) != (M - 1) * N or not all(value is not None for value in assignment[1:]):
        raise ValueError("planted model did not cover the full XCNF")
    receipt = {
        "kind": "n41_phi_second_link_planted_chain_correctness_control",
        "status": "PASS_FULL_PLANTED_XCNF_AND_LOOKUP_ROOT",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "role": "correctness_only_not_ordinary_yield",
        "trial": trial, "leaf_codes": codes, "leaf_signs": signs,
        "partial_phi_masks": partials,
        "synthetic_endpoint_phi_mask": endpoint_mask,
        "second_link_root_choice": root_choice,
        "checked_formula_variables": formula.nVars,
        "checked_formula_clauses": len(formula.clauses),
        "checked_formula_xors": len(formula.xors),
        "source_sha256": {"protocol": sha(protocol_path),
                          "table": sha(table_path),
                          "preflight": sha(ready_path),
                          "script": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "trial": trial,
                      "second_link_root_choice": root_choice}))


if __name__ == "__main__":
    main()
