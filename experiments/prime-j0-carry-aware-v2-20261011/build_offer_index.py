#!/usr/bin/env python3
"""Encode the fixed seed/map alternatives as a compact class CSR index."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("carry_offer_source", HERE / "screen.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
INDEX = ROOT / "prime-j0-adic-orbit-20261011/index.py"
SPEC_INDEX = importlib.util.spec_from_file_location("carry_adic_index", INDEX)
index = importlib.util.module_from_spec(SPEC_INDEX)
SPEC_INDEX.loader.exec_module(index)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    cover_raw, _, seeds = source.load_cover()
    canonical, nodes, _, _ = source.dual.parent.full_classes()
    node_index, providers = source.offer_index(seeds, canonical, nodes)
    offsets = [0]
    records = bytearray()
    for expected, (class_index, (ra, rb)) in enumerate(index.representatives()):
        assert class_index == expected
        source_index = node_index[canonical[ra * 1024 + rb]]
        for seed_id, map_id, mapped in providers[source_index]:
            matches = [(unit, digit) for unit, digit in enumerate(
                source.dual.screen.units(mapped))
                if digit[0] % 1024 == ra and digit[1] % 1024 == rb]
            assert matches
            for unit, digit in matches:
                assert all(-32768 <= coordinate <= 32767 for coordinate in digit)
                code = (seed_id << 5) | (map_id << 3) | unit
                records.extend(struct.pack("<Ihh", code, *digit))
        offsets.append(len(records) // 8)
    assert len(offsets) == 174_765
    assert offsets[-1] >= 246_429
    header = struct.pack("<4sIII", b"CA12", 1024, 174_764, offsets[-1])
    raw = header + struct.pack(f"<{len(offsets)}I", *offsets) + records
    assert len(raw) == 16 + 4 * len(offsets) + len(records)
    output = HERE / "offers-r1024-dual-priority.bin"
    output.write_bytes(raw)
    receipt = {"schema": 1, "status": "constructed", "classes": 174_764,
               "offers": offsets[-1], "bytes": len(raw),
               "cover_sha256": digest(cover_raw),
               "screen_sha256": digest((HERE / "screen.py").read_bytes()),
               "builder_sha256": digest(Path(__file__).read_bytes()),
               "offer_index_sha256": digest(raw)}
    (HERE / "offer-index.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
