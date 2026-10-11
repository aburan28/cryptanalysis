#!/usr/bin/env python3
"""Check each native tau-only record and all inverse unit transforms."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "prime-j0-dual-orbit-20261011/build_native_atlas.py"
SPEC = importlib.util.spec_from_file_location("tau_exact_native_verify_base", BASE)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
cover = base.cover
index = base.index


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "atlas-r1024-full-tau-exact.bin").read_bytes()
    builder = json.loads((HERE / "native-atlas.json").read_bytes())
    assert builder["atlas_sha256"] == digest(raw)
    magic, radix, classes, seed_count = struct.unpack_from("<4sIII", raw)
    assert (magic, radix, classes, seed_count) == \
        (b"DR20", 1024, 174_764, 73_417)
    seed_start = 16 + 8 * classes
    assert len(raw) == seed_start + 4 * seed_count
    seeds = list(struct.iter_unpack("<hh", raw[seed_start:]))
    assert seeds[0] == (0, 0)
    records = []
    for expected, (class_index, pair) in enumerate(index.representatives()):
        assert class_index == expected
        code, a, b = struct.unpack_from("<Ihh", raw, 16 + 8 * class_index)
        seed_id, map_id, unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < seed_count and map_id < 3 and unit < 6
        digit = cover.screen.units(cover.mapped(seeds[seed_id], map_id))[unit]
        assert digit == (a, b)
        assert (a % radix, b % radix) == pair
        assert cover.screen.norm(digit) <= radix * radix
        records.append((digit, seed_id, map_id, unit))
    assert len(records) == classes
    for ra in range(radix):
        for rb in range(radix):
            class_index, transform = index.canonicalize(ra, rb)
            digit, seed_id, map_id, unit = records[class_index]
            inverse = 2 * ((3 - transform // 2) % 3) + (transform & 1)
            rotated = cover.screen.units(digit)[inverse]
            assert (rotated[0] % radix, rotated[1] % radix) == (ra, rb)
            unit_code = 2 * ((unit // 2 + 3 - transform // 2) % 3) \
                + ((unit & 1) ^ (transform & 1))
            assert cover.screen.units(cover.mapped(seeds[seed_id],
                                                   map_id))[unit_code] == rotated
    result = {"schema": 1, "status": "passed", "classes": classes,
              "residues": radix * radix, "seed_count": seed_count,
              "atlas_sha256": digest(raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_index_sha256": digest(Path(index.__file__).read_bytes())}
    (HERE / "native-atlas-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
