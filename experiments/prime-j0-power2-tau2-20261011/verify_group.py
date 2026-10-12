#!/usr/bin/env python3
"""Independent affine replay of three-image radix-1024 shift windows."""

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

RADICES = (1024,) * 12
FULL_ATLAS = HERE / "atlas-r1024-full-tau2.bin"
TERMINAL_ATLAS = HERE / "atlas-r1024-terminal-tau2.bin"


def tau_power(pair, exponent):
    for _ in range(exponent):
        pair = reference.coord_tau(pair)
    return pair


class FullAtlas:
    def __init__(self, path):
        raw = path.read_bytes()
        assert raw[:4] == b"T103"
        self.radix = 1024
        self.count = struct.unpack_from("<I", raw, 4)[0]
        self.codes = memoryview(raw)[8:8 + 4 * self.radix * self.radix]
        self.seeds = memoryview(raw)[8 + 4 * self.radix * self.radix:]
        assert len(raw) == 8 + 4 * self.radix * self.radix + 4 * self.count
        assert self.seed(0) == (0, 0)
        self.digest = sha256(raw).hexdigest()

    def seed(self, index):
        assert 0 <= index < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * index)

    def decode(self, a, b):
        slot = (a % self.radix) * self.radix + b % self.radix
        code = struct.unpack_from("<I", self.codes, 4 * slot)[0]
        seed_id, exponent, unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < self.count and exponent <= 2 and unit < 6
        seed = self.seed(seed_id)
        digit = reference.coord_unit(tau_power(seed, exponent), unit)
        assert digit[0] % self.radix == a % self.radix
        assert digit[1] % self.radix == b % self.radix
        return digit, seed_id, exponent, unit


class TerminalAtlas:
    def __init__(self, path):
        raw = path.read_bytes()
        magic, self.bound, self.b_min, self.b_max, self.count, pairs, reserved = \
            struct.unpack_from("<4sHhhIIH", raw)
        assert magic == b"R103" and self.bound == 149 and reserved == 0
        self.rows = [struct.unpack_from("<hHI", raw, 20 + 8 * i)
                     for i in range(self.b_max - self.b_min + 1)]
        code_start = 20 + 8 * len(self.rows)
        self.codes = memoryview(raw)[code_start:code_start + 4 * pairs]
        self.seeds = memoryview(raw)[code_start + 4 * pairs:]
        assert len(self.seeds) == 4 * self.count
        assert self.seed(0) == (0, 0)
        self.digest = sha256(raw).hexdigest()

    def seed(self, index):
        assert 0 <= index < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * index)

    def decode(self, a, b):
        assert screen.norm((a, b)) < self.bound * self.bound
        assert self.b_min <= b <= self.b_max
        a_min, length, offset = self.rows[b - self.b_min]
        assert a_min <= a < a_min + length
        code = struct.unpack_from("<I", self.codes, 4 * (offset + a - a_min))[0]
        seed_id, exponent, unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < self.count and exponent <= 2 and unit < 6
        seed = self.seed(seed_id)
        digit = reference.coord_unit(tau_power(seed, exponent), unit)
        assert digit == (a, b)
        return digit, seed_id, exponent, unit


def evaluate_grouped(choices):
    buckets = [None, None, None]
    rotations = 0
    for exponent in range(3):
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
    assert rotations <= 6
    return reference.add(buckets[0], reference.tau_point(
        reference.add(buckets[1], reference.tau_point(buckets[2])))), rotations


def check_panel(path, limit, atlases):
    raw = path.read_bytes()
    panel = json.loads(raw)
    scalars = [int(value, 16) for value in panel["scalars_hex"][:limit]]
    bases = []
    base = reference.G
    for radix in RADICES:
        bases.append((base, reference.tau_point(base)))
        base = reference.multiply(radix, base)
    bases.append((base, reference.tau_point(base)))
    cache = {}
    bucket_counts = [0, 0, 0]
    mixed_additions = 0
    gauge_rotations = 0
    outer_tau_images = 0
    output_hash = sha256()
    for case, scalar in enumerate(scalars):
        a, b = screen.representative(scalar % screen.ORDER)
        assert (a + b * reference.LAMBDA_TAU - scalar) % screen.ORDER == 0
        start = a, b
        reconstruction = [0, 0]
        place = 1
        choices = []
        buckets = [None, None, None]
        for row, (base, tau_base) in enumerate(bases[:-1]):
            atlas = atlases["full"]
            digit, seed_id, exponent, unit = atlas.decode(a, b)
            assert screen.norm(digit) <= 1024 * 1024
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
            assert (a - digit[0]) % 1024 == (b - digit[1]) % 1024 == 0
            a, b = (a - digit[0]) >> 10, (b - digit[1]) >> 10
            place *= 1024
        assert screen.norm((a, b)) < 149 * 149, case
        terminal = atlases["terminal"]
        digit, seed_id, exponent, unit = terminal.decode(a, b)
        assert digit == (a, b)
        reconstruction[0] += place * digit[0]
        reconstruction[1] += place * digit[1]
        if seed_id:
            row = len(RADICES)
            key = row, seed_id
            if key not in cache:
                sa, sb = terminal.seed(seed_id)
                base, tau_base = bases[row]
                cache[key] = reference.add(reference.multiply(sa, base),
                                           reference.multiply(sb, tau_base))
            point = cache[key]
            choices.append((point, exponent, unit))
            buckets[exponent] = reference.add(buckets[exponent],
                reference.unit_point(point, unit))
            bucket_counts[exponent] += 1
        assert tuple(reconstruction) == start, case
        per_term = reference.add(buckets[0], reference.tau_point(
            reference.add(buckets[1], reference.tau_point(buckets[2]))))
        grouped, rotations = evaluate_grouped(choices)
        expected = reference.multiply(scalar % screen.ORDER, reference.G)
        assert per_term == grouped == expected, case
        mixed_additions += max(0, len(choices) - 1)
        gauge_rotations += rotations
        outer_tau_images += (buckets[1] is not None or buckets[2] is not None) \
            + (buckets[2] is not None)
        if expected is None:
            output_hash.update(bytes(64))
        else:
            output_hash.update(expected[0].to_bytes(32, "big"))
            output_hash.update(expected[1].to_bytes(32, "big"))
    return {"cases": len(scalars), "input_sha256": sha256(raw).hexdigest(),
            "output_sha256": output_hash.hexdigest(), "bucket_terms": bucket_counts,
            "mixed_additions": mixed_additions, "gauge_rotations": gauge_rotations,
            "outer_tau_images": outer_tau_images,
            "cached_seed_points": len(cache)}


def main():
    atlases = {
        "full": FullAtlas(FULL_ATLAS),
        "terminal": TerminalAtlas(TERMINAL_ATLAS),
    }
    assert reference.omega_point(reference.G) == reference.multiply(
        (1 - reference.LAMBDA_TAU) % screen.ORDER, reference.G)
    design = sys.argv[1:] == ["--design"]
    assert design or not sys.argv[1:]
    path = (PARENT / "prime-j0-power2-residual-20261010/fresh-inputs.json"
            if design else HERE / "fresh-inputs.json")
    result = check_panel(path, 64 if design else 4096, atlases)
    receipt = {"schema": 1, "status": "passed", "source_sha256":
               sha256(Path(__file__).read_bytes()).hexdigest(),
               "atlas_sha256": {name: atlas.digest for name, atlas in atlases.items()},
               "panel": result}
    output = HERE / ("design-check.json" if design else "group-check.json")
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
