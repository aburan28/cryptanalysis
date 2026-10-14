#!/usr/bin/env python3
"""Compare exact S3 tree formula shapes on the frozen N83 target slice."""

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n83-geometric-m5-fixedtarget16-20261012"
spec = importlib.util.spec_from_file_location("fixedtarget_run", PARENT / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

TREES = {
    "balanced": (("p0", "p1", "i0"), ("p2", "p3", "i1"),
                 ("i0", "i1", "i2"), ("i2", "p4", "t")),
    "leftdeep": (("p0", "p1", "i0"), ("i0", "p2", "i1"),
                 ("i1", "p3", "i2"), ("i2", "p4", "t")),
    "rightdeep": (("p3", "p4", "i0"), ("p2", "i0", "i1"),
                  ("p1", "i1", "i2"), ("p0", "i2", "t")),
    "pair_reorder": (("p0", "p4", "i0"), ("p1", "p2", "i1"),
                     ("i0", "i1", "i2"), ("i2", "p3", "t")),
    "target_first": (("p0", "t", "i0"), ("i0", "p1", "i1"),
                     ("i1", "p2", "i2"), ("i2", "p3", "p4")),
    "target_as_c_first": (("p0", "i0", "t"), ("i0", "p1", "i1"),
                         ("i1", "p2", "i2"), ("i2", "p3", "p4")),
}


def build(tree, onb, target_x):
    calls = []
    original = runner.s3_link_folded

    def defer(formula, left, right, output, multiplication, square_dest):
        calls.append((formula, left, right, output, multiplication, square_dest))
        if len(calls) < 4:
            return
        symbols = {
            "p0": calls[0][1], "p1": calls[0][2],
            "p2": calls[1][1], "p3": calls[1][2],
            "p4": calls[3][2], "t": calls[3][3],
            "i0": calls[0][3], "i1": calls[1][3],
            "i2": calls[2][3],
        }
        for left_name, right_name, output_name in tree:
            original(formula, symbols[left_name], symbols[right_name],
                     symbols[output_name], multiplication, square_dest)

    runner.s3_link_folded = defer
    try:
        formula, _, _ = runner.build_affine_formula(
            16, 1 << 81, [target_x] * 332, onb)
    finally:
        runner.s3_link_folded = original
    assert len(calls) == 4
    return runner.stats(formula)


def main():
    parent = json.loads((PARENT / "width16_ordinary.json").read_text())
    target_x = parent["formula_target_x"]
    onb = runner.field.Onb(83)
    shapes = {name: build(tree, onb, target_x)
              for name, tree in TREES.items()}
    assert shapes["balanced"] == parent["formula_shape"]
    print(json.dumps(shapes, sort_keys=True))


if __name__ == "__main__":
    main()
