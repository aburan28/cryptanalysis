"""Independent checked-Sage audit of the universal linear certificate."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
SYSTEM = HERE.parent / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


proof = json.loads((HERE / "universal_proof.json").read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert runtime["status"] == "verified"
assert proof["system_sha256"] == sha(SYSTEM)
assert proof["source_sha256"] == sha(HERE / "universal_proof.py")
lines = SYSTEM.read_text().splitlines()
assert len(lines) == 500 and lines[1] == "2"
polynomials = []
for line in lines[2:]:
    polynomial = set()
    for raw in line.rstrip(",").split("+"):
        monomial = frozenset() if raw == "1" else frozenset(
            int(part[1:]) for part in raw.split("*"))
        polynomial.symmetric_difference_update([monomial])
    polynomials.append(polynomial)
assert len(polynomials) == 498
free_columns = sorted({term for poly in polynomials for term in poly
                       if term and all(i >= 48 for i in term)},
                      key=lambda term: tuple(sorted(term)))
column_index = {term: index for index, term in enumerate(free_columns)}
coefficient_rows = []
fixed_rows = []
for polynomial in polynomials:
    coefficient = 0
    fixed = set()
    for term in polynomial:
        source = [i for i in term if i < 48]
        free = [i for i in term if i >= 48]
        assert not (source and free)
        if free:
            coefficient ^= 1 << column_index[term]
        else:
            fixed.symmetric_difference_update([term])
    coefficient_rows.append(coefficient)
    fixed_rows.append(fixed)

# Use low pivots, opposite to the producer's high-pivot elimination.
pivots = {}
for original in coefficient_rows:
    row = original
    while row:
        pivot = (row & -row).bit_length() - 1
        if pivot not in pivots:
            pivots[pivot] = row
            break
        row ^= pivots[pivot]
assert len(pivots) == 413

dependency_bits = [int(raw, 16) for raw in proof["dependency_combinations_hex"]]
assert len(dependency_bits) == 85
dependency_pivots = {}
for combination in dependency_bits:
    row = combination
    while row:
        pivot = (row & -row).bit_length() - 1
        if pivot not in dependency_pivots:
            dependency_pivots[pivot] = row
            break
        row ^= dependency_pivots[pivot]
    coefficient = 0
    fixed = set()
    bits = combination
    while bits:
        low = bits & -bits
        index = low.bit_length() - 1
        assert index < len(coefficient_rows)
        coefficient ^= coefficient_rows[index]
        fixed.symmetric_difference_update(fixed_rows[index])
        bits ^= low
    assert coefficient == 0 and not fixed
assert len(dependency_pivots) == 85

# A small independent Sage GF(2) minor confirms the bit encoding of rows.
minor_columns = sorted(pivots)[:64]
minor = matrix(GF(2), 498, 64,
               lambda i, j: (coefficient_rows[i] >> minor_columns[j]) & 1)
assert minor.rank() == 64
out = {"status": "PASS_INDEPENDENT_SAGE_UNIVERSAL_CERTIFICATE",
       "fixed_source_bits": 48,
       "free_monomials": len(free_columns),
       "low_pivot_coefficient_rank": len(pivots),
       "independent_dependency_count": len(dependency_pivots),
       "sage_minor_rank": minor.rank(),
       "verified_zero_fixed_polynomials": len(dependency_bits),
       "sha256": {"verifier": sha(Path(__file__)),
                  "proof": sha(HERE / "universal_proof.json"),
                  "system": sha(SYSTEM),
                  "runtime": sha(HERE / "sage_runtime_info.json")}}
(HERE / "universal_sage_audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], out["low_pivot_coefficient_rank"], out["independent_dependency_count"])
