"""Finite checks supplement the argument in README; arbitrary masks are unsafe."""
import hashlib
import json
from pathlib import Path
import time


def check():
    started = time.perf_counter()
    counts = {}
    def less(a, b):
        return (a.bit_count(), -a) < (b.bit_count(), -b)
    for n in range(1, 9):
        count = 0
        full = (1 << n) - 1
        for leading in range(1 << n):
            tails = [t for t in range(1 << n) if less(t, leading)]
            remaining = full ^ leading
            multiplier = remaining
            while True:
                for tail in tails:
                    assert less(tail | multiplier, leading | multiplier)
                    count += 1
                if not multiplier:
                    break
                multiplier = (multiplier - 1) & remaining
        counts[n] = count
    assert less(2, 1) and not less(2 | 1, 1 | 1)
    return {'scope': 'finite invariant check, not a general proof or speed measurement',
            'triple_checks_by_variables': counts, 'total': sum(counts.values()),
            'overlap_counterexample': {'leading': 1, 'tail': 2, 'multiplier': 1},
            'seconds': time.perf_counter() - started,
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
