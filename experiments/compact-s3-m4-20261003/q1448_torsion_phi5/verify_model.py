"""Independently replay a Q1448 SAT model against the exact point relation."""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from q1448_torsion_phi5.build_formula import transformed_targets  # noqa: E402


def model_from_file(path: Path) -> dict[int, bool]:
    content = path.read_text()
    assert "s SATISFIABLE" in content
    model = {}
    for line in content.splitlines():
        if line.startswith("v "):
            for token in line[2:].split():
                lit = int(token)
                if lit:
                    assert abs(lit) not in model
                    model[abs(lit)] = lit > 0
    return model


def decode(bits, model):
    return sum(1 << i for i, bit in enumerate(bits) if model[bit])


def replay(formula, meta, model_path: Path, instance: dict) -> dict:
    model = model_from_file(model_path)
    assert set(range(1, formula.variables + 1)).issubset(model)
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    n = meta["field_degree_n"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    selector = decode(meta["target_selector_variables"], model)
    assert selector < len(meta["raw_target_x_values"])
    assert decode(meta["target_phi_variables"], model) == meta[
        "transformed_target_u_values"][selector]
    raw_masks = [decode(bits, model) for bits in meta["leaf_x_variables"]]
    phi_masks = [decode(bits, model) for bits in meta["leaf_phi_variables"]]
    for x, u in zip(raw_masks, phi_masks):
        assert u == transformed_targets(onb, [x])[0]
    raw_points, projected_points, projected_keys = [], [], []
    for mask in raw_masks:
        assert 0 < mask < (1 << n)
        assert mask.bit_count() <= meta["normal_basis_weight_bound"]
        point = curve.pointFromX(onb.fromCoords(mask))
        if point is None:
            return {"status": "nonrational_raw_x", "raw_leaf_x": raw_masks,
                    "target_selector_choice": selector}
        subgroup = curve.mul(point, instance["cofactor"])
        if subgroup is None:
            return {"status": "identity_projection", "raw_leaf_x": raw_masks,
                    "target_selector_choice": selector}
        assert curve.mul(subgroup, instance["subgroup_order"]) is None
        key = canonical_rotation(orbit.cycle_bits(subgroup[0]), n)
        raw_points.append(point)
        projected_points.append(subgroup)
        projected_keys.append(key)
    if len(set(projected_keys)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": raw_masks,
                "target_selector_choice": selector}
    public = tuple(map(int, meta["public_target"]))
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(raw_points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total is not None and curve.mul(total, instance["cofactor"]) == public:
            return {
                "status": "verified_four_point_relation",
                "raw_leaf_x": raw_masks,
                "raw_leaf_phi": phi_masks,
                "signs": list(signs),
                "target_selector_choice": selector,
                "target_raw_x": meta["raw_target_x_values"][selector],
                "projected_points": [[int(x), int(y)]
                                     for x, y in projected_points],
                "projected_columns": projected_keys,
                "distinct_columns": 4,
                "public_target": list(public),
            }
    return {"status": "no_signed_public_sum", "raw_leaf_x": raw_masks,
            "target_selector_choice": selector}
