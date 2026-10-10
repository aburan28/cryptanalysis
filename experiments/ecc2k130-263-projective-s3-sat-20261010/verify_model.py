#!/usr/bin/env python3
"""Independently check native-XOR SAT models and replay their point signs."""

from __future__ import annotations

import hashlib
from itertools import product
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-projective-s3-20261010"
sys.path.insert(0, str(PARENT))
import binary_group as group  # noqa: E402


ref = group.f


def parse_assignment(stdout, variable_count):
    """Require a complete, nonconflicting DIMACS model."""
    values = bytearray([2]) * (variable_count + 1)
    seen = 0
    status = []
    for line in stdout.splitlines():
        if line.startswith("s "):
            status.append(line.strip())
        if not line.startswith("v "):
            continue
        for item in line[2:].split():
            literal = int(item)
            if not literal:
                continue
            variable = abs(literal)
            if variable > variable_count:
                raise ValueError("model variable outside XCNF header")
            value = int(literal > 0)
            if values[variable] != 2 and values[variable] != value:
                raise ValueError("contradictory model assignment")
            if values[variable] == 2:
                seen += 1
            values[variable] = value
    if status != ["s SATISFIABLE"] or seen != variable_count:
        raise ValueError("missing terminal SAT line or incomplete assignment")
    return values


def literal_value(literal, values):
    value = values[abs(literal)]
    if value == 2:
        raise ValueError("unassigned literal")
    return value if literal > 0 else value ^ 1


def verify_xcnf(path, values):
    """Check every ordinary clause and signed native-XOR record."""
    clauses = xors = 0
    with path.open("rb") as stream:
        header = stream.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("XCNF has no canonical header")
        vars_, total = map(int, header[2:])
        if vars_ != len(values) - 1:
            raise ValueError("model/XCNF variable count differs")
        for line in stream:
            if not line.strip() or line.startswith(b"c"):
                continue
            if line.startswith(b"x"):
                literals = [int(x) for x in line[1:].split()]
                if not literals or literals[-1] != 0:
                    raise ValueError("malformed native XOR record")
                parity = 0
                for literal in literals[:-1]:
                    parity ^= literal_value(literal, values)
                if parity != 1:
                    raise ValueError("native XOR fails model replay")
                xors += 1
            else:
                literals = [int(x) for x in line.split()]
                if not literals or literals[-1] != 0:
                    raise ValueError("malformed ordinary clause")
                if not any(literal_value(lit, values) for lit in literals[:-1]):
                    raise ValueError("ordinary clause fails model replay")
                clauses += 1
    if clauses + xors != total:
        raise ValueError("XCNF constraint count differs from header")
    return {"variables": vars_, "ordinary_clauses_checked": clauses,
            "native_xors_checked": xors}


def read_word(name, width, input_vars, values):
    result = 0
    for bit in range(width):
        literal = input_vars[f"{name}:{bit}"]
        result |= literal_value(literal, values) << bit
    return result


def replay_signs(policy, input_vars, choice, witness, values):
    alpha, b = ref.coefficients(policy)
    if (alpha != witness["alpha"] or b != witness["normalized_b"]
            or read_word("target", ref.DEGREE, input_vars, values)
            != witness["target_x"]):
        raise ValueError("decoded target or curve coefficient differs")
    if any(literal_value(bit, values) for bit in choice):
        raise ValueError("SAT model selected a different target x")
    points = []
    masks = []
    for index, entry in enumerate(witness["leaves"]):
        mask = read_word(f"s{index}", 24, input_vars, values)
        x = read_word(f"x{index}", ref.DEGREE, input_vars, values)
        z = read_word(f"z{index}", ref.DEGREE, input_vars, values)
        expected_x, expected_z, _ = ref.leaf(mask, alpha)
        point = tuple(entry["raw_point_normalized"])
        if (mask != entry["mask"] or x != expected_x
                or z != expected_z or x != point[0]
                or not group.on_curve(point, b)):
            raise ValueError("decoded factor-base leaf differs from witness")
        points.append(point)
        masks.append(mask)
    decoded_intermediates = []
    for index in range(4):
        x = read_word(f"t{index}", ref.DEGREE, input_vars, values)
        finite = literal_value(input_vars[f"f:{index}"], values)
        if not finite and x != 1:
            raise ValueError("noncanonical identity model")
        decoded_intermediates.append((x, finite))
    target = tuple(witness["target_point_normalized"])
    if not group.on_curve(target, b):
        raise ValueError("checked target is off curve")
    satisfying_signs = []
    for signs in product((0, 1), repeat=6):
        selected = [group.negate(point) if sign else point
                    for point, sign in zip(points, signs)]
        pair01 = group.add(selected[0], selected[1], b)
        pair23 = group.add(selected[2], selected[3], b)
        pair45 = group.add(selected[4], selected[5], b)
        pair0123 = group.add(pair01, pair23, b)
        intermediates = (pair01, pair23, pair45, pair0123)
        if tuple(group.projective_x(point) for point in intermediates) != \
                tuple(decoded_intermediates):
            continue
        if group.add(pair0123, pair45, b) == target:
            satisfying_signs.append(signs)
    if not satisfying_signs:
        raise ValueError("no leaf signs replay model to exact group target")
    return {
        "target_point_exact": list(target),
        "decoded_leaf_masks": masks,
        "decoded_intermediates": [
            {"x": x, "finite": bool(finite)}
            for x, finite in decoded_intermediates],
        "matching_sign_assignments": len(satisfying_signs),
        "first_matching_signs": list(satisfying_signs[0]),
        "model_assignment_sha256": hashlib.sha256(values).hexdigest(),
    }
