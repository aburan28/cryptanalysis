#!/usr/bin/env python3
"""Verify every compressed offer and its inverse unit action."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location(
    "offer_index_arithmetic", HERE / "verify_holdout.py")
arithmetic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arithmetic)
SPEC_INDEX = importlib.util.spec_from_file_location(
    "offer_index_class", ROOT / "prime-j0-adic-orbit-20261011/index.py")
index = importlib.util.module_from_spec(SPEC_INDEX)
SPEC_INDEX.loader.exec_module(index)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "offers-r1024-dual-priority.bin").read_bytes()
    cover = (ROOT / "prime-j0-dual-orbit-20261011" /
             "cover-priority-rho0.bin").read_bytes()
    magic, radix, classes, offers = struct.unpack_from("<4sIII", raw)
    assert (magic, radix, classes) == (b"CA12", 1024, 174_764)
    offsets = struct.unpack_from(f"<{classes + 1}I", raw, 16)
    records_start = 16 + 4 * (classes + 1)
    assert len(raw) == records_start + 8 * offers
    assert offsets[0] == 0 and offsets[-1] == offers
    seeds = list(struct.iter_unpack("<hh", cover[20 + 4 * classes:]))
    assert len(seeds) == 67_338
    providers = [[] for _ in range(classes)]
    for seed_id, seed in enumerate(seeds):
        for map_id in range(4):
            digit = arithmetic.mapped(seed, map_id)
            if arithmetic.norm(digit) > radix * radix:
                continue
            class_id, _ = index.canonicalize(digit[0] % radix,
                                             digit[1] % radix)
            providers[class_id].append((seed_id, map_id, digit))
    records = []
    for class_id, pair in index.representatives():
        assert offsets[class_id] < offsets[class_id + 1]
        local = []
        for number in range(offsets[class_id], offsets[class_id + 1]):
            code, a, b = struct.unpack_from("<Ihh", raw, records_start + 8 * number)
            seed_id, map_id, unit = code >> 5, (code >> 3) & 3, code & 7
            assert seed_id < len(seeds) and map_id < 4 and unit < 6
            digit = arithmetic.unit_image(
                arithmetic.mapped(seeds[seed_id], map_id), unit)
            assert digit == (a, b)
            assert (a % radix, b % radix) == pair
            assert arithmetic.norm(digit) <= radix * radix
            local.append((digit, seed_id, map_id, unit))
        expected = []
        for seed_id, map_id, mapped in providers[class_id]:
            for unit in range(6):
                digit = arithmetic.unit_image(mapped, unit)
                if (digit[0] % radix, digit[1] % radix) == pair:
                    expected.append((digit, seed_id, map_id, unit))
        assert local == expected, class_id
        records.append(local)
    assert len(records) == classes
    for ra in range(radix):
        for rb in range(radix):
            class_id, transform = index.canonicalize(ra, rb)
            inverse = 2 * ((3 - transform // 2) % 3) + (transform & 1)
            for (digit, seed_id, map_id, unit) in records[class_id]:
                rotated = arithmetic.unit_image(digit, inverse)
                assert (rotated[0] % radix, rotated[1] % radix) == (ra, rb)
                unit_code = 2 * ((unit // 2 + 3 - transform // 2) % 3) \
                    + ((unit & 1) ^ (transform & 1))
                assert arithmetic.unit_image(
                    arithmetic.mapped(seeds[seed_id], map_id), unit_code) == rotated
    construction = json.loads((HERE / "offer-index.json").read_bytes())
    assert construction["offer_index_sha256"] == digest(raw)
    assert construction["cover_sha256"] == digest(cover)
    result = {"schema": 1, "status": "passed", "classes": classes,
              "residues": radix * radix, "offers": offers,
              "offer_index_sha256": digest(raw),
              "verifier_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "offer-index-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
