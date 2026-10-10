#!/usr/bin/env python3
"""Build exact Q1420 source and descendant W24 six-summand XCNFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time

import field as ref


sys.path.insert(0, str(ref.CODEGEN))
import build  # noqa: E402
import cnf  # noqa: E402
import ir  # noqa: E402


POLICIES = ("source", "descendant_native")


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def constant(prog, one, value):
    return [one if (value >> bit) & 1 else None for bit in range(ref.DEGREE)]


def add_leaf(prog, index, basis, alpha, one):
    selectors = [prog.addInput("s%d" % index, bit) for bit in range(24)]
    x = [prog.addInput("x%d" % index, bit) for bit in range(ref.DEGREE)]
    z = [prog.addInput("z%d" % index, bit) for bit in range(ref.DEGREE)]
    w = build.linearMapIr(prog, selectors, ref.matrix_rows(basis), 4)
    u = build.linearMapIr(
        prog, selectors,
        ref.matrix_rows([ref.halftrace(word) for word in basis]), 4)
    wz = build.pbMulIr(prog, w, z, ref.DEGREE, [13, 2, 1], 8)
    x_plus_alpha = [prog.xor(x[bit], one if (alpha >> bit) & 1 else None)
                    for bit in range(ref.DEGREE)]
    ux = build.pbMulIr(prog, u, x_plus_alpha,
                       ref.DEGREE, [13, 2, 1], 8)
    roots = [prog.xor(wz[bit], one if bit == 0 else None)
             for bit in range(ref.DEGREE)]
    roots.extend(prog.xor(ux[bit], one if (alpha >> bit) & 1 else None)
                 for bit in range(ref.DEGREE))
    row = ref.trace_row(alpha)
    roots.append(prog.xorList([z[bit] for bit in range(ref.DEGREE)
                               if (row >> bit) & 1]))
    return {"selectors": selectors, "x": x, "z": z}, roots


def s3_roots(prog, a, middle, c, b, one):
    """(ac+middle*(a+c))^2+middle*ac+b=0."""
    ac = build.pbMulIr(prog, a, c, ref.DEGREE, [13, 2, 1], 8)
    a_plus_c = [prog.xor(left, right) for left, right in zip(a, c)]
    middle_sum = build.pbMulIr(prog, middle, a_plus_c,
                               ref.DEGREE, [13, 2, 1], 8)
    squared = build.pbSqrIr(
        prog, [prog.xor(left, right) for left, right in zip(ac, middle_sum)],
        ref.DEGREE, [13, 2, 1])
    middle_ac = build.pbMulIr(prog, middle, ac,
                              ref.DEGREE, [13, 2, 1], 8)
    return [prog.xor(prog.xor(squared[bit], middle_ac[bit]),
                     one if (b >> bit) & 1 else None)
            for bit in range(ref.DEGREE)]


def build_ir(policy, mode):
    if policy not in POLICIES or mode not in ("leaf", "m6"):
        raise ValueError("unknown circuit policy or mode")
    basis = ref.basis()
    if len(basis) != 24 or any(ref.trace(word) != 0 for word in basis):
        raise ArithmeticError("W24 basis changed")
    alpha, b = ref.coefficients(policy)
    prog = ir.Prog()
    one = prog.addInput("one", 0)
    leaves, roots = [], []
    for index in range(6 if mode == "m6" else 1):
        leaf, equations = add_leaf(prog, index, basis, alpha, one)
        leaves.append(leaf)
        roots.extend(equations)
    chain = []
    if mode == "m6":
        chain = [[prog.addInput("t%d" % index, bit)
                  for bit in range(ref.DEGREE)] for index in range(4)]
        target = [prog.addInput("target", bit) for bit in range(ref.DEGREE)]
        for pair in range(3):
            roots.extend(s3_roots(
                prog, leaves[2*pair]["x"], leaves[2*pair+1]["x"],
                chain[pair], b, one))
        roots.extend(s3_roots(prog, chain[0], chain[1], chain[3], b, one))
        roots.extend(s3_roots(prog, chain[3], chain[2], target, b, one))
    return prog, roots, leaves, chain


def target_lifts(policy):
    config = ref.read(ref.HERE / "CONFIG.json")
    receipt = ref.read(ref.HERE / "runs/R1/lifts.json")
    verification = ref.read(ref.HERE / "runs/R1/verification.json")
    if (verification["status"]
            != "PASS_TWO_CURVES_FOUR_LIFTS_AND_M6_CONTROLS"
            or verification["lifts_sha256"]
            != ref.sha(ref.HERE / "runs/R1/lifts.json")
            or receipt["status"] != "PASS_EXACT_FOUR_LIFTS_AND_TRANSPORT"
            or receipt["primary_workload_id"] != config["primary_workload_id"]
            or receipt["config_sha256"] != ref.sha(ref.HERE / "CONFIG.json")
            or receipt[policy]["public_query"] != ref.read(
                ref.INPUT / "primary_workload.json")["targets"][0][
                    "source" if policy == "source" else "descendant"]):
        raise ValueError("four-lift input is not independently replayed")
    xs = [int(point[0]) for point in receipt[policy]["raw_target_lifts"]]
    if len(xs) != 4 or len(set(xs)) != 4:
        raise ValueError("four distinct raw target x coordinates required")
    return xs


def target_mux(formula, xs):
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
    return bits, [s0, s1]


def encode(policy, prog, roots, leaves, chain, xs):
    config = ref.read(ref.HERE / "CONFIG.json")
    formula = cnf.Cnf()
    literals = {("one", 0): formula.true}
    selected = []
    cutoff = config[policy + "_last_selected_mask"]
    for index, leaf in enumerate(leaves):
        bits = [formula.newVar() for _ in leaf["selectors"]]
        selected.append(bits)
        for bit, literal in enumerate(bits):
            literals[("s%d" % index, bit)] = literal
        for name in ("x", "z"):
            for bit in range(ref.DEGREE):
                literals[("%s%d" % (name, index), bit)] = formula.newVar()
        if cutoff < (1 << 24)-1:
            upper = [formula.true if cutoff & (1 << bit) else formula.false
                     for bit in range(23, -1, -1)]
            formula.lexLeq(list(reversed(bits)), upper)
    for index in range(len(selected)-1):
        formula.lexLeq(list(reversed(selected[index])),
                       list(reversed(selected[index+1])))
    choice = None
    if xs is not None:
        target_bits, choice = target_mux(formula, xs)
        for bit, literal in enumerate(target_bits):
            literals[("target", bit)] = literal
        for index in range(len(chain)):
            for bit in range(ref.DEGREE):
                literals[("t%d" % index, bit)] = formula.newVar()
    for literal in prog.emitCnf(roots, literals, formula):
        formula.assertZero(literal)
    return formula, choice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--mode", choices=("leaf", "m6"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix(".json").exists():
        parser.error("refusing to overwrite formula or receipt")
    started = time.perf_counter()
    config = ref.read(ref.HERE / "CONFIG.json")
    base = ref.read(ref.INPUT / "base_selection.json")
    if (ref.sha(ref.INPUT / "base_selection.json")
            != config["base_selection_sha256"]
            or base[args.policy]["selected_mask_stream_sha256"]
            != config["selected_mask_stream_sha256"][args.policy]):
        raise ValueError("base identity changed")
    xs = target_lifts(args.policy) if args.mode == "m6" else None
    prog, roots, leaves, chain = build_ir(args.policy, args.mode)
    formula, choice = encode(args.policy, prog, roots, leaves, chain, xs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula.writeDimacs(args.out)
    receipt = {
        "schema": "ecc2k130-263-native-w24-m6-xcnf-v1",
        "status": "FORMULA_BUILT",
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "policy": args.policy,
        "mode": args.mode,
        "primary_workload_id": config["primary_workload_id"],
        "actual_usable_points_B": config["selected_usable_points_B_each"],
        "summands": 6 if args.mode == "m6" else 1,
        "normalized_b": ref.coefficients(args.policy)[1],
        "alpha": ref.coefficients(args.policy)[0],
        "target_x_choices": [str(x) for x in xs] if xs is not None else None,
        "target_selector_variables": choice,
        "target_selector_order": "j=s0+2*s1" if choice else None,
        "tree": "pair(0,1),pair(2,3),pair(4,5),pair(pair01,pair23),target(pair0123,pair45)",
        "formula_sha256": ref.sha(args.out),
        "builder_sha256": ref.sha(Path(__file__)),
        "field_source_sha256": ref.sha(ref.HERE / "field.py"),
        "config_sha256": ref.sha(ref.HERE / "CONFIG.json"),
        "base_selection_sha256": ref.sha(ref.INPUT / "base_selection.json"),
        "lifts_sha256": ref.sha(ref.HERE / "runs/R1/lifts.json") if xs else None,
        "verification_sha256": ref.sha(
            ref.HERE / "runs/R1/verification.json") if xs else None,
        "codegen": {name: ref.sha(ref.CODEGEN / name)
                    for name in ("build.py", "ir.py", "cnf.py")},
        "stats": formula.stats(),
        "ir_operations": prog.opCount(roots),
        "build_wall_seconds": time.perf_counter()-started,
        "peak_rss_bytes": peak_bytes(),
    }
    args.out.with_suffix(".json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "policy", "mode", "formula_sha256",
                       "stats", "build_wall_seconds", "peak_rss_bytes")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
