#!/usr/bin/env python3
"""Build exact four-hot normal4 leaves and balanced four-lift m6 XCNFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BALANCED = ROOT / "experiments/ecc2k130-equalb-balanced-s3-20261010"
sys.path.insert(0, str(BALANCED))

import build_balanced as parent  # noqa: E402


gate = parent.gate
source = parent.source
ref = parent.ref
WIDTH = 131
INDEX_BITS = 8
POLICIES = ("counter", "support_index")


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def assert_exact_four_counter(formula, bits: list[int]) -> None:
    """Constrain four-hot membership with O(4n) threshold state."""
    formula.atMost(bits, 4)
    ge = [formula.true] + [formula.false] * 4
    for bit in bits:
        following = [formula.true]
        for threshold in range(1, 5):
            following.append(formula.orLit(
                ge[threshold], formula.andLit(bit, ge[threshold - 1])))
        ge = following
    formula.addClause([ge[4]])


def less_than(formula, a: list[int], b: list[int]) -> None:
    """Assert a < b for equal-width little-endian unsigned bit vectors."""
    formula.lexLeq(list(reversed(a)), list(reversed(b)))
    formula.addClause([formula.xorLit(left, right)
                       for left, right in zip(a, b)])


def support_literals(formula) -> tuple[list[int], list[list[int]]]:
    """Decode four ordered eight-bit positions to one exact four-hot mask."""
    positions = [[formula.newVar() for _ in range(INDEX_BITS)]
                 for _ in range(4)]
    bound = [formula.true if (130 >> bit) & 1 else formula.false
             for bit in range(INDEX_BITS)]
    decoders = []
    for position in positions:
        formula.lexLeq(list(reversed(position)), list(reversed(bound)))
        prefix = {(0, 0): formula.true}
        equal = []
        for value in range(WIDTH):
            for depth in range(1, INDEX_BITS + 1):
                key = (depth, value >> (INDEX_BITS - depth))
                if key not in prefix:
                    prior = prefix[(depth - 1, key[1] >> 1)]
                    bit = position[INDEX_BITS - depth]
                    prefix[key] = formula.andLit(
                        prior, bit if key[1] & 1 else -bit)
            equal.append(prefix[(INDEX_BITS, value)])
        decoders.append(equal)
    for left, right in zip(positions, positions[1:]):
        less_than(formula, left, right)
    mask = [formula.orLit(
        formula.orLit(decoders[0][bit], decoders[1][bit]),
        formula.orLit(decoders[2][bit], decoders[3][bit]))
        for bit in range(WIDTH)]
    return mask, positions


def encode(policy: str, mode: str):
    if policy not in POLICIES or mode not in ("leaf", "m6"):
        raise ValueError("unknown selector policy or formula mode")
    xs = gate.target_lifts() if mode == "m6" else None
    if mode == "m6":
        prog, roots, leaves, chain = parent.build_ir("normal4_source")
    else:
        prog, roots, leaves, chain = source.build_ir(
            "normal4_source", "leaf", None)
    formula = source.cnf.Cnf()
    literals = {("one", 0): formula.true}
    masks = []
    positions = []
    coordinates = []
    for index, leaf in enumerate(leaves):
        if len(leaf["selectors"]) != WIDTH:
            raise ValueError("normal4 selector width changed")
        if policy == "counter":
            mask = [formula.newVar() for _ in range(WIDTH)]
            assert_exact_four_counter(formula, mask)
            current_positions = None
        else:
            mask, current_positions = support_literals(formula)
        masks.append(mask)
        positions.append(current_positions)
        for bit, literal in enumerate(mask):
            literals[("s%d" % index, bit)] = literal
        xyz = {}
        for name in ("x", "z"):
            xyz[name] = [formula.newVar() for _ in range(ref.DEGREE)]
            for bit, literal in enumerate(xyz[name]):
                literals[("%s%d" % (name, index), bit)] = literal
        coordinates.append(xyz)
    for left, right in zip(masks, masks[1:]):
        formula.lexLeq(list(reversed(left)), list(reversed(right)))
    target_selectors = None
    if xs is not None:
        target_bits, target_selectors = gate.encode_target_mux(formula, xs)
        for bit, literal in enumerate(target_bits):
            literals[("target", bit)] = literal
        for index in range(len(chain)):
            for bit in range(ref.DEGREE):
                literals[("t%d" % index, bit)] = formula.newVar()
    for literal in prog.emitCnf(roots, literals, formula):
        formula.assertZero(literal)
    return formula, {"masks": masks, "positions": positions,
                     "coordinates": coordinates,
                     "target_selectors": target_selectors,
                     "ir_operations": prog.opCount(roots),
                     "target_x_choices": xs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--mode", choices=("leaf", "m6"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix(".json").exists():
        parser.error("refusing to overwrite formula or receipt")
    started = time.perf_counter()
    formula, mapping = encode(args.policy, args.mode)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula.writeDimacs(args.out)
    receipt = {
        "schema": "ecc2k130-normal4-selector-xcnf-v1",
        "status": "FORMULA_BUILT",
        "candidate_id": None,
        "policy": args.policy,
        "mode": args.mode,
        "ordinary_query_index": 0 if args.mode == "m6" else None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "actual_usable_points_B": 11743888,
        "summands": 6 if args.mode == "m6" else 1,
        "target_x_choices": ([str(value) for value in mapping["target_x_choices"]]
                             if mapping["target_x_choices"] else None),
        "formula_sha256": ref.sha(args.out),
        "builder_sha256": ref.sha(Path(__file__)),
        "balanced_builder_sha256": ref.sha(BALANCED / "build_balanced.py"),
        "leaf_builder_sha256": ref.sha(gate.PARENT / "build_formula.py"),
        "input_prefix_sha256": ref.sha(ref.EQUAL / "runs/R1/base_prefixes.json"),
        "stats": formula.stats(),
        "ir_operations": mapping["ir_operations"],
        "build_wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_bytes(),
    }
    args.out.with_suffix(".json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("policy", "mode", "formula_sha256", "stats",
                       "build_wall_seconds", "peak_rss_bytes")}, sort_keys=True))


if __name__ == "__main__":
    main()
