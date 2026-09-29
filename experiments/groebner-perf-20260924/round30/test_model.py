"""Exact semantic control for proposed deferred physical row movement.

This is a Python mathematical model, not a GPU implementation or benchmark.
"""
import hashlib
import json
from pathlib import Path
import random


def xor_rows(rows, mask):
    result = 0
    while mask:
        bit = mask & -mask
        result ^= rows[bit.bit_length() - 1]
        mask ^= bit
    return result


def reference(rows, cols):
    rows = list(rows)
    rank = 0
    for col in range(cols):
        pivot = next((i for i in range(rank, len(rows)) if (rows[i] >> col) & 1), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] >> col) & 1:
                rows[i] ^= rows[rank]
        rank += 1
    return rows, rank


def inverse(matrix, size):
    left = list(matrix)
    right = [1 << i for i in range(size)]
    for col in range(size):
        pivot = next(i for i in range(col, size) if (left[i] >> col) & 1)
        left[col], left[pivot] = left[pivot], left[col]
        right[col], right[pivot] = right[pivot], right[col]
        for row in range(size):
            if row != col and (left[row] >> col) & 1:
                left[row] ^= left[col]
                right[row] ^= right[col]
    assert left == [1 << i for i in range(size)]
    return right


def mapped(rows, cols, width):
    physical = list(rows)
    order = list(range(len(rows)))
    rank = col = 0
    panels = 0
    while rank < len(rows) and col < cols:
        forward, pivots, selected = [], [], []
        while len(selected) < width and rank + len(selected) < len(rows) and col < cols:
            found = None
            for logical in range(rank + len(selected), len(rows)):
                value = physical[order[logical]]
                for row, pivot_col in zip(forward, pivots):
                    if (value >> pivot_col) & 1:
                        value ^= row
                if (value >> col) & 1:
                    found = logical, value
                    break
            if found is not None:
                logical, value = found
                slot = rank + len(selected)
                order[slot], order[logical] = order[logical], order[slot]
                selected.append(order[slot])
                forward.append(value)
                pivots.append(col)
            col += 1
        size = len(selected)
        if not size:
            break
        panels += 1
        raw = [physical[index] for index in selected]
        pivot_block = [sum(((row >> p) & 1) << j for j, p in enumerate(pivots)) for row in raw]
        transform = inverse(pivot_block, size)
        canonical = [xor_rows(raw, mask) for mask in transform]
        # Immutable tables must be constructed before modifying any source row.
        selected_index = {physical_index: j for j, physical_index in enumerate(selected)}
        for physical_index, row in enumerate(physical):
            coefficient = sum(((row >> p) & 1) << j for j, p in enumerate(pivots))
            if physical_index in selected_index:
                coefficient ^= 1 << selected_index[physical_index]
            physical[physical_index] ^= xor_rows(canonical, coefficient)
        for j, p in enumerate(pivots):
            assert [i for i, row in enumerate(physical) if (row >> p) & 1] == [selected[j]]
        rank += size
    return [physical[i] for i in order], rank, panels


def main():
    checked = 0
    rng = random.Random(2026092930)
    digest = hashlib.sha256()
    widths = (1, 2, 3, 4, 8, 16, 32)
    def check(rows, cols):
        nonlocal checked
        expected = reference(rows, cols)
        for width in widths:
            actual, rank, panels = mapped(rows, cols, width)
            assert (actual, rank) == expected
            digest.update(json.dumps([rows, cols, width, actual, rank, panels], separators=(',', ':')).encode())
            checked += 1
    for nr, nc in ((0, 0), (0, 65), (3, 0), (1, 1), (2, 2), (2, 3), (3, 3)):
        for bits in range(1 << (nr * nc)):
            check([(bits >> (i * nc)) & ((1 << nc) - 1) for i in range(nr)], nc)
    for nr in (1, 7, 16, 17, 31, 32, 33, 65, 73):
        for nc in (1, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 257):
            rows = [rng.getrandbits(nc) for _ in range(nr)]
            check(rows, nc)
            check([0] * nr, nc)
            check([rows[i % max(1, nr // 2)] for i in range(nr)], nc)
            check([row & ~((1 << (nc // 2)) - 1) for row in rows], nc)
    # Omitting the selected-row unit correction would erase even this rank-one row.
    assert 1 ^ xor_rows([1], 1) == 0
    report = {'status': 'PASS', 'scope': 'exact Python semantic model only; no GPU/native/speed/novelty claim',
              'checked_width_instances': checked, 'widths': widths, 'seed': 2026092930,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'exact_output_digest': digest.hexdigest(), 'wrong_selected_row_update_counterexample': {'input': [1], 'wrong_output': [0]}}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
