#!/usr/bin/env python3
"""Rebuild the frozen N41 relation assignment for an independent XCNF check."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w5_allpair_index_20261010"

spec = importlib.util.spec_from_file_location("frozen_allpair_runner", SOURCE / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    ctx, entries, hit, masks, signs, middle, targets, selected = runner.context_and_witness()
    circuit, meta = runner.build(ctx, targets, entries)
    initial = {}
    for row, mask in zip(meta["masks"], masks):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == hit["target_preimage_index"])
    for row, point in zip(meta["middle"], middle):
        value = runner.single.old.old.transformed(ctx["field"], point)
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    for pair in range(5):
        for i, wire in enumerate(meta["pair_selectors"][pair]):
            initial[wire] = int(i == selected[pair])
        for i, wire in enumerate(meta["pair_sequences"][pair]):
            initial[wire] = int(selected[pair] <= i)
    assignment = runner.single.old.old.witness_tools.complete_assignment(circuit, initial)
    path = HERE / "control_model.stdout.txt"
    assert not path.exists()
    with path.open("x") as out:
        out.write("s SATISFIABLE\n")
        for variable in range(1, circuit.next_var):
            value = assignment.get(variable)
            assert value is not None, variable
            out.write(f"v {variable if value else -variable} 0\n")
    assert selected == [240, 172, 138, 253, 178]
    print(json.dumps({"status": "PASS", "variables": circuit.next_var - 1,
                      "control_model": str(path)}))


if __name__ == "__main__":
    main()
