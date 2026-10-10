"""Exact pair-order quotient of the frozen two-fixed-seed W15 circuit."""

import importlib.util
from pathlib import Path

BASELINE = Path(__file__).resolve().parent.parent / "n131_w15_two_fixed_seeds_public_20261010" / "circuit.py"
spec = importlib.util.spec_from_file_location("lex_baseline_circuit", BASELINE)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def build(circuit, field, bases_w, columns, target_reciprocals,
          rotations, frobenius):
    meta = baseline.build(circuit, field, bases_w, columns,
                          target_reciprocals, rotations, frobenius)
    assert len(meta["masks"]) == 12
    for pair in range(6):
        left, right = meta["masks"][2*pair:2*pair+2]
        assert len(left) == len(right) == 15
        differences = [circuit.xor((a, b)) for a, b in zip(left, right)]
        for bit in range(15):
            # With every more significant bit equal, forbid left=1,right=0.
            clause = [*differences[bit+1:], -left[bit], right[bit]]
            circuit.clauses.append(" ".join(map(str, clause)) + " 0")
    meta["lex_pairs"] = 6
    meta["lex_clauses"] = 90
    meta["lex_reused_difference_wires"] = 90
    meta["lex_added_xor_rows"] = 0
    return meta
