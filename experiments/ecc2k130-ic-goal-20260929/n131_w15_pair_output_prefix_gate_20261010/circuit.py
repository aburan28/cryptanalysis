"""Add exact pair-output prefix support to the two-fixed-seed W15 circuit."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w15_two_fixed_seeds_public_20261010" / "circuit.py"
spec = importlib.util.spec_from_file_location("two_fixed_seed_base_circuit", ORIGINAL)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def build(*args):
    circuit = args[0]
    meta = base.build(*args)
    receipt = json.loads((HERE / "prefix_table.json").read_text())
    audit = json.loads((HERE / "prefix_audit.json").read_text())
    assert receipt["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_PREFIX_TABLE"
    assert audit["status"] == "PASS_INDEPENDENT_W15_PAIR_OUTPUT_PREFIX_AUDIT"
    assert receipt["prefix_bits"] == 16
    assert [table["seed"] for table in receipt["tables"]] == [12004, 9022]
    assert [table["rotation"] for table in receipt["tables"]] == [0, 13]
    assert tuple(meta["fixed_seeds"]) == (12004, 9022)
    counts = []
    for pair_index, table in enumerate(receipt["tables"]):
        wires = meta["middle"][pair_index]
        assert len(wires) == circuit.n == 131
        for depth, pattern in table["forbidden_prefixes"]:
            assert 1 <= depth <= receipt["prefix_bits"]
            assert 0 <= pattern < (1 << depth)
            circuit.clauses.append(" ".join(
                str(-wire if pattern >> bit & 1 else wire)
                for bit, wire in enumerate(wires[:depth])) + " 0")
        counts.append(len(table["forbidden_prefixes"]))
    meta["prefix_filter_clause_counts"] = counts
    meta["prefix_filter_bits"] = receipt["prefix_bits"]
    meta["prefix_filter_allowed_counts"] = [len(table["allowed_prefixes"])
                                            for table in receipt["tables"]]
    return meta
