#!/usr/bin/env python3
"""Replay quotient and direct-code atlases on the same scalar panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011/verify_group.py"
SPEC = importlib.util.spec_from_file_location("three_image_group", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
RADIX = 1_024


def digest(raw):
    return sha256(raw).hexdigest()


def residue(pair):
    return (pair[0] % RADIX) * RADIX + pair[1] % RADIX


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def unit_images(pair):
    images = []
    for _ in range(3):
        images.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return images


class QuotientFullAtlas:
    def __init__(self, path):
        raw = path.read_bytes()
        magic, radix, classes, self.count, word_count = struct.unpack_from(
            "<4sIIII", raw)
        assert (magic, radix, classes, word_count) == (
            b"OQ13", RADIX, 174_764, RADIX * RADIX // 64)
        mask_start = 20
        rank_start = mask_start + 8 * word_count
        code_start = rank_start + 4 * (word_count + 1)
        seed_start = code_start + 3 * classes
        assert len(raw) == seed_start + 4 * self.count
        self.words = struct.unpack_from(f"<{word_count}Q", raw, mask_start)
        self.prefix = struct.unpack_from(f"<{word_count + 1}I", raw, rank_start)
        self.codes = memoryview(raw)[code_start:seed_start]
        self.seeds = memoryview(raw)[seed_start:]
        self.digest = digest(raw)
        assert self.seed(0) == (0, 0)

    def seed(self, index):
        assert 0 <= index < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * index)

    def decode(self, a, b):
        target = a % RADIX, b % RADIX
        orbit = [residue(image) for image in unit_images(target)]
        canonical = min(orbit)
        transform = orbit.index(canonical)
        word_index, bit = divmod(canonical, 64)
        word = self.words[word_index]
        assert word & (1 << bit)
        index = self.prefix[word_index] + (
            word & ((1 << bit) - 1)).bit_count()
        code = int.from_bytes(self.codes[3 * index:3 * index + 3], "little")
        seed_id, exponent, canonical_unit = code >> 5, (code >> 3) & 3, code & 7
        assert seed_id < self.count and exponent <= 2 and canonical_unit < 6
        unit = 2 * ((canonical_unit // 2 - transform // 2) % 3) \
            + ((canonical_unit & 1) ^ (transform & 1))
        digit = parent.reference.coord_unit(
            parent.tau_power(self.seed(seed_id), exponent), unit)
        assert digit[0] % RADIX == target[0]
        assert digit[1] % RADIX == target[1]
        return digit, seed_id, exponent, unit


def main():
    design = sys.argv[1:] == ["--design"]
    assert design or not sys.argv[1:]
    if design:
        panel_path = HERE.parent / "prime-j0-power2-cache-budget-20261011/fresh-inputs.json"
        count = 64
    else:
        panel_path = HERE / "fresh-inputs.json"
        input_check = json.loads((HERE / "input-check.json").read_bytes())
        assert input_check["status"] == "passed"
        assert digest(panel_path.read_bytes()) == input_check["input_sha256"]
        count = 4096

    terminal = parent.TerminalAtlas(
        HERE / "atlas-r1024-terminal-orbit-quotient.bin")
    variants = {
        "quotient": {
            "full": QuotientFullAtlas(HERE / "atlas-r1024-full-orbit-quotient.bin"),
            "terminal": terminal,
        },
        "budgeted_direct": {
            "full": parent.FullAtlas(HERE.parent
                / "prime-j0-power2-cache-budget-20261011"
                / "atlas-r1024-full-cache-budget.bin"),
            "terminal": terminal,
        },
        "minimum_direct": {
            "full": parent.FullAtlas(HERE.parent
                / "prime-j0-power2-tau2-20261011"
                / "atlas-r1024-full-tau2.bin"),
            "terminal": terminal,
        },
    }
    results = {name: parent.check_panel(panel_path, count, atlases)
               for name, atlases in variants.items()}
    output_hashes = {row["output_sha256"] for row in results.values()}
    assert len(output_hashes) == 1
    assert len({row["mixed_additions"] for row in results.values()}) == 1
    assert all(row["cases"] == count for row in results.values())
    receipt = {"schema": 1, "status": "passed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "parent_verifier_sha256": digest(PARENT.read_bytes()),
               "panel_sha256": digest(panel_path.read_bytes()),
               "atlas_sha256": {
                   name: {kind: atlas.digest for kind, atlas in atlases.items()}
                   for name, atlases in variants.items()},
               "results": results}
    output = HERE / ("design-check.json" if design else "group-check.json")
    if output.exists():
        assert json.loads(output.read_text()) == receipt
    else:
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
