"""Freeze, check, and search the exact halftrace-cubic N41 public formula."""

import argparse
import importlib.util
import json
from pathlib import Path

import circuit as method

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HORNER = ROOT / "n41_single_branch_horner_20261011"
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010" / "screen.json"
spec = importlib.util.spec_from_file_location("frozen_cubic_runner", HORNER / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.HERE = HERE
base.method = method
original_profile = base.profile


def profile(circuit, meta, construction_seconds):
    record = original_profile(circuit, meta, construction_seconds)
    record.update(pair_and_gates=meta["pair_and_gates"],
                  joint_link_and_gates=meta["joint_link_and_gates"])
    return record


def sources():
    return {"cubic_run.py": Path(__file__), "cubic_circuit.py": HERE / "circuit.py",
            "basis_circuit.py": method.BASE / "circuit.py",
            "basis_sparse.py": method.BASE / "sparse.py",
            "horner_run.py": HORNER / "run.py", "horner_circuit.py": HORNER / "circuit.py",
            "heldout_input.txt": base.SOURCE_INPUT,
            "source_screen.json": SCREEN,
            "corrected_lifts.json": base.PUBLIC_LIFTS,
            "known_blocks.json": base.KNOWN_BLOCKS,
            "karatsuba_circuit.py": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "circuit_sat.py": ROOT.parent / "koblitz-s5-invariant-20260924" / "circuit_sat.py",
            "cryptominisat5": base.SOLVER}


def source_points():
    lines = base.SOURCE_INPUT.read_text().splitlines()
    result = []
    row = 1
    for rotation in range(6):
        degree, size = map(int, lines[row].split())
        assert degree == 5 * rotation and size == 64
        row += 1
        table = {}
        for line in lines[row:row + size]:
            x, y, mask, sign, _ = map(int, line.split())
            table[mask, sign] = x, y
        assert len(table) == 64
        result.append(table)
        row += size
    assert row == len(lines)
    return result


def branch(field, left, right, output):
    rhs = field.square(left ^ right ^ output)
    assert method.trace(field, rhs) == 0
    bit = field.mul(field.mul(left, right), output) ^ method.halftrace(field, rhs)
    assert bit in (0, 1)
    return bit


def source_branch(field, a, b, output):
    s, p = a ^ b, field.mul(a, b)
    rhs = field.square(s ^ output)
    assert method.trace(field, rhs) == 0
    bit = field.mul(p, output) ^ method.halftrace(field, rhs)
    assert bit in (0, 1)
    return bit


def control():
    protocol = base.checked_protocol()
    circuit, meta, elapsed = base.build()
    frozen = json.loads(base.KNOWN_BLOCKS.read_text())
    field = method.Field()
    masks, signs = frozen["masks"], frozen["signs"]
    tables = source_points()
    screen = json.loads(SCREEN.read_text())
    raw = {row["mask"]: tuple(row["raw_pair_point"]) for row in screen["raw_audit"]}
    source = []
    for i in range(12):
        point = raw[masks[i]]
        for _ in range(5 * (i // 2)):
            point = field.square(point[0]), field.square(point[1])
        leaf = tables[i // 2][masks[i], signs[i]]
        four = base.point_add(field, point, point)
        four = base.point_add(field, four, four)
        if four != leaf:
            point = point[0], point[1] ^ point[0]
            four = base.point_add(field, point, point)
            four = base.point_add(field, four, four)
        assert four == leaf
        source.append(point)
    pairs = [base.point_add(field, source[2*i], source[2*i+1]) for i in range(6)]
    blocks = [base.point_add(field, pairs[2*i], pairs[2*i+1]) for i in range(3)]
    assert blocks == [tuple(row["point"]) for row in frozen["four_atom_blocks"]]
    intermediate = base.point_add(field, blocks[0], blocks[1])
    assert base.point_add(field, intermediate, blocks[2]) == tuple(frozen["raw_sum"])
    assert all(point is not None and point[0] for point in [*pairs, *blocks, intermediate])
    pair_z = [field.inv(point[0]) for point in pairs]
    block_z = [field.inv(point[0]) for point in blocks]
    intermediate_z = field.inv(intermediate[0])
    target_z = protocol["target_raw_reciprocal_coordinates"][1]
    assert target_z == field.inv(frozen["raw_sum"][0])
    branches = [source_branch(field, field.inv(source[2*i][0]),
                              field.inv(source[2*i+1][0]), pair_z[i]) for i in range(6)]
    branches += [branch(field, pair_z[2*i], pair_z[2*i+1], block_z[i])
                 for i in range(3)]
    branches += [branch(field, block_z[0], block_z[1], intermediate_z),
                 branch(field, intermediate_z, block_z[2], target_z)]
    initial = {}

    def bind(wires, value):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(wires)})

    for wires, value in zip(meta["masks"], masks):
        bind(wires, value)
    for wires, value in zip(meta["pair_z"], pair_z):
        bind(wires, value)
    for wires, value in zip(meta["output_z"], block_z):
        bind(wires, value)
    bind(meta["intermediate"], intermediate_z)
    for wires, value in zip(meta["branch_w"], branches):
        bind(wires, value)
    initial[meta["target_flag"]] = 1
    assert len(initial) == len(meta["primary_variables"])
    values = base.complete_assignment(circuit, initial)
    check = base.check_assignment(circuit, values)
    record = {"status": "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT",
              "target": protocol["target_q"], "known_masks": masks,
              "known_signs": signs, "pair_reciprocals": pair_z,
              "block_reciprocals": block_z, "intermediate_reciprocal": intermediate_z,
              "branch_bits": branches, "raw_lift_index": 1,
              "formula": profile(circuit, meta, elapsed), "assignment_check": check,
              "source_sha256": {"protocol.json": base.sha(HERE / "protocol.json")}}
    base.save(HERE / "control_result.json", record)
    print(json.dumps({"status": record["status"], "formula": record["formula"]}))


base.profile = profile
base.sources = sources
base.control = control


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": base.freeze, "control": control, "query": base.query}[mode]()
