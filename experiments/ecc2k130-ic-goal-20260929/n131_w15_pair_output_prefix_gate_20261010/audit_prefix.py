#!/usr/bin/env python3
"""Independently replay every pair root and exact prefix complement in bits."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
CONTROL = BASE / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"
N = 131
MASK = (1 << N)-1
SQUARE_BYTE = tuple(sum(((byte >> bit) & 1) << (2*bit)
                        for bit in range(8)) for byte in range(256))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reduce_poly(value):
    while value >> N:
        upper = value >> N
        value = ((value & MASK) ^ upper ^ (upper << 1) ^
                 (upper << 2) ^ (upper << 13))
    return value


def multiply(left, right):
    product = 0
    while right:
        low = right & -right
        product ^= left << (low.bit_length()-1)
        right ^= low
    return reduce_poly(product)


def square(value):
    expanded = 0
    shift = 0
    while value:
        expanded ^= SQUARE_BYTE[value & 255] << shift
        value >>= 8
        shift += 16
    return reduce_poly(expanded)


def frobenius(value, rotation):
    for _ in range(rotation):
        value = square(value)
    return value


def audit_prefixes(allowed, forbidden, bits):
    allowed_set = set(allowed)
    assert len(allowed_set) == len(allowed)
    assert all(0 <= value < (1 << bits) for value in allowed_set)
    allowed_by_depth = {depth: {value & ((1 << depth)-1)
                                 for value in allowed_set}
                        for depth in range(1, bits+1)}
    seen = set()
    covered = 0
    for depth, pattern in sorted(map(tuple, forbidden)):
        assert 1 <= depth <= bits and 0 <= pattern < (1 << depth)
        assert (depth, pattern) not in seen
        assert all((prior, pattern & ((1 << prior)-1)) not in seen
                   for prior in range(1, depth))
        assert pattern not in allowed_by_depth[depth]
        seen.add((depth, pattern))
        covered += 1 << (bits-depth)
    assert covered + len(allowed_set) == 1 << bits
    return covered


def main():
    protocol = json.loads((HERE / "projection_protocol.json").read_text())
    roots = json.loads((HERE / "pair_roots.json").read_text())
    table = json.loads((HERE / "prefix_table.json").read_text())
    assert roots["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS"
    assert table["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_PREFIX_TABLE"
    assert table["sha256"]["roots"] == sha(HERE / "pair_roots.json")
    assert roots["sha256"]["protocol"] == table["sha256"]["protocol"] == \
        sha(HERE / "projection_protocol.json")
    columns = {int(a): int(b) for a, b in
               (row.split() for row in SUPPORT.read_text().splitlines())}
    control = json.loads(CONTROL.read_text())
    checked = []
    for index, (seed, rotation) in enumerate(zip(protocol["seeds"],
                                                 protocol["rotations"])):
        root_case = roots["pair_rows"][index]
        table_case = table["tables"][index]
        assert root_case["seed"] == table_case["seed"] == seed
        assert root_case["rotation"] == table_case["rotation"] == rotation
        expected = {(a, a ^ seed) for a, column in columns.items()
                    if (a ^ seed) in columns and a < (a ^ seed)
                    and column != columns[a ^ seed]}
        actual = {(row[0], row[1]) for row in root_case["pairs"]}
        assert actual == expected and len(actual) == len(root_case["pairs"])
        seed_field = frobenius(seed << 1, rotation)
        seed_square = square(seed_field)
        output_set = set()
        for a, b, first, second in root_case["pairs"]:
            assert first != second and 0 < first <= MASK and 0 < second <= MASK
            product = frobenius(multiply(a << 1, b << 1), rotation)
            leading = 1 ^ square(product)
            assert leading != 0
            for output in (first, second):
                assert (multiply(leading, square(output)) ^
                        multiply(product, output) ^ seed_square) == 0
                output_set.add(output)
        assert control["middle_reciprocals"][index] in output_set
        allowed = sorted({value & ((1 << protocol["prefix_bits"])-1)
                          for value in output_set})
        assert allowed == table_case["allowed_prefixes"]
        covered = audit_prefixes(allowed, table_case["forbidden_prefixes"],
                                 protocol["prefix_bits"])
        assert len(output_set) == table_case["distinct_full_outputs"]
        assert len(expected) == table_case["unordered_pair_count"]
        checked.append({"seed": seed, "rotation": rotation,
                        "unordered_pairs": len(expected),
                        "quadratic_roots_checked": 2*len(expected),
                        "allowed_prefixes": len(allowed),
                        "forbidden_prefix_clauses": len(table_case["forbidden_prefixes"]),
                        "excluded_signatures": covered})
    receipt = {"status": "PASS_INDEPENDENT_W15_PAIR_OUTPUT_PREFIX_AUDIT",
               "curve_id": protocol["curve_id"], "pair_cases": checked,
               "sha256": {"script": sha(Path(__file__)),
                          "protocol": sha(HERE / "projection_protocol.json"),
                          "roots": sha(HERE / "pair_roots.json"),
                          "table": sha(HERE / "prefix_table.json"),
                          "support": sha(SUPPORT)}}
    with (HERE / "prefix_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "pair_cases": checked}))


if __name__ == "__main__":
    main()
