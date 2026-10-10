#!/usr/bin/env python3
"""Build an exact one-formula four-target-lift source m6 XCNF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/ecc2k130-equalb-m6-leaf-circuit-20261010"
sys.path.insert(0, str(PARENT))

import build_formula as source  # noqa: E402
import field as ref  # noqa: E402


LIFTS = PARENT / "runs/R1/torsion_lifts.json"
PUBLIC = ref.EQUAL / "runs/R1/point16/public_points.json"
POLICIES = ("w24_source", "normal4_source")


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def target_lifts() -> list[int]:
    receipt = json.loads(LIFTS.read_text())
    public = json.loads(PUBLIC.read_text())
    if (receipt["status"] != "PASS_FOUR_EXACT_RAW_TARGET_LIFTS"
            or receipt["source_curve_id"] != "EC1N131Ckb1h136f03e58c98"
            or receipt["query_index"] != 0
            or receipt["public_input_sha256"] != ref.sha(PUBLIC)
            or receipt["query"] != public["first_16_public_queries"][0]["source"]
            or receipt["distinct_x_coordinates"] != 4
            or not receipt["all_project_to_four_times_query"]):
        raise ValueError("four raw target lifts are not source-bound")
    rows = receipt["raw_target_lifts"]
    if [row["torsion_shift"] for row in rows] != list(range(4)):
        raise ValueError("target-lift order changed")
    xs = [int(row["point"][0]) for row in rows]
    if len(set(xs)) != 4 or any(x <= 0 or x > ref.MASK for x in xs):
        raise ValueError("invalid target-lift x coordinates")
    return xs


def encode_target_mux(formula, xs: list[int]):
    """Return target bits for j=s0+2*s1 and the two selection literals."""
    if len(xs) != 4 or len(set(xs)) != 4:
        raise ValueError("four distinct target coordinates are required")
    s0, s1 = formula.newVar(), formula.newVar()
    both = formula.andLit(s0, s1)
    bits = []
    for bit in range(ref.DEGREE):
        values = [(x >> bit) & 1 for x in xs]
        value = formula.true if values[0] else formula.false
        if values[0] ^ values[1]:
            value = formula.xorLit(value, s0)
        if values[0] ^ values[2]:
            value = formula.xorLit(value, s1)
        if values[0] ^ values[1] ^ values[2] ^ values[3]:
            value = formula.xorLit(value, both)
        bits.append(value)
    return bits, (s0, s1)


def encode(policy: str, prog, roots, leaves, chain, xs: list[int]):
    formula = source.cnf.Cnf()
    literals = {("one", 0): formula.true}
    selectors = []
    for index, leaf in enumerate(leaves):
        bits = [formula.newVar() for _ in leaf["selectors"]]
        selectors.append(bits)
        for bit, literal in enumerate(bits):
            literals[("s%d" % index, bit)] = literal
        for name in ("x", "z"):
            for bit in range(ref.DEGREE):
                literals[("%s%d" % (name, index), bit)] = formula.newVar()
        if policy == "normal4_source":
            formula.atMost(bits, 4)
            formula.atMost([-bit for bit in bits], len(bits) - 4)
        else:
            prefix = json.loads((ref.EQUAL / "runs/R1/base_prefixes.json").read_text())
            cutoff = int(prefix["source"]["last_selected_mask"])
            upper = [formula.true if cutoff & (1 << bit) else formula.false
                     for bit in range(len(bits) - 1, -1, -1)]
            formula.lexLeq(list(reversed(bits)), upper)
    for index in range(len(selectors) - 1):
        formula.lexLeq(list(reversed(selectors[index])),
                       list(reversed(selectors[index + 1])))
    target_bits, target_selectors = encode_target_mux(formula, xs)
    for bit, literal in enumerate(target_bits):
        literals[("target", bit)] = literal
    for index in range(len(chain)):
        for bit in range(ref.DEGREE):
            literals[("t%d" % index, bit)] = formula.newVar()
    for literal in prog.emitCnf(roots, literals, formula):
        formula.assertZero(literal)
    return formula, selectors, target_selectors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix(".json").exists():
        parser.error("refusing to overwrite formula or receipt")
    started = time.perf_counter()
    xs = target_lifts()
    prog, roots, leaves, chain = source.build_ir(args.policy, "m6", xs[0])
    formula, _, choice = encode(args.policy, prog, roots, leaves, chain, xs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula.writeDimacs(args.out)
    receipt = {
        "schema": "ecc2k130-equalb-four-lift-m6-xcnf-v1",
        "status": "FORMULA_BUILT",
        "candidate_id": None,
        "policy": args.policy,
        "ordinary_query_index": 0,
        "target_x_choices": [str(x) for x in xs],
        "target_selector_variables": list(choice),
        "target_selector_order": "j=s0+2*s1",
        "actual_usable_points_B": 11743888,
        "summands": 6,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "formula_sha256": ref.sha(args.out),
        "builder_sha256": ref.sha(Path(__file__)),
        "parent_builder_sha256": ref.sha(PARENT / "build_formula.py"),
        "parent_field_sha256": ref.sha(PARENT / "field.py"),
        "parent_torsion_lifts_sha256": ref.sha(LIFTS),
        "public_points_sha256": ref.sha(PUBLIC),
        "input_config_sha256": ref.sha(ref.EQUAL / "CONFIG.json"),
        "input_prefix_sha256": ref.sha(ref.EQUAL / "runs/R1/base_prefixes.json"),
        "codegen": {name: ref.sha(source.CODEGEN / name)
                    for name in ("build.py", "ir.py", "cnf.py")},
        "stats": formula.stats(),
        "ir_operations": prog.opCount(roots),
        "build_wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_bytes(),
    }
    args.out.with_suffix(".json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("policy", "formula_sha256", "stats", "ir_operations",
                       "build_wall_seconds", "peak_rss_bytes")}, sort_keys=True))


if __name__ == "__main__":
    main()
