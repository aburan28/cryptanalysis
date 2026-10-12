#!/usr/bin/env python3
"""Build and independently verify the compressed-cover native DR20 atlas."""

from collections import Counter
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
CANDIDATE = EXPERIMENTS / "prime-j0-cycle-compression-20261011"
BASE = EXPERIMENTS / "prime-j0-dual-orbit-20261011/build_native_atlas.py"
INDEPENDENT = EXPERIMENTS / "prime-j0-dual-orbit-20261011/verify_cover.py"
ATLAS = HERE / "atlas-r1024-full-dual-compressed.bin"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("redundant_native_base", BASE)
independent = load("redundant_native_independent", INDEPENDENT)
index = base.index


def digest(raw):
    return sha256(raw).hexdigest()


def write_json(path, record):
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def build():
    cover_raw = (CANDIDATE / "cover-cycle-compressed.bin").read_bytes()
    check = json.loads((CANDIDATE / "check.json").read_bytes())
    assert check["status"] == "passed" and digest(cover_raw) == \
        check["cover_sha256"]
    magic, radix, classes, count, mask = struct.unpack_from(
        "<4sIIII", cover_raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    seed_start = 20 + 4 * classes
    seed_bytes = cover_raw[seed_start:]
    seeds = list(struct.iter_unpack("<hh", seed_bytes))
    canonical, nodes, _, _ = base.cover.parent.full_classes()
    node_index = {node: i for i, node in enumerate(nodes)}
    records = bytearray()
    maps = Counter()
    for expected, (class_index, (a, b)) in enumerate(index.representatives()):
        assert class_index == expected
        class_slot = node_index[canonical[a * radix + b]]
        code = struct.unpack_from("<I", cover_raw, 20 + 4 * class_slot)[0]
        seed_id, map_id = code >> 4, code & 15
        assert seed_id < count and map_id < 4
        mapped = base.cover.mapped(seeds[seed_id], map_id)
        matches = [(unit, digit) for unit, digit in enumerate(
            base.cover.screen.units(mapped))
            if digit[0] % radix == a and digit[1] % radix == b]
        assert matches
        unit, digit = matches[0]
        assert base.cover.screen.norm(digit) <= radix * radix
        records.extend(struct.pack("<Ihh", (seed_id << 5) |
                                   (map_id << 3) | unit, *digit))
        maps[map_id] += 1
    binary = struct.pack("<4sIII", b"DR20", radix, classes, count) \
        + records + seed_bytes
    assert len(binary) == 1_667_480
    ATLAS.write_bytes(binary)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "cover_sha256": digest(cover_raw),
               "atlas_sha256": digest(binary), "atlas_bytes": len(binary),
               "seed_count": count, "classes": classes,
               "map_class_counts": dict(sorted(maps.items())),
               "affine_entries": 12 * count + 9_288}
    write_json(HERE / "native-atlas.json", receipt)
    print(json.dumps(receipt, sort_keys=True))


def verify():
    raw = ATLAS.read_bytes()
    builder = json.loads((HERE / "native-atlas.json").read_bytes())
    assert builder["source_sha256"] == digest(Path(__file__).read_bytes())
    assert builder["atlas_sha256"] == digest(raw)
    magic, radix, classes, count = struct.unpack_from("<4sIII", raw)
    assert (magic, radix, classes, count) == \
        (b"DR20", 1024, 174_764, 67_338)
    start = 16 + 8 * classes
    assert len(raw) == start + 4 * count
    seeds = list(struct.iter_unpack("<hh", raw[start:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count
    records = []
    for expected, (class_index, pair) in enumerate(index.representatives()):
        assert class_index == expected
        code, a, b = struct.unpack_from("<Ihh", raw, 16 + 8 * class_index)
        seed_id, map_id, unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < count and map_id < 4 and unit < 6
        mapped = independent.action(seeds[seed_id], map_id)
        digit = independent.unit_images(mapped)[unit]
        assert digit == (a, b)
        assert (a % radix, b % radix) == pair
        assert independent.norm(digit) <= radix * radix
        records.append((digit, mapped, unit))
    for ra in range(radix):
        for rb in range(radix):
            class_index, transform = index.canonicalize(ra, rb)
            digit, mapped, unit = records[class_index]
            inverse = 2 * ((3 - transform // 2) % 3) + (transform & 1)
            rotated = independent.unit_images(digit)[inverse]
            assert (rotated[0] % radix, rotated[1] % radix) == (ra, rb)
            unit_code = 2 * ((unit // 2 + 3 - transform // 2) % 3) \
                + ((unit & 1) ^ (transform & 1))
            assert independent.unit_images(mapped)[unit_code] == rotated
    receipt = {"schema": 1, "status": "passed", "classes": classes,
               "residues": radix * radix, "seed_count": count,
               "atlas_sha256": digest(raw),
               "source_sha256": digest(Path(__file__).read_bytes()),
               "independent_actions_sha256": digest(INDEPENDENT.read_bytes()),
               "independent_index_sha256": digest(Path(index.__file__).read_bytes())}
    write_json(HERE / "native-atlas-check.json", receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    args = parser.parse_args()
    (build if args.action == "build" else verify)()
