#!/usr/bin/env python3
"""Count exact recoding and group-call structure on a frozen scalar panel."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
FRONTIER = EXPERIMENTS / "prime-j0-tau-frontier-20261010"
POWER16 = EXPERIMENTS / "prime-j0-tau-power16-20261010"
RADIX384 = EXPERIMENTS / "prime-j0-tau384-matching-20261010"
NATIVE = EXPERIMENTS / "prime-j0-tau-frontier-native-prototype-20261010"
GROUP_SOURCE = POWER16 / "verify_group.py"
sys.path.insert(0, str(POWER16))
spec = importlib.util.spec_from_file_location("tau_group_cost", GROUP_SOURCE)
group = importlib.util.module_from_spec(spec)
spec.loader.exec_module(group)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class Radix384Atlas:
    def __init__(self, path):
        raw = path.read_bytes()
        assert raw[:4] == b"T384"
        self.radix = 384
        self.count = struct.unpack_from("<I", raw, 4)[0]
        code_bytes = 4 * self.radix * self.radix
        assert len(raw) == 8 + code_bytes + 4 * self.count
        self.codes = memoryview(raw)[8:8 + code_bytes]
        self.seeds = memoryview(raw)[8 + code_bytes:]
        assert self.seed(0) == (0, 0)

    def seed(self, seed_id):
        return struct.unpack_from("<hh", self.seeds, 4 * seed_id)

    def decode(self, a, b):
        slot = (a % self.radix) * self.radix + b % self.radix
        code = struct.unpack_from("<I", self.codes, 4 * slot)[0]
        seed_id, exponent, unit = code >> 4, (code >> 3) & 1, code & 7
        assert seed_id < self.count and unit < 6
        seed = self.seed(seed_id)
        digit = group.coord_unit(group.coord_tau(seed) if exponent else seed, unit)
        assert digit[0] % self.radix == a % self.radix
        assert digit[1] % self.radix == b % self.radix
        return digit, seed_id, exponent, unit


def load_power_atlas(width, bound):
    source = (POWER16 if (width, bound) in ((8, 256), (9, 363))
              else FRONTIER / f"w{width}-d{bound}")
    previous = group.HERE
    try:
        group.HERE = source
        atlas = group.Atlas(width)
    finally:
        group.HERE = previous
    return atlas, source / f"atlas-w{width}.bin"


def recode(scalar, widths, bounds, atlases):
    a, b = group.representative(scalar % group.ORDER)
    original = (a, b)
    assert (a + b * group.LAMBDA_TAU - scalar) % group.ORDER == 0
    reconstruction = [0, 0]
    scale = 1
    choices = []
    for width, bound, atlas in zip(widths, bounds, atlases):
        digit, seed_id, exponent, unit = atlas.decode(a, b)
        assert group.norm(digit) <= bound * bound
        if exponent:
            assert 3 * group.norm(atlas.seed(seed_id)) <= bound * bound
        assert (seed_id == 0) == (digit == (0, 0))
        radix = 1 << width if width != 384 else 384
        assert (a - digit[0]) % radix == (b - digit[1]) % radix == 0
        reconstruction[0] += scale * digit[0]
        reconstruction[1] += scale * digit[1]
        a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        scale *= radix
        choices.append((seed_id, exponent, unit))
    assert (a, b) == (0, 0)
    assert tuple(reconstruction) == original
    return choices


def calls(choices):
    occupied = [False, False]
    gauge = None
    mixed_calls = 0
    nontrivial_mixed = 0
    gauge_rotations = 0
    negative_table_points = 0
    for power in (1, 2, 0):
        selected = [(seed, exponent, unit) for seed, exponent, unit in choices
                    if seed and unit // 2 == power]
        if not selected:
            continue
        if gauge is not None and (gauge + 3 - power) % 3:
            gauge_rotations += sum(occupied)
        gauge = power
        for _, exponent, unit in selected:
            mixed_calls += 1
            nontrivial_mixed += int(occupied[exponent])
            occupied[exponent] = True
            negative_table_points += unit & 1
    if gauge is not None and gauge != 0:
        gauge_rotations += sum(occupied)
    return {"atlas_reads": len(choices), "table_loads": mixed_calls,
            "mixed_add_calls": mixed_calls,
            "nontrivial_mixed_adds": nontrivial_mixed,
            "occupied_buckets": sum(occupied),
            "nontrivial_final_merge": int(all(occupied)),
            "nontrivial_final_tau": int(occupied[1]),
            "gauge_rotations": gauge_rotations,
            "negative_table_points": negative_table_points}


def summarize(rows):
    result = {}
    for key in rows[0]:
        values = sorted(row[key] for row in rows)
        result[key] = {"total": sum(values), "min": values[0],
                       "median_low": values[(len(values) - 1) // 2],
                       "median_high": values[len(values) // 2],
                       "p95_nearest_rank": values[(95 * len(values) - 1) // 100],
                       "max": values[-1],
                       "histogram": {str(value): count
                                     for value, count in sorted(Counter(values).items())}}
    return result


def main():
    source = NATIVE / "fresh-inputs.json"
    panel = json.loads(source.read_text())
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == panel["count"] == 4096
    frontier_source = FRONTIER / "screen-result.json"
    frontier = json.loads(frontier_source.read_text())
    assert digest(POWER16 / "atlas-w8.bin") == digest(
        FRONTIER / "w8-d256" / "atlas-w8.bin")
    atlas_cache = {}
    atlases = {}
    for count in (16, 17, 18, 19):
        layout = frontier["best"][str(count)][0]
        pairs = list(zip(layout["widths"], layout["bounds"]))
        for pair in pairs:
            if pair not in atlas_cache:
                atlas_cache[pair] = load_power_atlas(*pair)
        atlases[str(count)] = [atlas_cache[pair][0] for pair in pairs]
    radix_path = RADIX384 / "atlas.bin"
    radix = Radix384Atlas(radix_path)
    radix_receipt = json.loads((RADIX384 / "screen-result.json").read_text())
    assert radix.count == radix_receipt["seed_count"]
    assert radix_path.stat().st_size == radix_receipt["atlas_bytes"]

    result = {"schema": "prime-j0-tau-frontier-cost-v1",
              "timing_class": "exact_call_count_diagnostic",
              "source_sha256": digest(Path(__file__)),
              "input_sha256": digest(source),
              "frontier_sha256": digest(frontier_source),
              "group_source_sha256": digest(GROUP_SOURCE),
              "radix384_atlas_sha256": digest(radix_path),
              "power_atlas_sha256": {f"w{width}-d{bound}": digest(path)
                                     for (width, bound), (_, path)
                                     in sorted(atlas_cache.items())},
              "cases": len(scalars), "layouts": {}}
    for label in ("radix384", "16", "17", "18", "19"):
        if label == "radix384":
            widths = [384] * 15
            bounds = [253] * 15
            selected = [radix] * 15
            point_slots = 15 * radix.count
            retained = point_slots * 64 + radix_path.stat().st_size
            assert point_slots * 64 == radix_receipt["point_payload_bytes"]
        else:
            layout = frontier["best"][label][0]
            widths, bounds = layout["widths"], layout["bounds"]
            selected = atlases[label]
            point_slots = layout["point_slots"]
            retained = layout["retained_before_metadata"]
        rows = [calls(recode(scalar, widths, bounds, selected)) for scalar in scalars]
        result["layouts"][label] = {
            "widths": widths, "bounds": bounds,
            "point_slots": point_slots,
            "retained_before_metadata": retained,
            "call_counts": summarize(rows)}
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for label, row in result["layouts"].items():
        counts = row["call_counts"]
        print(label, row["retained_before_metadata"],
              counts["mixed_add_calls"]["total"],
              counts["gauge_rotations"]["total"])


if __name__ == "__main__":
    main()
