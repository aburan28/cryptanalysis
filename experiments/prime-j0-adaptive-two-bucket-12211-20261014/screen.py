#!/usr/bin/env python3
"""Count adaptive point rotations on the frozen scalar fixture."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-split-prime-12211-20261014"
spec = importlib.util.spec_from_file_location("split_prime_12211_screen", PARENT / "screen.py")
assert spec is not None and spec.loader is not None
radix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radix)


def images(pair: tuple[int, int]) -> list[tuple[int, int]]:
    a, b = pair
    result = []
    for _ in range(3):
        result.extend([(a, b), (-a, -b)])
        a, b = a + 3*b, -a - 2*b
    assert (a, b) == pair
    return result


def terminal_group(pair: tuple[int, int]) -> int:
    a, b = pair
    if a < 0 or (a == 0 and b < 0):
        pair = (-a, -b)
    canonical = min(image for image in images(pair)
                    if image[0] > 0 or (image[0] == 0 and image[1] >= 0))
    return images(canonical).index(pair) // 2


def run() -> dict:
    codes, seeds = radix.digits()
    assert len(seeds) == 2036
    fixture = json.loads(radix.FIXTURE.read_text())
    rows = []
    for case in fixture["cases"]:
        scalar = int(case["scalar_hex"], 16) % radix.model.mixed.screen.ORDER
        state = radix.model.mixed.screen.representative(scalar)
        counts = [0, 0, 0]
        for _ in range(18):
            state, (index, unit, _, _) = radix.step(state, codes)
            if index:
                counts[unit // 2] += 1
        if state != (0, 0):
            counts[terminal_group(state)] += 1
        fused = 1 if counts[1] <= counts[2] else 2
        rows.append({"groups": counts, "fused": fused,
                     "point_rotations": counts[fused]})
    distribution = Counter(row["point_rotations"] for row in rows)
    return {
        "schema": 1,
        "variant": "adaptive_two_bucket_fusion",
        "fixture_sha256": sha256(radix.FIXTURE.read_bytes()).hexdigest(),
        "radix_screen_sha256": sha256((PARENT / "screen.py").read_bytes()).hexdigest(),
        "cases": len(rows),
        "case0": rows[0],
        "point_rotation_distribution": dict(sorted(distribution.items())),
        "total_point_rotations": sum(row["point_rotations"] for row in rows),
        "chosen_bucket_counts": dict(sorted(Counter(row["fused"] for row in rows).items())),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
