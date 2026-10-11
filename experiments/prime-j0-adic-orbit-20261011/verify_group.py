#!/usr/bin/env python3
"""Paired full scalar replay of direct-index and quotient atlases."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUOTIENT = ROOT / "prime-j0-orbit-quotient-20261011"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


index = load("adic_group_index", HERE / "index.py")
q = load("quotient_group_control", QUOTIENT / "verify_group.py")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class AdicFullAtlas:
    def __init__(self, path):
        raw = path.read_bytes()
        magic, radix, classes, self.count = struct.unpack_from("<4sIII", raw)
        assert (magic, radix, classes, self.count) == \
            (b"AO14", 1024, 174_764, 83_051)
        offset = 16 + 3 * classes
        assert len(raw) == offset + 4 * self.count
        self.codes = memoryview(raw)[16:offset]
        self.seeds = memoryview(raw)[offset:]
        self.digest = digest(path)
        assert self.seed(0) == (0, 0)

    def seed(self, seed_id):
        assert 0 <= seed_id < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * seed_id)

    def decode(self, a, b):
        ra, rb = a % 1024, b % 1024
        class_index, transform = index.canonicalize(ra, rb)
        offset = 3 * class_index
        code = int.from_bytes(self.codes[offset:offset + 3], "little")
        seed_id, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < self.count and exponent < 3 and canonical_unit < 6
        unit = 2 * ((canonical_unit // 2 - transform // 2) % 3) \
            + ((canonical_unit & 1) ^ (transform & 1))
        digit = q.parent.reference.coord_unit(
            q.parent.tau_power(self.seed(seed_id), exponent), unit)
        assert (digit[0] % 1024, digit[1] % 1024) == (ra, rb)
        return digit, seed_id, exponent, unit


def main():
    panel = HERE / "fresh-inputs.json"
    input_check = json.loads((HERE / "input-check.json").read_bytes())
    assert input_check["status"] == "passed"
    assert input_check["input_sha256"] == digest(panel)
    terminal = q.parent.TerminalAtlas(
        HERE / "atlas-r1024-terminal-adic-orbit.bin")
    atlases = {
        "adic": AdicFullAtlas(HERE / "atlas-r1024-full-adic-orbit.bin"),
        "quotient": q.QuotientFullAtlas(
            QUOTIENT / "atlas-r1024-full-orbit-quotient.bin"),
    }
    results = {name: q.parent.check_panel(panel, 4096,
               {"full": atlas, "terminal": terminal})
               for name, atlas in atlases.items()}
    assert results["adic"]["output_sha256"] == results["quotient"]["output_sha256"]
    for field in ("mixed_additions", "gauge_rotations", "outer_tau_images",
                  "bucket_terms", "cached_seed_points"):
        assert results["adic"][field] == results["quotient"][field], field
    receipt = {"schema": 1, "status": "passed",
               "source_sha256": digest(Path(__file__)),
               "index_source_sha256": digest(HERE / "index.py"),
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
