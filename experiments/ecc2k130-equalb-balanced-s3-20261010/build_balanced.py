#!/usr/bin/env python3
"""Build the equal-B source m6 four-lift XCNF with a balanced S3 pair tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/ecc2k130-equalb-four-lift-pdp-20261010"
sys.path.insert(0, str(PARENT))

import build_four_lift as gate  # noqa: E402


source = gate.source
ref = gate.ref
POLICIES = gate.POLICIES


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def build_ir(policy: str):
    basis = ref.words(policy)
    if policy not in POLICIES:
        raise ValueError("unknown source policy")
    if (len(basis) != (131 if policy == "normal4_source" else 24)
            or any(ref.trace(word) != (1 if policy == "normal4_source" else 0)
                   for word in basis)):
        raise ValueError("source policy basis changed")
    prog = source.ir.Prog()
    one = prog.addInput("one", 0)
    leaves = []
    roots = []
    for index in range(6):
        selectors, x, z, leaf_roots = source.add_leaf(
            prog, index, basis, one, ref.trace_row())
        leaves.append({"selectors": selectors, "x": x, "z": z})
        roots.extend(leaf_roots)
    chain = [[prog.addInput("t%d" % index, bit)
              for bit in range(ref.DEGREE)] for index in range(4)]
    target = [prog.addInput("target", bit) for bit in range(ref.DEGREE)]
    for pair in range(3):
        roots.extend(source.s3_roots(
            prog, leaves[2*pair]["x"], leaves[2*pair+1]["x"],
            chain[pair], one))
    roots.extend(source.s3_roots(prog, chain[0], chain[1], chain[3], one))
    roots.extend(source.s3_roots(prog, chain[3], chain[2], target, one))
    return prog, roots, leaves, chain


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix(".json").exists():
        parser.error("refusing to overwrite formula or receipt")
    started = time.perf_counter()
    xs = gate.target_lifts()
    prog, roots, leaves, chain = build_ir(args.policy)
    formula, _, choice = gate.encode(args.policy, prog, roots, leaves, chain, xs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula.writeDimacs(args.out)
    receipt = {
        "schema": "ecc2k130-equalb-balanced-s3-m6-xcnf-v1",
        "status": "FORMULA_BUILT",
        "candidate_id": None,
        "policy": args.policy,
        "ordinary_query_index": 0,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "actual_usable_points_B": 11743888,
        "summands": 6,
        "intermediate_x_count": 4,
        "tree": "pair(0,1),pair(2,3),pair(4,5),pair(pair01,pair23),target(pair0123,pair45)",
        "target_x_choices": [str(x) for x in xs],
        "target_selector_variables": list(choice),
        "target_selector_order": "j=s0+2*s1",
        "formula_sha256": ref.sha(args.out),
        "builder_sha256": ref.sha(Path(__file__)),
        "four_lift_builder_sha256": ref.sha(PARENT / "build_four_lift.py"),
        "leaf_builder_sha256": ref.sha(gate.PARENT / "build_formula.py"),
        "field_source_sha256": ref.sha(gate.PARENT / "field.py"),
        "parent_torsion_lifts_sha256": ref.sha(gate.LIFTS),
        "public_points_sha256": ref.sha(gate.PUBLIC),
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
