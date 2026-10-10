#!/usr/bin/env python3
"""Exact two-bucket storage frontier over small power-of-two window widths."""

from collections import Counter
from functools import lru_cache
from hashlib import sha256
from itertools import combinations_with_replacement
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REORDER = ROOT / "prime-j0-tau-reordered16-20261010" / "screen.py"
spec = importlib.util.spec_from_file_location("reorder_screen", REORDER)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
ORDER = prior.source.ORDER


@lru_cache(None)
def atlas(width, bound):
    return prior.seed_count(width, bound)


def candidate(nonfinal, last):
    widths = tuple(nonfinal) + (last,)
    prefix, digit_sum = 1, 0
    for width in nonfinal:
        digit_sum += (1 << width) * prefix
        prefix <<= width
    product = prefix << last
    # The strict inequality is monotone while product - digit_sum - D*prefix > 0.
    lo, hi = 0, (1 << last) - 1
    while lo < hi:
        middle = (lo + hi + 1) // 2
        gap = product - digit_sum - middle * prefix
        if gap > 0 and 3 * gap * gap > ORDER:
            lo = middle
        else:
            hi = middle - 1
    bound = lo
    gap = product - digit_sum - bound * prefix
    if not (gap > 0 and 3 * gap * gap > ORDER):
        return None
    final = atlas(last, bound)
    if final["max_direct_norm"] > bound * bound:
        return None
    counts = Counter(nonfinal)
    point_slots = final["seeds"] + sum(count * atlas(width, 1 << width)["seeds"]
                                        for width, count in counts.items())
    atlas_bytes = final["atlas_bytes"]
    for width in counts:
        if width != last or bound != 1 << width:
            atlas_bytes += atlas(width, 1 << width)["atlas_bytes"]
    return {"widths": widths, "bounds": tuple(1 << w for w in nonfinal) + (bound,),
            "total_bits": sum(widths), "point_slots": point_slots,
            "point_payload_bytes": 64 * point_slots, "atlas_bytes": atlas_bytes,
            "retained_before_metadata": 64 * point_slots + atlas_bytes,
            "termination_margin": str(3 * gap * gap - ORDER)}


def main():
    full = {str(width): atlas(width, 1 << width) for width in range(6, 10)}
    assert all(item["segments"].get(1) == 2 for item in full.values())
    best = {}
    valid = Counter()
    for window_count in range(16, 20):
        top = []
        for nonfinal in combinations_with_replacement(range(6, 10), window_count - 1):
            for last in range(6, 10):
                item = candidate(nonfinal, last)
                if item is None:
                    continue
                valid[window_count] += 1
                top.append(item)
        top.sort(key=lambda item: (item["retained_before_metadata"],
                                   item["point_slots"], item["widths"]))
        best[str(window_count)] = top[:5]
        assert best[str(window_count)]
    result = {"schema": "prime-j0-tau-frontier-screen-v1",
              "width_range": [6, 9], "window_counts": [16, 17, 18, 19],
              "selection": "minimum point payload plus distinct 32-bit atlas allocations",
              "nonfinal_order": "ascending width minimizes digit sum for a fixed multiset",
              "full_bound_atlases": full, "valid_layout_counts": valid,
              "best": best,
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "reordered_screen_sha256": sha256(REORDER.read_bytes()).hexdigest(),
              "base_screen_sha256": sha256(prior.PARENT.read_bytes()).hexdigest()}
    (HERE / "screen-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for count, rows in best.items():
        first = rows[0]
        print(count, first["retained_before_metadata"], first["point_slots"],
              first["total_bits"], list(first["widths"]), list(first["bounds"]))


if __name__ == "__main__":
    main()
