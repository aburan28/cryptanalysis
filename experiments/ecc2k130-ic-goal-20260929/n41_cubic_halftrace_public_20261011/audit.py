"""Independently compare cubic S3 with source-pair group sums."""

import importlib.util
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010" / "screen.json"
OLD_REPLAY = ROOT / "n41_basis_aware_quartic_20261011" / "replay.py"
spec = importlib.util.spec_from_file_location("independent_n41_replay", OLD_REPLAY)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def trace(field, value):
    out = 0
    for _ in range(field.n):
        out ^= value
        value = field.square(value)
    assert out in (0, 1)
    return out


def halftrace(field, value):
    out = 0
    for _ in range((field.n + 1) // 2):
        out ^= value
        value = field.square(field.square(value))
    return out


def main():
    screen = json.loads(SCREEN.read_text())
    field = replay.Field()
    points = {row["mask"]: tuple(row["raw_pair_point"]) for row in screen["raw_audit"]}
    assert len(points) == 32
    checked = 0
    for rotation in (0, 5, 10, 15, 20, 25):
        rotated = {}
        for mask, point in points.items():
            for _ in range(rotation):
                point = field.square(point[0]), field.square(point[1])
            rotated[mask] = point
        for a_mask in sorted(rotated):
            for b_mask in sorted(rotated):
                if a_mask >= b_mask:
                    continue
                left = rotated[a_mask]
                for sign in (0, 1):
                    right = rotated[b_mask]
                    if sign:
                        right = right[0], right[1] ^ right[0]
                    summed = replay.add(field, left, right)
                    assert summed is not None and summed[0]
                    a, b, c = (field.inv(point[0]) for point in (left, right, summed))
                    s, p = a ^ b, field.mul(a, b)
                    z = field.mul(p, c)
                    quartic = field.square(z) ^ z ^ field.square(c ^ s)
                    branch = z ^ replay.Field.halftrace(field, field.square(c ^ s))
                    assert quartic == 0 and trace(field, c ^ s) == 0 and branch in (0, 1)
                    checked += 1
    result = {"status": "PASS_ALL_N41_SOURCE_PAIR_S3",
              "rotations": [0, 5, 10, 15, 20, 25],
              "source_masks_per_rotation": len(points),
              "relative_sign_choices": 2,
              "pairs_checked": checked,
              "expected_pairs": 6 * 496 * 2}
    assert checked == result["expected_pairs"]
    rng = random.Random(20261011)
    for _ in range(1000):
        a, b, c = (rng.getrandbits(41) for _ in range(3))
        z = field.mul(field.mul(a, b), c)
        v = a ^ b ^ c
        original = field.square(z) ^ z ^ field.square(v)
        bit = z ^ halftrace(field, field.square(v))
        encoded = trace(field, v) == 0 and bit in (0, 1)
        assert (original == 0) == encoded
    result["arbitrary_triples_checked"] = 1000
    (HERE / "audit_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
