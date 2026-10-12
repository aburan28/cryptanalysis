#!/usr/bin/env python3
"""Independent affine replay of the fourteen-window mixed-radix tau format."""

from hashlib import sha256
import json
from pathlib import Path
import struct
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT / "prime-j0-tau-power16-20261010"))
import screen
import verify_group as reference

RADICES = (512,) * 6 + (640,) * 8
BOUNDS = (512,) * 6 + (640,) * 7 + (391,)
ATLAS512 = PARENT / "prime-j0-bound-budget15-20261010/atlas-w9.bin"
ATLAS640 = HERE / "atlas-r640-d640.bin"
ATLAS391 = HERE / "atlas-r640-d391.bin"


class Atlas:
    def __init__(self, path, radix, magic):
        raw = path.read_bytes()
        assert raw[:4] == magic
        self.radix = radix
        self.count = struct.unpack_from("<I", raw, 4)[0]
        self.codes = memoryview(raw)[8:8 + 4 * radix * radix]
        self.seeds = memoryview(raw)[8 + 4 * radix * radix:]
        assert len(raw) == 8 + 4 * radix * radix + 4 * self.count
        assert self.seed(0) == (0, 0)
        self.digest = sha256(raw).hexdigest()

    def seed(self, index):
        assert 0 <= index < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * index)

    def decode(self, a, b):
        slot = (a % self.radix) * self.radix + b % self.radix
        code = struct.unpack_from("<I", self.codes, 4 * slot)[0]
        seed_id, exponent, unit = code >> 4, (code >> 3) & 1, code & 7
        assert seed_id < self.count and unit < 6
        seed = self.seed(seed_id)
        digit = reference.coord_unit(reference.coord_tau(seed) if exponent else seed, unit)
        assert digit[0] % self.radix == a % self.radix
        assert digit[1] % self.radix == b % self.radix
        return digit, seed_id, exponent, unit


def evaluate_grouped(choices):
    buckets = [None, None]
    rotations = 0
    for exponent in range(2):
        gauge = None
        for power in (1, 2, 0):
            selected = [(point, unit) for point, e, unit in choices
                        if e == exponent and unit // 2 == power]
            if not selected:
                continue
            if gauge is not None:
                delta = (gauge + 3 - power) % 3
                if delta and buckets[exponent] is not None:
                    buckets[exponent] = reference.unit_point(buckets[exponent], 2 * delta)
                    rotations += 1
            gauge = power
            for point, unit in selected:
                signed = reference.negate(point) if unit & 1 else point
                buckets[exponent] = reference.add(buckets[exponent], signed)
        if gauge and buckets[exponent] is not None:
            buckets[exponent] = reference.unit_point(buckets[exponent], 2 * gauge)
            rotations += 1
    assert rotations <= 4
    return reference.add(buckets[0], reference.tau_point(buckets[1])), rotations


def check_panel(path, limit, atlases):
    raw = path.read_bytes()
    panel = json.loads(raw)
    scalars = [int(value, 16) for value in panel["scalars_hex"][:limit]]
    bases = []
    base = reference.G
    for radix in RADICES:
        bases.append((base, reference.tau_point(base)))
        base = reference.multiply(radix, base)
    cache = {}
    bucket_counts = [0, 0]
    mixed_additions = 0
    gauge_rotations = 0
    output_hash = sha256()
    for case, scalar in enumerate(scalars):
        a, b = screen.representative(scalar % screen.ORDER)
        assert (a + b * reference.LAMBDA_TAU - scalar) % screen.ORDER == 0
        start = a, b
        reconstruction = [0, 0]
        place = 1
        choices = []
        buckets = [None, None]
        for row, (radix, bound, (base, tau_base)) in enumerate(
                zip(RADICES, BOUNDS, bases)):
            atlas = atlases["512" if row < 6 else "391" if row == 13 else "640"]
            digit, seed_id, exponent, unit = atlas.decode(a, b)
            assert screen.norm(digit) <= bound * bound
            reconstruction[0] += place * digit[0]
            reconstruction[1] += place * digit[1]
            if seed_id:
                key = row, seed_id
                if key not in cache:
                    sa, sb = atlas.seed(seed_id)
                    cache[key] = reference.add(reference.multiply(sa, base),
                                               reference.multiply(sb, tau_base))
                point = cache[key]
                choices.append((point, exponent, unit))
                buckets[exponent] = reference.add(buckets[exponent],
                    reference.unit_point(point, unit))
                bucket_counts[exponent] += 1
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
            place *= radix
        assert (a, b) == (0, 0), case
        assert tuple(reconstruction) == start, case
        per_term = reference.add(buckets[0], reference.tau_point(buckets[1]))
        grouped, rotations = evaluate_grouped(choices)
        expected = reference.multiply(scalar % screen.ORDER, reference.G)
        assert per_term == grouped == expected, case
        mixed_additions += max(0, len(choices) - 1)
        gauge_rotations += rotations
        if expected is None:
            output_hash.update(bytes(64))
        else:
            output_hash.update(expected[0].to_bytes(32, "big"))
            output_hash.update(expected[1].to_bytes(32, "big"))
    return {"cases": len(scalars), "input_sha256": sha256(raw).hexdigest(),
            "output_sha256": output_hash.hexdigest(), "bucket_terms": bucket_counts,
            "mixed_additions": mixed_additions, "gauge_rotations": gauge_rotations,
            "cached_seed_points": len(cache)}


def main():
    atlases = {
        "512": Atlas(ATLAS512, 512, b"T2B9"),
        "640": Atlas(ATLAS640, 640, b"T640"),
        "391": Atlas(ATLAS391, 640, b"T640"),
    }
    assert reference.omega_point(reference.G) == reference.multiply(
        (1 - reference.LAMBDA_TAU) % screen.ORDER, reference.G)
    design = sys.argv[1:] == ["--design"]
    assert design or not sys.argv[1:]
    path = (PARENT / "prime-j0-bound-budget15-gauge-20261010/fresh-inputs.json"
            if design else HERE / "fresh-inputs.json")
    result = check_panel(path, 64 if design else 4096, atlases)
    if not design:
        receipt = {"schema": 1, "status": "passed", "source_sha256":
                   sha256(Path(__file__).read_bytes()).hexdigest(),
                   "atlas_sha256": {name: atlas.digest for name, atlas in atlases.items()},
                   "panel": result}
        (HERE / "group-check.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
