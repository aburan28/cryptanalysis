#!/usr/bin/env python3
"""Check selector-weighted leaf circuits against direct GF(2^131) arithmetic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import sys

import bilinear


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(bilinear.PARENT))
import distinct  # noqa: E402


ref = bilinear.ref


def input_values(mask, x, z):
    values = {("one", 0): 1}
    for name, word, width in (("s0", mask, 24), ("x0", x, ref.DEGREE),
                              ("z0", z, ref.DEGREE)):
        values.update({(name, bit): (word >> bit) & 1
                       for bit in range(width)})
    return values


def expected_roots(mask, x, z, alpha, basis, halves):
    w = ref.parameter(basis, mask)
    u = ref.parameter(halves, mask)
    first = ref.multiply(w, z) ^ 1
    second = ref.multiply(u, x ^ alpha) ^ alpha
    trace = ref.trace(ref.multiply(alpha, z))
    return ([(first >> bit) & 1 for bit in range(ref.DEGREE)]
            + [(second >> bit) & 1 for bit in range(ref.DEGREE)]
            + [trace])


def cases_for(policy, cfg, witness):
    rng = random.Random(cfg["equivalence_seed"] + (0 if policy == "source" else 1))
    cases = [(0, 0, 0),
             ((1 << 24) - 1, ref.MASK, ref.MASK)]
    cases.extend((1 << bit, rng.getrandbits(ref.DEGREE),
                  rng.getrandbits(ref.DEGREE)) for bit in range(24))
    alpha, _ = ref.coefficients(policy)
    for leaf in witness["policies"][policy]["leaves"]:
        mask = leaf["mask"]
        x, z, _ = ref.leaf(mask, alpha)
        cases.append((mask, x, z))
    cases.extend((rng.getrandbits(24), rng.getrandbits(ref.DEGREE),
                  rng.getrandbits(ref.DEGREE))
                 for _ in range(cfg["equivalence_random_cases_per_curve"]))
    return cases


def main():
    cfg = ref.read(HERE / "CONFIG.json")
    parent_cfg = distinct.config()
    witness = distinct.witness(parent_cfg)
    if (ref.sha(bilinear.PARENT / "CONFIG.json")
            != cfg["parent_config_sha256"]
            or ref.sha(bilinear.PARENT / "runs/R1/witness.json")
            != cfg["parent_witness_sha256"]
            or cfg["variants"] != list(bilinear.VARIANTS)):
        raise ValueError("parent or variant configuration changed")
    basis = ref.basis()
    halves = [ref.halftrace(word) for word in basis]
    rows = {}
    for policy in cfg["policies"]:
        alpha, _ = ref.coefficients(policy)
        programs = {}
        for variant in ("baseline", *cfg["variants"]):
            prog = bilinear.finite.ir.Prog()
            one = prog.addInput("one", 0)
            leaf, roots = (bilinear.finite.add_leaf(
                prog, 0, basis, alpha, one)
                if variant == "baseline" else bilinear.add_leaf(
                    prog, 0, basis, alpha, one, variant))
            if len(roots) != 2 * ref.DEGREE + 1 or len(leaf["selectors"]) != 24:
                raise ValueError("leaf equation/input count changed")
            programs[variant] = (prog, roots)
        cases = cases_for(policy, cfg, witness)
        for index, (mask, x, z) in enumerate(cases):
            want = expected_roots(mask, x, z, alpha, basis, halves)
            values = input_values(mask, x, z)
            for variant, (prog, roots) in programs.items():
                got = prog.evaluate(values, roots)
                if got != want:
                    bit = next(bit for bit, pair in enumerate(zip(got, want))
                               if pair[0] != pair[1])
                    raise ArithmeticError(
                        f"{policy}/{variant} case {index} root {bit} differs")
        raw = json.dumps(cases, separators=(",", ":")).encode()
        rows[policy] = {
            "cases": len(cases),
            "cases_sha256": hashlib.sha256(raw).hexdigest(),
            "root_equations_per_case": 2 * ref.DEGREE + 1,
            "ir_operations": {name: prog.opCount(roots)
                              for name, (prog, roots) in programs.items()},
            "status": "PASS_DIRECT_FIELD_EQUIVALENCE",
        }
    result = {
        "schema": "ecc2k130-263-bilinear-equivalence-v1",
        "status": "PASS_BOTH_CURVES_AND_VARIANTS",
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "builder_sha256": ref.sha(HERE / "bilinear.py"),
        "equivalence_source_sha256": ref.sha(Path(__file__)),
        "parent_witness_sha256": cfg["parent_witness_sha256"],
        "seed": cfg["equivalence_seed"],
        "policies": rows,
    }
    path = HERE / "runs/R1/equivalence.json"
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(rows, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
