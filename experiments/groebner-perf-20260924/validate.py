#!/usr/bin/env python3
"""Differential checks against Sage/Singular plus exact Boolean certificates."""
import argparse
import json
import random
import subprocess
from pathlib import Path

from benchmark import verify, digest
from boolean_f5b import BooleanF5B
from sage.all import GF, PolynomialRing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--m4ri", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(20260924)
    cases = [(2, [[0, 3]]), (2, []), (2, [[0]]), (2, [[1], [0, 1]]),
             (3, [[3, 4]]), (3, [[0, 7]])]
    for n in range(1, 7):
        for _ in range(20):
            generators = [sorted({rng.randrange(1 << n)
                                   for _ in range(rng.randrange(1, 9))})
                          for _ in range(rng.randrange(1, n + 3))]
            cases.append((n, generators))
    runs = 0
    for n, generators in cases:
        ring = PolynomialRing(GF(2), n, names="x", order="degrevlex")
        variables = ring.gens()
        def polynomial(terms):
            result = ring.zero()
            for mask in terms:
                monomial = ring.one()
                for j in range(n):
                    if mask & (1 << j):
                        monomial *= variables[j]
                result += monomial
            return result
        # Explicit field equations give an independent ordinary-ring oracle.
        reference = ring.ideal([polynomial(g) for g in generators] +
                               [x*x + x for x in variables]).groebner_basis()
        expected = []
        for poly in reference:
            terms = set()
            for powers in poly.dict():
                mask = sum(1 << i for i, exponent in enumerate(powers) if exponent)
                terms.symmetric_difference_update((mask,))
            if terms:
                expected.append(sorted(terms))
        expected.sort()
        python = BooleanF5B(n, timeout=10, max_signature_insertions=8)
        basis = python.basis([python.from_terms(g) for g in generators])
        actual = sorted(sorted(python.terms(g)) for g in basis)
        assert actual == expected, ("python", n, generators, actual, expected)
        verify(n, generators, actual)
        runs += 1
        for backend, binary, degree in [("native", args.native, -1),
                                        ("m4ri", args.m4ri, 0),
                                        ("m4ri", args.m4ri, min(2, n)),
                                        ("m4ri", args.m4ri, n)]:
            data = f"{n} {len(generators)} 8 {degree}\n"
            data += "".join(f'{len(g)} {" ".join(map(str,g))}\n' for g in generators)
            run = subprocess.run([str(binary.resolve())], input=data, text=True,
                                 capture_output=True, timeout=10, check=True)
            lines = run.stdout.splitlines()
            actual = sorted(list(map(int, line.split()))[1:] for line in lines[1:])
            assert actual == expected, (backend, n, degree, generators, actual, expected)
            verify(n, generators, actual)
            runs += 1
    report = {"status": "PASS", "seed": 20260924, "ideals": len(cases),
              "checked_runs": runs, "oracle": "Sage/Singular GF(2) degrevlex with explicit field equations",
              "native_sha256": digest(args.native.read_bytes()),
              "m4ri_sha256": digest(args.m4ri.read_bytes()),
              "checks": ["canonical_basis_equal", "Boolean_field_pairs", "S_pairs",
                         "reduced", "original_generators", "exhaustive_root_set_equality"]}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
