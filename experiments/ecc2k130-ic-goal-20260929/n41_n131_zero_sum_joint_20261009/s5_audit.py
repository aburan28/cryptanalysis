#!/usr/bin/env python3
"""Independent Sage replay of a target-ended S5 SAT model and raw leaf signs."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_triple_20261009"
N, ORDER = 41, 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def main(mode):
    output = HERE / f"s5_{mode}" / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    result = json.loads((HERE / f"s5_{mode}" / "result.json").read_text())
    build_file = "s5_control_build.json" if mode == "chart" else f"s5_{mode}_build.json"
    build = json.loads((HERE / build_file).read_text())
    assert runtime["status"] == "verified"
    assert result["sha256"]["protocol"] == sha(HERE / "s5_protocol.json")
    receipt = {"status": "NO_MODEL", "mode": mode,
               "producer_status": result["status"],
               "sha256": {"source": sha(__file__),
                          "runtime": sha(HERE / "sage_runtime_info.json"),
                          "protocol": sha(HERE / "s5_protocol.json"),
                          "producer_result": sha(HERE / f"s5_{mode}" / "result.json")}}
    if result["status"] != "SAT_MODEL":
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps(receipt, sort_keys=True))
        return
    bits_file = HERE / f"s5_{mode}" / "model_bits.txt"
    assert result["sha256"]["model_bits"] == sha(bits_file)
    bits = bits_file.read_text().strip()
    assert len(bits) == build["formula_variables"]

    def unpack(wires):
        return sum((bits[wire-1] == "1") << i for i, wire in enumerate(wires))

    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**N, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(polynomial([(int(value) >> i) & 1 for i in range(N)]))

    def half_trace(value):
        value_out = field.zero()
        for _ in range((N + 1)//2):
            value_out += value
            value = value**4
        return value_out

    def transform(point):
        if point == curve(0) or point[0] == 1:
            return None
        return encode(1/(point[0] + 1))

    lines = (SOURCE / "input_public.txt").read_text().splitlines()
    qx, qy, r, blocks = map(int, lines[0].split())
    assert r == ORDER and blocks == 4
    target = curve(decode(qx), decode(qy))
    assert ORDER*target == curve(0)
    input_map = {}
    position = 1
    for block, rotation in enumerate((0, 10, 20, 30)):
        actual, count = map(int, lines[position].split())
        assert actual == rotation and count == 126
        position += 1
        for line in lines[position:position+count]:
            mask, sign, column, x, y = map(int, line.split())
            input_map[(block, mask, x, y)] = (sign, column)
        position += count
    assert position == len(lines)

    mask_triples = []
    for a_wires, b_wires in build["mask_wire_rows"]:
        a, b = unpack(a_wires), unpack(b_wires)
        mask_triples.append((a, b, a ^ b))
    assert mask_triples == [tuple(row) for row in result["model_masks"]]
    z_values = [unpack(row) for row in build["block_output_wire_rows"]]
    assert z_values == result["model_block_u"]
    chosen_flags = [bits[wire-1] == "1" for wire in build["target_flag_wires"]]
    assert sum(chosen_flags) == 1
    fiber_index = chosen_flags.index(True)
    assert fiber_index == result["model_target_fiber_index"]
    target_u = build["target_u_fiber"][fiber_index]

    # Re-evaluate the five-point invariant with Sage field arithmetic.
    values = list(map(decode, z_values + [target_u]))
    w = [value*value + value for value in values]
    e = [field.one()] + [field.zero() for _ in range(5)]
    for index, wi in enumerate(w):
        for k in range(index + 1, 0, -1):
            e[k] += e[k-1]*wi
    v = (sum(values, field.zero()))**2
    e3sq, e4sq, e5sq = e[3]**2, e[4]**2, e[5]**2
    check = v + e[5]
    check = check*v + e4sq
    check = check*v + e[5]*(e3sq + e5sq)
    check = check*v + (e[2]*e[5] + e3sq + e5sq)**2 + e[5]*e5sq
    assert check == 0

    block_states = []
    for block, masks in enumerate(mask_triples):
        assert 0 < masks[0] < masks[1] < masks[2]
        assert masks[0] ^ masks[1] == masks[2]
        choices = []
        for mask in masks:
            w = sum((field(t**(i + 1)) for i in range(7) if mask >> i & 1),
                    field.zero())
            if (1/w).trace() != 0:
                choices = []
                break
            u = half_trace(w)**(2**(10*block))
            if u in (0, 1):
                choices = []
                break
            possible = []
            for raw in curve.lift_x(1 + 1/u, all=True):
                subgroup = 4*raw
                if subgroup == curve(0) or ORDER*subgroup != curve(0):
                    continue
                x, y = encode(subgroup[0]), encode(subgroup[1])
                key = (block, mask, x, y)
                if key in input_map:
                    sign, column = input_map[key]
                    possible.append((raw, subgroup, mask, sign, column))
            choices.append(possible)
        admissible = []
        if len(choices) == 3:
            for triple in itertools.product(*choices):
                columns = [leaf[4] for leaf in triple]
                if len(set(columns)) < 3:
                    continue
                raw_sum = sum((leaf[0] for leaf in triple), curve(0))
                if transform(raw_sum) == z_values[block]:
                    admissible.append((raw_sum, triple))
        block_states.append(admissible)

    torsion = curve(field(1), field(1))
    target_fiber = [pow(4, -1, ORDER)*target + i*torsion for i in range(4)]
    assert len(set(target_fiber)) == 4
    row = None
    for states in itertools.product(*block_states):
        raw_total = sum((item[0] for item in states), curve(0))
        if raw_total != target_fiber[fiber_index]:
            continue
        leaves = tuple(leaf for state in states for leaf in state[1])
        if len({leaf[4] for leaf in leaves}) != 12:
            continue
        if sum((leaf[1] for leaf in leaves), curve(0)) != target:
            continue
        row = [{"rotation": 10*(i//3), "mask": leaf[2],
                "sign": leaf[3], "column": leaf[4],
                "point": [encode(leaf[1][0]), encode(leaf[1][1])]}
               for i, leaf in enumerate(leaves)]
        break
    receipt.update({"status": "VERIFIED_RAW_ROW" if row else "EXTRANEOUS_MODEL",
                    "model_masks": [list(triple) for triple in mask_triples],
                    "block_output_u": z_values,
                    "target_fiber_index": fiber_index,
                    "block_state_counts": list(map(len, block_states)),
                    "row": row})
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "mode", "model_masks",
                       "block_state_counts", "target_fiber_index")},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("chart", "control", "public"))
    main(parser.parse_args().mode)
