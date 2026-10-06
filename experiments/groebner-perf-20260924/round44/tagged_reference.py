"""Offline original-ANF certification; no native code or producer state."""
from functools import lru_cache
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round34'))
from affine_reference import branch_model

spec = importlib.util.spec_from_file_location('partial_affine_reference43', HERE.parent / 'round43/reference.py')
partial_reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = partial_reference
spec.loader.exec_module(partial_reference)

TAG = 1 << 63


@lru_cache(maxsize=48)
def certify_roots(x, y, equations, items, raw, byteorder):
    """Check all identities and exhaust every remaining original assignment.

    The cache is offline audit reuse only. This function is never part of a
    timed query or the implementation's producer/checker data path.
    """
    assert byteorder in ('little', 'big') and len(raw) % 8 == 0 and len(raw) <= 64 << 20
    _, vectors, monomials, _, _ = branch_model(x, y, equations, items)
    limbs, branches = (equations + 63) // 64, 1 << x
    prefix, entry = branches * limbs, 1 + (y + 1) * limbs
    words = tuple(int.from_bytes(raw[i:i + 8], byteorder) for i in range(0, len(raw), 8))
    assert len(words) >= prefix and (len(words) - prefix) % entry == 0
    assert (len(words) - prefix) // entry <= branches
    mask, covered = (1 << equations) - 1, bytearray(branches)
    constants, extended, partials, roots, assignments = 0, [], [], [], 0
    for branch, vector in enumerate(vectors):
        witness = sum(words[branch * limbs + limb] << (64 * limb) for limb in range(limbs))
        assert 0 <= witness <= mask
        if not witness:
            continue
        for feature in range(len(monomials)):
            assert ((vector & mask & witness).bit_count() & 1) == int(feature == 0)
            vector >>= equations
        covered[branch] = 1
        constants += 1
    previous = -1
    for offset in range(prefix, len(words), entry):
        tagged, branch = bool(words[offset] & TAG), words[offset] & ~TAG
        assert previous < branch < branches and not covered[branch]
        previous = branch
        coefficients = tuple((vectors[branch] >> (equations * j)) & mask for j in range(len(monomials)))
        witnesses = tuple(sum(words[offset + 1 + slot * limbs + limb] << (64 * limb)
                              for limb in range(limbs)) for slot in range(y + 1))
        assert all(0 <= witness <= mask for witness in witnesses)
        if tagged:
            # Reconstruct original polynomial rows for the separately written
            # mathematical checker. It accepts only equation-row witnesses.
            original = [0] * equations
            for monomial, coefficient in zip(monomials, coefficients):
                while coefficient:
                    bit = coefficient & -coefficient
                    original[bit.bit_length() - 1] ^= 1 << monomial
                    coefficient ^= bit
            checked = partial_reference.checker(y, tuple(original), witnesses)
            assignments += checked.candidates
            assert assignments <= 4194304
            roots.extend(branch | (root << x) for root in checked.roots)
            partials.append((branch, checked.rank, checked.inconsistent, checked.candidates))
        else:
            identity = set()
            for slot, witness in enumerate(witnesses):
                multiplier = 0 if slot == 0 else 1 << (slot - 1)
                for monomial, coefficient in zip(monomials, coefficients):
                    if (coefficient & witness).bit_count() & 1:
                        identity.symmetric_difference_update((monomial | multiplier,))
            assert identity == {0}, 'invalid multiplier contradiction'
            extended.append(branch)
        covered[branch] = 1
    supports = tuple(tuple(j for j, m in enumerate(monomials) if a & m == m) for a in range(1 << y))
    for branch, vector in enumerate(vectors):
        if covered[branch]:
            continue
        assignments += 1 << y
        assert assignments <= 4194304
        coefficients = tuple((vector >> (equations * j)) & mask for j in range(len(monomials)))
        for assignment, features in enumerate(supports):
            value = 0
            for feature in features:
                value ^= coefficients[feature]
            if not value:
                roots.append(branch | (assignment << x))
    assert len(roots) <= 256 and len(set(roots)) == len(roots)
    return tuple(sorted(roots)), constants, tuple(extended), tuple(partials), assignments
