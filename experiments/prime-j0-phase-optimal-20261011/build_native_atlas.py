#!/usr/bin/env python3
"""Reindex the exact tau-only cover into the native DR20 class atlas."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "prime-j0-dual-orbit-20261011/build_native_atlas.py"
SPEC = importlib.util.spec_from_file_location("tau_exact_native_base", BASE)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
cover = base.cover
index = base.index


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    cover_raw = (HERE / "cover-phase-optimal.bin").read_bytes()
    check = json.loads((HERE / "check.json").read_bytes())
    assert check["status"] == "passed" and digest(cover_raw) == check["cover_sha256"]
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", cover_raw)
    assert (magic, radix, classes, seed_count, mask) == \
        (b"LP21", 1024, 174_764, 73_417, 7)
    seed_start = 20 + 4 * classes
    seed_bytes = cover_raw[seed_start:]
    seeds = list(struct.iter_unpack("<hh", seed_bytes))
    canonical, nodes, _, _ = cover.parent.full_classes()
    node_index = {node: i for i, node in enumerate(nodes)}
    records = bytearray()
    map_counts = Counter()
    for expected, (class_index, (a, b)) in enumerate(index.representatives()):
        assert class_index == expected
        class_slot = node_index[canonical[a * radix + b]]
        code = struct.unpack_from("<I", cover_raw, 20 + 4 * class_slot)[0]
        seed_id, map_id = code >> 4, code & 15
        assert seed_id < seed_count and map_id < 3
        mapped = cover.mapped(seeds[seed_id], map_id)
        matches = [(unit, digit) for unit, digit in enumerate(
            cover.screen.units(mapped))
            if digit[0] % radix == a and digit[1] % radix == b]
        assert matches
        unit, digit = matches[0]
        assert cover.screen.norm(digit) <= radix * radix
        assert all(-32768 <= value <= 32767 for value in digit)
        records.extend(struct.pack("<Ihh", (seed_id << 5) | (map_id << 3) | unit,
                                   *digit))
        map_counts[map_id] += 1
    binary = struct.pack("<4sIII", b"DR20", radix, classes, seed_count) \
        + records + seed_bytes
    assert len(binary) == 16 + 8 * classes + 4 * seed_count
    output = HERE / "atlas-r1024-full-phase-optimal.bin"
    output.write_bytes(binary)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "cover_sha256": digest(cover_raw), "atlas_sha256": digest(binary),
               "atlas_bytes": len(binary), "seed_count": seed_count,
               "classes": classes,
               "map_class_counts": dict(sorted(map_counts.items())),
               "affine_entries": 12 * seed_count + 9_288}
    (HERE / "native-atlas.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
