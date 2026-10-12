#!/usr/bin/env python3
"""Independently enumerate the complete six-unit orbit partition."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("candidate_adic_index", HERE / "index.py")
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)
RADIX = 1024
COUNT = RADIX * RADIX


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def images(pair):
    """Independent six-unit action in index-code order."""
    a, b = pair
    result = []
    for _ in range(3):
        result.extend(((a % RADIX, b % RADIX),
                       ((-a) % RADIX, (-b) % RADIX)))
        a, b = a + 3 * b, -a - 2 * b
    return result


def oracle_representatives():
    yield (0, 0)
    yield (RADIX // 2, 0)
    for m in range(2, 11):
        factor = 1 << (10 - m)
        for odd_a in range(1, 1 << (m - 1), 2):
            for even_b in range(0, 1 << m, 2):
                yield odd_a * factor, even_b * factor


def main():
    seen = bytearray(COUNT)
    sizes = Counter()
    candidate_reps = candidate.representatives()
    classes = 0
    for index, representative in enumerate(oracle_representatives()):
        assert next(candidate_reps) == (index, representative)
        orbit = set(images(representative))
        sizes[len(orbit)] += 1
        for a, b in orbit:
            slot = a * RADIX + b
            assert seen[slot] == 0, (index, a, b)
            seen[slot] = 1
            actual_index, unit = candidate.canonicalize(a, b)
            assert actual_index == index
            assert 0 <= unit < 6
            assert images((a, b))[unit] == representative
        classes += 1
    assert list(candidate_reps) == []
    assert classes == 174_764
    assert sum(seen) == COUNT
    assert sizes == {1: 1, 3: 1, 6: 174_762}
    receipt = {"schema": 1, "status": "passed",
               "residues": COUNT, "classes": classes,
               "orbit_sizes": dict(sizes),
               "index_source_sha256": digest(HERE / "index.py"),
               "verifier_sha256": digest(Path(__file__))}
    (HERE / "index-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
