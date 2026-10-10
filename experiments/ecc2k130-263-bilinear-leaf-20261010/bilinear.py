#!/usr/bin/env python3
"""Exact selector-weighted W24 leaf equations in the projective S3 circuit."""

from __future__ import annotations

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-distinct-s3-control-20261010"
SAT = HERE.parent / "ecc2k130-263-projective-s3-sat-20261010"
sys.path.insert(0, str(SAT))
import build_control as control  # noqa: E402


projective = control.parent
finite = control.finite
ref = control.ref
VARIANTS = ("wz_only", "both_products")


def sparse_basis_product(prog, word, basis_word, shift):
    """Multiply by the W24 basis word t^shift + trace(t^shift)."""
    if basis_word & ~((1 << shift) | 1) or not basis_word & (1 << shift):
        raise ValueError("W24 basis is not the pinned sparse monomial")
    wide = [None] * shift + list(word)
    shifted = finite.build.pbReduceIr(
        prog, wide, ref.DEGREE, [13, 2, 1])
    if basis_word & 1:
        return [prog.xor(a, b) for a, b in zip(shifted, word)]
    return shifted


def constant_product(prog, word, constant):
    """Apply the exact multiplication-by-constant GF(2) linear map."""
    columns = [ref.multiply(1 << bit, constant)
               for bit in range(ref.DEGREE)]
    return finite.build.linearMapIr(
        prog, word, ref.matrix_rows(columns), 4)


def selector_weighted_product(prog, selectors, word, constants, method):
    if len(selectors) != 24 or len(constants) != 24:
        raise ValueError("W24 selector/constant count changed")
    terms = [[] for _ in range(ref.DEGREE)]
    for index, (selector, constant) in enumerate(zip(selectors, constants)):
        if method == "sparse":
            product = sparse_basis_product(prog, word, constant, index + 1)
        elif method == "linear":
            product = constant_product(prog, word, constant)
        else:
            raise ValueError("unknown product implementation")
        for bit, item in enumerate(product):
            terms[bit].append(prog.andOp(selector, item))
    return [prog.xorList(row) for row in terms]


def add_leaf(prog, index, basis, alpha, one, variant):
    if variant not in VARIANTS:
        raise ValueError("unknown bilinear leaf variant")
    selectors = [prog.addInput("s%d" % index, bit) for bit in range(24)]
    x = [prog.addInput("x%d" % index, bit) for bit in range(ref.DEGREE)]
    z = [prog.addInput("z%d" % index, bit) for bit in range(ref.DEGREE)]
    wz = selector_weighted_product(prog, selectors, z, basis, "sparse")
    x_plus_alpha = [prog.xor(x[bit], one if (alpha >> bit) & 1 else None)
                    for bit in range(ref.DEGREE)]
    halves = [ref.halftrace(word) for word in basis]
    if variant == "both_products":
        ux = selector_weighted_product(
            prog, selectors, x_plus_alpha, halves, "linear")
    else:
        u = finite.build.linearMapIr(
            prog, selectors, ref.matrix_rows(halves), 4)
        ux = finite.build.pbMulIr(
            prog, u, x_plus_alpha, ref.DEGREE, [13, 2, 1], 8)
    roots = [prog.xor(wz[bit], one if bit == 0 else None)
             for bit in range(ref.DEGREE)]
    roots.extend(prog.xor(ux[bit], one if (alpha >> bit) & 1 else None)
                 for bit in range(ref.DEGREE))
    row = ref.trace_row(alpha)
    roots.append(prog.xorList([z[bit] for bit in range(ref.DEGREE)
                               if (row >> bit) & 1]))
    return {"selectors": selectors, "x": x, "z": z}, roots


def build_ir(policy, variant):
    if policy not in finite.POLICIES or variant not in VARIANTS:
        raise ValueError("unknown curve or variant")
    basis = ref.basis()
    if len(basis) != 24 or any(ref.trace(word) != 0 for word in basis):
        raise ArithmeticError("W24 basis changed")
    alpha, b = ref.coefficients(policy)
    prog = finite.ir.Prog()
    one = prog.addInput("one", 0)
    leaves, roots = [], []
    for index in range(6):
        leaf, equations = add_leaf(prog, index, basis, alpha, one, variant)
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
        roots.extend(projective.projective_s3_roots(
            prog, (leaves[2 * pair]["x"], None),
            (leaves[2 * pair + 1]["x"], None), chain[pair], b, one))
    roots.extend(projective.projective_s3_roots(
        prog, chain[0], chain[1], chain[3], b, one))
    roots.extend(projective.projective_s3_roots(
        prog, chain[3], chain[2], (target, None), b, one))
    return prog, roots, leaves, chain
