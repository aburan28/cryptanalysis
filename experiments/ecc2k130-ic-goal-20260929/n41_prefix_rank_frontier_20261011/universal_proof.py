"""Prove the full-mask linear relaxation is consistent for every assignment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEM = HERE.parent / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def equations():
    lines = SYSTEM.read_text().splitlines()
    assert lines[1] == "2" and len(lines) == 500
    output = []
    for line in lines[2:]:
        polynomial = set()
        for token in line.rstrip(",").split("+"):
            monomial = () if token == "1" else tuple(sorted(set(
                int(piece[1:]) for piece in token.split("*"))))
            assert all(0 <= variable < 420 for variable in monomial)
            polynomial.symmetric_difference_update([monomial])
        output.append(polynomial)
    return output


def prove():
    out_path = HERE / "universal_proof.json"
    if out_path.exists():
        raise FileExistsError(out_path)
    polynomials = equations()
    free = sorted({term for poly in polynomials for term in poly
                   if term and min(term) >= 48})
    columns = {term: index for index, term in enumerate(free)}
    coefficient_rows = []
    fixed_rows = []
    for polynomial in polynomials:
        coefficient = 0
        fixed = set()
        for term in polynomial:
            if term and min(term) >= 48:
                coefficient ^= 1 << columns[term]
            else:
                # The absence of mixed fixed/free monomials is the key
                # exact property of this particular quadratic system.
                assert not term or max(term) < 48
                fixed.add(term)
        coefficient_rows.append(coefficient)
        fixed_rows.append(fixed)
    pivots = {}
    dependencies = []
    for index, original_row in enumerate(coefficient_rows):
        row = original_row
        combination = 1 << index
        while row:
            pivot = row.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = (row, combination)
                break
            prior_row, prior_combination = pivots[pivot]
            row ^= prior_row
            combination ^= prior_combination
        if not row:
            dependencies.append(combination)
    assert len(pivots) == 413 and len(dependencies) == 85
    for combination in dependencies:
        coefficient_sum = 0
        fixed_sum = set()
        bits = combination
        while bits:
            low = bits & -bits
            index = low.bit_length() - 1
            coefficient_sum ^= coefficient_rows[index]
            fixed_sum.symmetric_difference_update(fixed_rows[index])
            bits ^= low
        assert coefficient_sum == 0 and not fixed_sum
    report = {
        "status": "PROVED_UNIVERSAL_FULL_MASK_LINEAR_CONSISTENCY",
        "scope": "frozen 498-equation N41 selected raw-target branch; all 2^48 assignments of its eight six-bit source masks; degree-two free monomials treated independently",
        "fixed_source_bits": 48,
        "equations": len(polynomials),
        "free_monomials": len(free),
        "cross_fixed_free_monomials": 0,
        "coefficient_rank": len(pivots),
        "dependency_count": len(dependencies),
        "nonzero_fixed_dependency_polynomials": 0,
        "dependency_combinations_hex": [format(bits, "x") for bits in dependencies],
        "source_sha256": sha(Path(__file__)),
        "system_sha256": sha(SYSTEM),
    }
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(report["status"], len(free), len(pivots), len(dependencies))


if __name__ == "__main__":
    prove()
