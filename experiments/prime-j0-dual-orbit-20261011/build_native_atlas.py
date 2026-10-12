#!/usr/bin/env python3
"""Reindex the rho0 cover into aligned direct-class native records."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("dual_native_cover", HERE / "screen.py")
cover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cover)
INDEXSPEC = importlib.util.spec_from_file_location(
    "dual_native_index", ROOT / "prime-j0-adic-orbit-20261011/index.py")
index = importlib.util.module_from_spec(INDEXSPEC)
INDEXSPEC.loader.exec_module(index)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    source = HERE / "cover-lowcost-rho0.bin"
    raw = source.read_bytes()
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seed_count, mask) == \
        (b"LC19", 1024, 174_764, 67_338, 0b1111)
    code_start = 20
    seed_start = code_start + 4 * classes
    assert len(raw) == seed_start + 4 * seed_count
    seed_bytes = raw[seed_start:]
    seeds = list(struct.iter_unpack("<hh", seed_bytes))
    assert seeds[0] == (0, 0)
    canonical, nodes, _, _ = cover.parent.full_classes()
    assert len(nodes) == classes
    node_index = {node: i for i, node in enumerate(nodes)}
    records = bytearray()
    map_counts = Counter()
    for expected, (class_index, (a, b)) in enumerate(index.representatives()):
        assert class_index == expected
        node = canonical[a * radix + b]
        old_index = node_index[node]
        old_code = struct.unpack_from("<I", raw, code_start + 4 * old_index)[0]
        seed_id, map_id = old_code >> 4, old_code & 15
        assert seed_id < seed_count and map_id < 4
        mapped = cover.mapped(seeds[seed_id], map_id)
        hits = [(unit, digit) for unit, digit in enumerate(cover.screen.units(mapped))
                if digit[0] % radix == a and digit[1] % radix == b]
        assert hits
        unit, digit = hits[0]
        assert cover.screen.norm(digit) <= radix * radix
        assert all(-32768 <= value <= 32767 for value in digit)
        native_code = (seed_id << 5) | (map_id << 3) | unit
        records.extend(struct.pack("<Ihh", native_code, *digit))
        map_counts[map_id] += 1
    assert len(records) == 8 * classes
    output = HERE / "atlas-r1024-full-dual-rho0.bin"
    output.write_bytes(struct.pack("<4sIII", b"DR20", radix, classes,
                                   seed_count) + records + seed_bytes)
    terminal = ROOT / "prime-j0-fused-orbit-20261011/atlas-r1024-terminal-fused-orbit.bin"
    entries = 12 * seed_count + 9_288
    receipt = {"schema": 1, "status": "constructed", "mode": "rho0",
               "generator_sha256": digest(Path(__file__)),
               "cover_sha256": digest(source), "atlas_sha256": digest(output),
               "terminal_sha256": digest(terminal), "classes": classes,
               "seed_count": seed_count, "map_class_counts": dict(sorted(map_counts.items())),
               "atlas_bytes": output.stat().st_size,
               "affine_entries": entries, "affine_payload_bytes": 64 * entries}
    (HERE / "native-atlas.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
