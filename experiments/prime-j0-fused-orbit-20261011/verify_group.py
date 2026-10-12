#!/usr/bin/env python3
"""Pair fused records and direct-index codes on a fresh scalar panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ADIC = HERE.parent / "prime-j0-adic-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("fused_group_control", ADIC / "verify_group.py")
adic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adic)
SPEC2 = importlib.util.spec_from_file_location("fused_digit_reference", HERE / "verify_atlas.py")
reference = importlib.util.module_from_spec(SPEC2)
SPEC2.loader.exec_module(reference)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class FusedFullAtlas:
    def __init__(self, path):
        raw = path.read_bytes()
        magic, radix, classes, self.count = struct.unpack_from("<4sIII", raw)
        assert (magic, radix, classes, self.count) == (b"FO18", 1024, 174_764, 83_051)
        seed_start = 16 + 8 * classes
        assert len(raw) == seed_start + 4 * self.count
        self.records = memoryview(raw)[16:seed_start]
        self.seeds = memoryview(raw)[seed_start:]
        self.digest = digest(path)
        assert self.seed(0) == (0, 0)

    def seed(self, seed_id):
        assert 0 <= seed_id < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * seed_id)

    def decode(self, a, b):
        ra, rb = a % 1024, b % 1024
        class_index, transform = adic.index.canonicalize(ra, rb)
        code, da, db = struct.unpack_from("<Ihh", self.records, 8 * class_index)
        seed_id, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < self.count and exponent < 3 and canonical_unit < 6
        unit = 2 * ((canonical_unit // 2 - transform // 2) % 3) \
            + ((canonical_unit & 1) ^ (transform & 1))
        digit = reference.inverse_transform((da, db), transform)
        assert (digit[0] % 1024, digit[1] % 1024) == (ra, rb)
        return digit, seed_id, exponent, unit


def main():
    panel = HERE / "fresh-inputs.json"
    input_check = json.loads((HERE / "input-check.json").read_bytes())
    assert input_check["status"] == "passed"
    assert input_check["input_sha256"] == digest(panel)
    terminal = adic.q.parent.TerminalAtlas(
        HERE / "atlas-r1024-terminal-fused-orbit.bin")
    atlases = {
        "fused": FusedFullAtlas(HERE / "atlas-r1024-full-fused-orbit.bin"),
        "direct_index": adic.AdicFullAtlas(
            ADIC / "atlas-r1024-full-adic-orbit.bin"),
    }
    results = {name: adic.q.parent.check_panel(
        panel, 4096, {"full": atlas, "terminal": terminal})
        for name, atlas in atlases.items()}
    assert results["fused"]["output_sha256"] == results["direct_index"]["output_sha256"]
    for field in ("mixed_additions", "gauge_rotations", "outer_tau_images",
                  "bucket_terms", "cached_seed_points"):
        assert results["fused"][field] == results["direct_index"][field], field
    receipt = {"schema": 1, "status": "passed",
               "source_sha256": digest(Path(__file__)),
               "reference_source_sha256": digest(HERE / "verify_atlas.py"),
               "index_source_sha256": digest(ADIC / "index.py"),
               "panel_sha256": digest(panel),
               "terminal_sha256": terminal.digest,
               "atlas_sha256": {name: atlas.digest for name, atlas in atlases.items()},
               "results": results}
    output = HERE / "group-check.json"
    if output.exists():
        assert json.loads(output.read_bytes()) == receipt
    else:
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
