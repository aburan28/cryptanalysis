"""W16 five-pair circuit with exact decision-graph source membership."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w16_exact_prefix_cache_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bdd = load("w16_membership_bdd", HERE / "bdd.py")
prior = load("w16_membership_prior", PRIOR / "core.py")
finish = prior.finish


def prepare(circuit, columns):
    if circuit.n != 131 or len(columns) != 32796:
        raise ValueError("invalid W16 source")
    masks = [[circuit.variable() for _ in range(16)] for _ in range(10)]
    flags = [circuit.variable() for _ in range(4)]
    prior.original.nonzero(circuit, flags)
    for i in range(4):
        for j in range(i + 1, 4):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    root, graph = bdd.build(set(columns), 16)
    membership = []
    for row in masks:
        wires, clauses = bdd.emit(circuit, row, root, graph)
        membership.append({"wires": wires, "clauses": clauses})
    aliases = {}
    for mask, column in columns.items():
        aliases.setdefault(column, []).append(mask)
    return {"masks": masks, "flags": flags, "aliases": aliases,
            "membership": membership, "membership_root": root,
            "membership_graph": graph}
