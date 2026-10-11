"""Replay the archived positive product witness through every XCNF row."""

import gzip
import hashlib
import json
from functools import reduce
from operator import xor
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N131_FIXED_OUTPUT_QUARTIC_SAT"
    assert protocol["source_sha256"]["build"] == build.sha(build.__file__)
    assert protocol["source_sha256"]["factorization"] == build.sha(build.FACTORS)
    assert protocol["source_sha256"]["control"] == build.sha(build.CONTROL)
    profile = json.loads((HERE / "factor0_build.json").read_text())
    data = json.loads(build.FACTORS.read_text())
    witness = json.loads(build.CONTROL.read_text())["n131"]
    seed = sum((1 << (i + 1) for i in range(15)
                if witness["seed_mask"] >> i & 1), 0)
    left_basis = build.product_basis(seed, 26)
    right_basis = build.product_basis(seed, 39)
    circuit, left_bits, right_bits = build.build(data["factors"][0], left_basis,
                                                   right_basis)
    pcode, qcode = profile["known_product_codes"]
    assert reduce(xor, (v for i, v in enumerate(left_basis) if pcode >> i & 1), 0) == witness["rotated_pair_products"][0]
    assert reduce(xor, (v for i, v in enumerate(right_basis) if qcode >> i & 1), 0) == witness["rotated_pair_products"][1]
    initial = {wire: bool(code >> index & 1)
               for code, bits in ((pcode, left_bits), (qcode, right_bits))
               for index, wire in enumerate(bits)}
    definitions = {out: ("and", a, b)
                   for (a, b), out in circuit.and_cache.items()}
    for row in circuit.xors:
        literals = [int(v) for v in row.split()[1:-1]]
        definitions[abs(literals[0])] = ("xor", literals)
    values = [False] * circuit.next_var
    for wire, value in initial.items():
        values[wire] = value
    for wire in range(1, circuit.next_var):
        if wire in initial:
            continue
        definition = definitions[wire]
        if definition[0] == "and":
            def literal(v):
                return v == -1 or (v > 0 and values[v])
            values[wire] = literal(definition[1]) and literal(definition[2])
        else:
            literals = definition[1]
            value = literals[0] > 0
            for v in literals[1:]:
                value ^= values[abs(v)] ^ (v < 0)
            values[wire] = value
    formula = HERE / "factor0.xcnf.gz"
    assert build.sha(formula) == profile["formula_gzip_sha256"]
    clauses = xors = 0
    digest = hashlib.sha256()
    with gzip.open(formula, "rb") as stream:
        for raw in stream:
            digest.update(raw)
            row = raw.decode().strip()
            if row.startswith("p "):
                assert row == (f"p cnf {profile['variables']} "
                               f"{profile['clauses'] + profile['xor_rows']}")
                continue
            if not row:
                continue
            if row.startswith("x "):
                literals = [int(v) for v in row.split()[1:-1]]
                assert sum(values[abs(v)] ^ (v < 0) for v in literals) % 2 == 1
                xors += 1
            else:
                literals = [int(v) for v in row.split()[:-1]]
                assert any(values[abs(v)] == (v > 0) for v in literals)
                clauses += 1
    assert clauses == profile["clauses"] and xors == profile["xor_rows"]
    result = {"status": "PASS_FULL_POSITIVE_QUARTIC_XCNF_ASSIGNMENT",
              "factor_index": 0, "known_product_codes": [pcode, qcode],
              "clauses_checked": clauses, "xor_rows_checked": xors,
              "formula_sha256": digest.hexdigest(),
              "formula_gzip_sha256": profile["formula_gzip_sha256"],
              "protocol_sha256": build.sha(HERE / "protocol.json"),
              "audit_source_sha256": build.sha(__file__)}
    (HERE / "audit_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
