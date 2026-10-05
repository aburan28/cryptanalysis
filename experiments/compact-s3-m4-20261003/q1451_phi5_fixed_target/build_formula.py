"""Specialize the compact phi5 circuit to one public-target raw preimage.

The selected target phi coordinate is a field constant in every product.
Metadata-only unit variables let the unchanged Q1448 point-replay checker
verify the selected raw preimage and its public target.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import (  # noqa: E402
    Formula, field, multiplication_table, product, square_destinations)
from q1448_torsion_phi5.build_formula import (  # noqa: E402
    BASE, ORDINARY, const_bits, phi5_terms, transformed_targets, xor_vectors)


def build(n: int, target_index: int = 0,
          raw_target_override: int | None = None,
          public_target_override=None):
    assert n in (53, 83)
    onb = field.Onb(n)
    base = json.loads(BASE[n].read_text())
    parent = json.loads(ORDINARY[n].read_text())
    assert base["curve_id"] == parent["curve_id"]
    original_raw = [int(x) for x in parent["raw_preimage_x_coordinates"]]
    if raw_target_override is None:
        assert 0 <= target_index < len(original_raw)
        selected_raw = original_raw[target_index]
        public_target = parent["public_target"]
        full_preimage_count = len(original_raw)
    else:
        assert target_index == 0
        assert public_target_override is not None
        selected_raw = int(raw_target_override)
        public_target = public_target_override
        full_preimage_count = 1
    selected_u = transformed_targets(onb, [selected_raw])[0]
    weight = int(base["normal_basis_weight_bound"])
    formula = Formula()
    xs = [[formula.new() for _ in range(n)] for _ in range(4)]
    us = [[formula.new() for _ in range(n)] for _ in range(4)]
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    one = const_bits(onb.toCoords(onb.one()), n)
    for x, u in zip(xs, us):
        formula.at_most(x, weight)
        formula.clauses.append(x[:])
        x_plus_one = xor_vectors(formula, x, one)
        inverse_check = product(formula, u, x_plus_one, table)
        for bit, expected in zip(inverse_check, one):
            formula.clauses.append([bit if expected == 1 else -bit])
    terms = phi5_terms(formula, [*us, const_bits(selected_u, n)],
                       table, destinations)
    for position in range(n):
        formula.xor_relation([term[position] for term in terms])

    # The point replay expects a target-phi vector and a selector. These
    # unit-fixed variables are deliberately not used in the phi5 circuit.
    target_bits = [formula.new() for _ in range(n)]
    for bit, expected in zip(target_bits, const_bits(selected_u, n)):
        formula.clauses.append([bit if expected == 1 else -bit])
    selector = [formula.new()]
    formula.clauses.append([-selector[0]])
    meta = {
        "proposal_id": "Q1451",
        "candidate_id": None,
        "isogeny": "none",
        "curve_id": base["curve_id"],
        "field_degree_n": n,
        "normal_basis_weight_bound": weight,
        "factor_base_actual_B": base[
            "actual_usable_points_B_before_folding"],
        "folded_columns_K": base["signed_frobenius_columns_K"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "public_target": public_target,
        "raw_target_x_values": [selected_raw],
        "transformed_target_u_values": [selected_u],
        "target_preimage_index": target_index,
        "target_preimage_x_count": 1,
        "full_target_preimage_x_count": full_preimage_count,
        "leaf_x_variables": xs,
        "leaf_phi_variables": us,
        "target_phi_variables": target_bits,
        "target_selector_variables": selector,
    }
    return formula, meta
