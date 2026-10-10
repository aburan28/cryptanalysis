#!/usr/bin/env python3
"""Exact equal-B source-leaf XCNF and target-first six-summand S3 circuit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
import field as f  # noqa: E402; resolve this experiment's field.py first
sys.path.insert(0, str(CODEGEN))

import build  # noqa: E402
import cnf  # noqa: E402
import ir  # noqa: E402


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def target_x(query_index: int) -> int:
    if not 0 <= query_index < 16:
        raise ValueError("the first 16 ordinary public queries are the frozen pilot")
    path = f.EQUAL / "runs/R1/point16/public_points.json"
    public = read(path)
    return int(public["first_16_public_queries"][query_index]["source"][0])


def add_leaf(prog, index: int, basis: list[int], ones: int, trace_row: int):
    n = len(basis)
    selectors = [prog.addInput("s%d" % index, bit) for bit in range(n)]
    x = [prog.addInput("x%d" % index, bit) for bit in range(f.DEGREE)]
    z = [prog.addInput("z%d" % index, bit) for bit in range(f.DEGREE)]
    w = build.linearMapIr(prog, selectors, f.matrix_rows(basis), 4)
    u = build.linearMapIr(
        prog, selectors, f.matrix_rows([f.halftrace(word) for word in basis]), 4)
    wz = build.pbMulIr(prog, w, z, f.DEGREE, [13, 2, 1], 8)
    xp = list(x)
    xp[0] = prog.xor(xp[0], ones)
    ux = build.pbMulIr(prog, u, xp, f.DEGREE, [13, 2, 1], 8)
    roots = [prog.xor(wz[bit], ones if bit == 0 else None)
             for bit in range(f.DEGREE)]
    roots.extend(prog.xor(ux[bit], ones if bit == 0 else None)
                 for bit in range(f.DEGREE))
    roots.append(prog.xorList(
        [z[bit] for bit in range(f.DEGREE) if (trace_row >> bit) & 1]))
    return selectors, x, z, roots


def s3_roots(prog, a, b, c, ones):
    """(ac+b(a+c))^2+b(ac)+1=0 on y^2+xy=x^3+1."""
    ac = build.pbMulIr(prog, a, c, f.DEGREE, [13, 2, 1], 8)
    a_plus_c = [prog.xor(u, v) for u, v in zip(a, c)]
    b_sum = build.pbMulIr(prog, b, a_plus_c, f.DEGREE, [13, 2, 1], 8)
    squared = build.pbSqrIr(
        prog, [prog.xor(u, v) for u, v in zip(ac, b_sum)],
        f.DEGREE, [13, 2, 1])
    bac = build.pbMulIr(prog, b, ac, f.DEGREE, [13, 2, 1], 8)
    return [prog.xor(prog.xor(squared[bit], bac[bit]),
                     ones if bit == 0 else None)
            for bit in range(f.DEGREE)]


def build_ir(policy: str, mode: str, x_target: int | None):
    basis = f.words(policy)
    if any(f.trace(word) != (1 if policy == "normal4_source" else 0)
           for word in basis):
        raise ValueError("parameter basis trace mismatch")
    if policy == "normal4_source" and len(basis) != 131:
        raise ValueError("normal4 basis width changed")
    if policy == "w24_source" and len(basis) != 24:
        raise ValueError("W24 basis width changed")
    prog = ir.Prog()
    one = prog.addInput("one", 0)
    leaves = []
    roots = []
    for index in range(6 if mode == "m6" else 1):
        selectors, x, z, leaf_roots = add_leaf(
            prog, index, basis, one, f.trace_row())
        leaves.append({"selectors": selectors, "x": x, "z": z})
        roots.extend(leaf_roots)
    chain = []
    if mode == "m6":
        if x_target is None:
            raise ValueError("m6 requires a public target x")
        target = [prog.addInput("target", bit) for bit in range(f.DEGREE)]
        chain = [[prog.addInput("t%d" % index, bit)
                  for bit in range(f.DEGREE)] for index in range(5)]
        left = target
        for index in range(5):
            roots.extend(s3_roots(prog, left, leaves[index]["x"],
                                  chain[index], one))
            left = chain[index]
        roots.extend(prog.xor(left[bit], leaves[5]["x"][bit])
                     for bit in range(f.DEGREE))
    return prog, roots, leaves, chain


def encode(prog, roots, leaves, chain, policy, x_target):
    formula = cnf.Cnf()
    literals = {("one", 0): formula.true}
    selected = []
    for index, leaf in enumerate(leaves):
        bits = [formula.newVar() for _ in leaf["selectors"]]
        selected.append(bits)
        for bit, literal in enumerate(bits):
            literals[("s%d" % index, bit)] = literal
        for name in ("x", "z"):
            for bit in range(f.DEGREE):
                literals[("%s%d" % (name, index), bit)] = formula.newVar()
        if policy == "normal4_source":
            formula.atMost(bits, 4)
            formula.atMost([-bit for bit in bits], len(bits) - 4)
        else:
            receipt = read(f.EQUAL / "runs/R1/base_prefixes.json")
            last = int(receipt["source"]["last_selected_mask"])
            upper = [formula.true if last & (1 << bit) else formula.false
                     for bit in range(len(bits) - 1, -1, -1)]
            formula.lexLeq(list(reversed(bits)), upper)
    for index in range(len(selected) - 1):
        formula.lexLeq(list(reversed(selected[index])),
                       list(reversed(selected[index + 1])))
    if x_target is not None:
        for bit in range(f.DEGREE):
            literals[("target", bit)] = (
                formula.true if x_target & (1 << bit) else formula.false)
        for index in range(len(chain)):
            for bit in range(f.DEGREE):
                literals[("t%d" % index, bit)] = formula.newVar()
    for literal in prog.emitCnf(roots, literals, formula):
        formula.assertZero(literal)
    return formula, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("w24_source", "normal4_source"),
                        required=True)
    parser.add_argument("--mode", choices=("leaf", "m6"), required=True)
    parser.add_argument("--query-index", type=int, default=0)
    parser.add_argument("--target-x", type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite an existing formula")
    started = time.perf_counter()
    x_target = None
    if args.mode == "m6":
        x_target = (args.target_x if args.target_x is not None
                    else target_x(args.query_index))
    prog, roots, leaves, chain = build_ir(args.policy, args.mode, x_target)
    formula, selected = encode(prog, roots, leaves, chain,
                               args.policy, x_target)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula.writeDimacs(args.out)
    receipt = {
        "schema": "ecc2k130-equalb-source-leaf-circuit-v1",
        "status": "FORMULA_BUILT",
        "candidate_id": None,
        "policy": args.policy,
        "mode": args.mode,
        "query_index": args.query_index if args.mode == "m6"
                       and args.target_x is None else None,
        "target_x": str(x_target) if x_target is not None else None,
        "summands": 6 if args.mode == "m6" else 1,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "actual_usable_points_B": 11743888,
        "formula_sha256": f.sha(args.out),
        "build_source_sha256": f.sha(Path(__file__)),
        "field_source_sha256": f.sha(HERE / "field.py"),
        "input_config_sha256": f.sha(f.EQUAL / "CONFIG.json"),
        "input_prefix_sha256": f.sha(f.EQUAL / "runs/R1/base_prefixes.json"),
        "public_points_sha256": f.sha(f.EQUAL / "runs/R1/point16/public_points.json"),
        "codegen": {name: f.sha(CODEGEN / name)
                    for name in ("build.py", "ir.py", "cnf.py")},
        "stats": formula.stats(),
        "ir_operations": prog.opCount(roots),
        "build_wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_bytes(),
        "selector_width": len(selected[0]),
    }
    args.out.with_suffix(".json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
