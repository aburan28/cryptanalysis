#!/usr/bin/env python3
"""Build Q1420 six-summand native-XOR circuits with projective S3 nodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-native-w24-m6-20261010"
sys.path.insert(0, str(PARENT))
import build_formula as finite  # noqa: E402
import field as ref  # noqa: E402


POLICIES = finite.POLICIES


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def multiply(prog, left, right):
    return finite.build.pbMulIr(prog, left, right, ref.DEGREE, [13, 2, 1], 8)


def gate(prog, word, flag):
    """A None flag denotes a known finite point (multiplication by one)."""
    return word if flag is None else [prog.andOp(bit, flag) for bit in word]


def combined_flag(prog, *flags):
    used = [flag for flag in flags if flag is not None]
    if not used:
        return None
    result = used[0]
    for flag in used[1:]:
        result = prog.andOp(result, flag)
    return result


def projective_s3_roots(prog, left, middle, right, b, one):
    a, za = left
    c, zc = middle
    d, zd = right
    if za is None and zc is None:
        ac = multiply(prog, a, c)
        a_plus_c = [prog.xor(x, y) for x, y in zip(a, c)]
        dsum = multiply(prog, d, a_plus_c)
        pair = [prog.xor(x, y) for x, y in zip(gate(prog, ac, zd), dsum)]
        triple = multiply(prog, ac, d)
        product_z = zd
    else:
        ac = multiply(prog, a, c)
        cd = multiply(prog, c, d)
        da = multiply(prog, d, a)
        terms = [gate(prog, ac, zd), gate(prog, cd, za),
                 gate(prog, da, zc)]
        pair = [prog.xorList([term[bit] for term in terms])
                for bit in range(ref.DEGREE)]
        triple = multiply(prog, ac, d)
        product_z = combined_flag(prog, za, zc, zd)
    squared = finite.build.pbSqrIr(prog, pair, ref.DEGREE, [13, 2, 1])
    gated_triple = gate(prog, triple, product_z)
    b_bit = one if product_z is None else prog.andOp(one, product_z)
    return [prog.xorList((squared[bit], gated_triple[bit],
                          b_bit if (b >> bit) & 1 else None))
            for bit in range(ref.DEGREE)]


def build_ir(policy):
    if policy not in POLICIES:
        raise ValueError("unknown W24 policy")
    basis = ref.basis()
    alpha, b = ref.coefficients(policy)
    prog = finite.ir.Prog()
    one = prog.addInput("one", 0)
    leaves, roots = [], []
    for index in range(6):
        leaf, equations = finite.add_leaf(prog, index, basis, alpha, one)
        leaves.append(leaf)
        roots.extend(equations)
    chain = []
    for index in range(4):
        x = [prog.addInput("t%d" % index, bit) for bit in range(ref.DEGREE)]
        z = prog.addInput("f", index)
        chain.append((x, z))
        nonfinite = prog.xor(z, one)
        for bit in range(ref.DEGREE):
            canonical = prog.xor(x[bit], one if bit == 0 else None)
            roots.append(prog.andOp(nonfinite, canonical))
    target = [prog.addInput("target", bit) for bit in range(ref.DEGREE)]
    for pair in range(3):
        roots.extend(projective_s3_roots(
            prog, (leaves[2*pair]["x"], None),
            (leaves[2*pair+1]["x"], None), chain[pair], b, one))
    roots.extend(projective_s3_roots(
        prog, chain[0], chain[1], chain[3], b, one))
    roots.extend(projective_s3_roots(
        prog, chain[3], chain[2], (target, None), b, one))
    return prog, roots, leaves, chain


def encode(policy, prog, roots, leaves, chain, xs):
    config = ref.read(HERE / "CONFIG.json")
    formula = finite.cnf.Cnf()
    literals = {("one", 0): formula.true}
    selectors = []
    cutoff = config[policy + "_last_selected_mask"]
    for index, leaf in enumerate(leaves):
        bits = [formula.newVar() for _ in leaf["selectors"]]
        selectors.append(bits)
        for bit, literal in enumerate(bits):
            literals[("s%d" % index, bit)] = literal
        for name in ("x", "z"):
            for bit in range(ref.DEGREE):
                literals[("%s%d" % (name, index), bit)] = formula.newVar()
        if cutoff < (1 << 24)-1:
            upper = [formula.true if cutoff & (1 << bit) else formula.false
                     for bit in range(23, -1, -1)]
            formula.lexLeq(list(reversed(bits)), upper)
    for index in range(5):
        formula.lexLeq(list(reversed(selectors[index])),
                       list(reversed(selectors[index+1])))
    target_bits, choice = finite.target_mux(formula, xs)
    for bit, literal in enumerate(target_bits):
        literals[("target", bit)] = literal
    for index in range(4):
        for bit in range(ref.DEGREE):
            literals[("t%d" % index, bit)] = formula.newVar()
        literals[("f", index)] = formula.newVar()
    for literal in prog.emitCnf(roots, literals, formula):
        formula.assertZero(literal)
    return formula, choice


def check_inputs(policy):
    config = ref.read(HERE / "CONFIG.json")
    pins = {
        PARENT / "build_formula.py": "parent_builder_sha256",
        PARENT / "field.py": "parent_field_sha256",
        PARENT / "CONFIG.json": "parent_config_sha256",
        PARENT / "runs/R1/lifts.json": "parent_lifts_sha256",
        PARENT / "runs/R1/verification.json": "parent_verification_sha256",
        ref.INPUT / "primary_workload.json": "primary_workload_sha256",
    }
    if any(ref.sha(path) != config[key] for path, key in pins.items()):
        raise ValueError("parent code or frozen inputs changed")
    small = ref.read(HERE / "runs/R1/small_field.json")
    boolean = ref.read(HERE / "runs/R1/exceptional_boolean.json")
    if (small["status"] != "PASS_EXHAUSTIVE_GROUP_LAW_EQUIVALENCE"
            or boolean["status"]
            != "PASS_SOURCE_AND_DESCENDANT_EXCEPTIONAL_BOOLEAN_CONTROLS"):
        raise ValueError("precommitted projective controls have not passed")
    return finite.target_lifts(policy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix(".json").exists():
        parser.error("refusing to overwrite formula or receipt")
    started = time.perf_counter()
    xs = check_inputs(args.policy)
    config = ref.read(HERE / "CONFIG.json")
    prog, roots, leaves, chain = build_ir(args.policy)
    formula, choice = encode(args.policy, prog, roots, leaves, chain, xs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula.writeDimacs(args.out)
    receipt = {
        "schema": "ecc2k130-263-projective-s3-xcnf-v1",
        "status": "FORMULA_BUILT",
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "policy": args.policy,
        "primary_workload_id": config["primary_workload_id"],
        "actual_usable_points_B": config["actual_usable_points_B_each"],
        "summands": 6,
        "projective_intermediates": 4,
        "target_x_choices": [str(value) for value in xs],
        "target_selector_variables": choice,
        "target_selector_order": "j=s0+2*s1",
        "formula_sha256": ref.sha(args.out),
        "builder_sha256": ref.sha(Path(__file__)),
        "parent_builder_sha256": ref.sha(PARENT / "build_formula.py"),
        "parent_field_sha256": ref.sha(PARENT / "field.py"),
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "parent_lifts_sha256": ref.sha(PARENT / "runs/R1/lifts.json"),
        "small_field_sha256": ref.sha(HERE / "runs/R1/small_field.json"),
        "exceptional_boolean_sha256": ref.sha(
            HERE / "runs/R1/exceptional_boolean.json"),
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
                      ("policy", "status", "formula_sha256", "stats",
                       "build_wall_seconds", "peak_rss_bytes")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
