"""Independent Singular oracle for the dual solver and dimension certificate."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from benchmark import verify
from boolean_basis import certify_boolean_basis
from solve_dual import _in_process
from sage.all import GF, PolynomialRing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=HERE / "build/boolean-dual")
    parser.add_argument("--output", type=Path, default=HERE / "results/dual-validation.json")
    args = parser.parse_args()
    rng = random.Random(2026092402)
    cases = [(1, []), (2, [[0, 3]]), (2, [[0]]), (2, [[1], [0, 1]]),
             (3, [[3, 4]]), (3, [[0, 7]]), (8, []),
             (4, [[1, 1], [2, 2, 4]]), (4, [[]] * 64 + [[0]]),
             (4, [[1]] * 64 + [[0, 1]])]
    for n in range(1, 9):
        for _ in range(24):
            cases.append((n, [[rng.randrange(1 << n)
                               for _ in range(rng.randrange(1, 16))]
                              for _ in range(rng.randrange(1, n + 3))]))
    false_bases_rejected = 0
    for n, generators in cases:
        ring = PolynomialRing(GF(2), n, names="x", order="degrevlex")
        variables = ring.gens()
        def poly(terms):
            out = ring.zero()
            for mask in terms:
                term = ring.one()
                for i, x in enumerate(variables):
                    if mask & (1 << i):
                        term *= x
                out += term
            return out
        oracle = ring.ideal([poly(g) for g in generators] +
                            [x*x + x for x in variables]).groebner_basis()
        expected = []
        for g in oracle:
            row = set()
            for powers in g.dict():
                row.symmetric_difference_update((sum(1 << i for i, e in enumerate(powers) if e),))
            if row:
                expected.append(sorted(row))
        expected.sort()
        data = f"{n} {len(generators)} 0 0\n" + "".join(
            f'{len(g)} {" ".join(map(str, g))}\n' for g in generators)
        run = subprocess.run([str(args.binary.resolve())], input=data, text=True,
                             capture_output=True, check=True, timeout=15)
        actual = sorted(list(map(int, line.split()))[1:] for line in run.stdout.splitlines()[1:])
        assert actual == expected, (n, generators, actual, expected)
        library_basis, metrics, _ = _in_process(n, generators)
        assert sorted(library_basis) == expected
        assert metrics["standard_monomials"] == metrics["roots"]
        normalized = []
        for g in generators:
            s = set()
            for m in g:
                s.symmetric_difference_update((m,))
            normalized.append(sorted(s))
        verify(n, normalized, actual)
        assert certify_boolean_basis(n, generators, actual)["verified"]
        assert certify_boolean_basis(n, generators, actual, monomial_cache=False)["verified"]
        for mutation in ([[0]], [], actual[:-1]):
            if sorted(mutation) == expected:
                continue
            assert not certify_boolean_basis(n, generators, mutation)["verified"], (n, generators, mutation)
            assert not certify_boolean_basis(n, generators, mutation, monomial_cache=False)["verified"]
            false_bases_rejected += 1
    cap = subprocess.run([str(args.binary.resolve())], input="9 0 0 0\n", text=True, capture_output=True)
    assert cap.returncode == 3 and "root cap exceeded" in cap.stderr and not cap.stdout
    capped, detail, _ = _in_process(9, [])
    assert capped is None and "root cap exceeded" in detail["error"]
    report = {"status": "PASS", "ideals": len(cases), "false_bases_rejected": false_bases_rejected,
              "root_cap_returns_inconclusive": True, "seed": 2026092402,
              "library_and_cli_equal": True,
              "oracle": "Sage/Singular GF(2) grevlex with explicit field equations",
              "checks": ["exact canonical basis", "S-pairs", "Boolean field pairs", "reducedness",
                         "exhaustive root equality", "dimension certificate", "more than 64 equations",
                         "duplicate-term cancellation", "empty/zero/unit ideals", "multiple root bitset words"],
              "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
