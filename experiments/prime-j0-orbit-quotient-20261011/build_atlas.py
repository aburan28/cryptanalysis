#!/usr/bin/env python3
"""Encode one code per unit orbit with a bitset and rank directory."""

from array import array
from collections import Counter, defaultdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011/build_atlas.py"
SPEC = importlib.util.spec_from_file_location("three_image_atlas", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
RADIX = 1_024
WORDS = RADIX * RADIX // 64
WINDOWS = 12
OVERHEAD_PROJECTION = 424


def digest(raw):
    return sha256(raw).hexdigest()


def plan_records():
    raw = (HERE / "cover-plan.bin").read_bytes()
    screen = json.loads((HERE / "screen.json").read_bytes())
    assert raw[:4] == b"OQ64"
    assert screen["cover_plan_sha256"] == digest(raw)
    cycles, segments = struct.unpack_from("<II", raw, 4)
    assert (cycles, segments) == (513, 83_051)
    assert len(raw) == 12 + 5 * segments
    grouped = defaultdict(list)
    for cycle_index, start, span in struct.iter_unpack("<HHB", raw[12:]):
        grouped[cycle_index].append((start, span))
    return grouped, digest(raw)


def build_full():
    canonical, nodes, direct, cycles = parent.parent.full_classes()
    grouped, plan_hash = plan_records()
    assert len(cycles) == len(grouped) == 513
    seeds = [(0, 0)]
    assigned = {0: (0, 0)}
    lengths = Counter()
    for cycle_index, cycle in enumerate(cycles):
        covered = set()
        for start, span in grouped[cycle_index]:
            assert start < len(cycle) and 1 <= span <= 3
            source = cycle[start]
            assert (3 ** (span - 1)) * parent.screen.norm(direct[source]) \
                <= RADIX ** 2
            lengths[span] += 1
            if source == 0:
                assert span == 1 and len(seeds) == 1
                seed_id = 0
            else:
                seed_id = len(seeds)
                seeds.append(direct[source])
            for exponent in range(span):
                position = (start + exponent) % len(cycle)
                assert position not in covered
                covered.add(position)
                target = cycle[position]
                if target == 0:
                    assert (seed_id, exponent) == (0, 0)
                else:
                    assert target not in assigned
                    assigned[target] = (seed_id, exponent)
        assert len(covered) == len(cycle)
    assert len(assigned) == len(nodes) == 174_764
    assert len(seeds) == 83_051
    assert lengths == {1: 2_117, 2: 70_155, 3: 10_779}

    words = array("Q", [0]) * WORDS
    packed_codes = bytearray()
    maximum_norm = 0
    previous = -1
    for node in nodes:
        assert previous < node
        previous = node
        word, bit = divmod(node, 64)
        assert not (words[word] >> bit) & 1
        words[word] |= 1 << bit
        seed_id, exponent = assigned[node]
        digit = parent.tau_power(seeds[seed_id], exponent)
        assert parent.screen.norm(digit) <= RADIX ** 2
        maximum_norm = max(maximum_norm, parent.screen.norm(digit))
        images = parent.screen.units(digit)
        units = [unit for unit, image in enumerate(images)
                 if parent.screen.index(image, RADIX) == node]
        assert units
        code = (seed_id << 5) | (exponent << 3) | units[0]
        assert code < 1 << 24
        packed_codes.extend(code.to_bytes(3, "little"))

    rank = array("I", [0]) * (WORDS + 1)
    for index, word in enumerate(words):
        rank[index + 1] = rank[index] + word.bit_count()
    assert rank[-1] == len(nodes)
    assert len(packed_codes) == 3 * len(nodes)
    orbit_sizes = Counter(canonical)
    exponent_residues = Counter()
    for node in nodes:
        exponent_residues[assigned[node][1]] += orbit_sizes[node]
    assert exponent_residues[2] == 64_674

    header = struct.pack("<4sIIII", b"OQ13", RADIX, len(nodes), len(seeds), WORDS)
    binary = bytearray(header)
    binary.extend(struct.pack(f"<{WORDS}Q", *words))
    binary.extend(struct.pack(f"<{WORDS + 1}I", *rank))
    binary.extend(packed_codes)
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "atlas-r1024-full-orbit-quotient.bin"
    output.write_bytes(binary)
    return {"residues": RADIX * RADIX, "unit_classes": len(nodes),
            "segment_lengths": dict(lengths), "seed_count": len(seeds),
            "word_count": WORDS, "rank_entries": len(rank),
            "code_bytes_per_class": 3,
            "exponent_residues": dict(exponent_residues),
            "maximum_decoded_norm": maximum_norm,
            "cover_plan_sha256": plan_hash,
            "atlas_bytes": len(binary), "atlas_sha256": digest(binary)}


def main():
    full = build_full()
    terminal_source = HERE.parent / "prime-j0-power2-tau2-20261011" \
        / "atlas-r1024-terminal-tau2.bin"
    terminal_raw = terminal_source.read_bytes()
    (HERE / "atlas-r1024-terminal-orbit-quotient.bin").write_bytes(terminal_raw)
    prior = json.loads((PARENT.parent / "atlas-receipt.json").read_bytes())
    terminal = prior["terminal"]
    assert terminal["atlas_sha256"] == digest(terminal_raw)
    slots = WINDOWS * full["seed_count"] + terminal["seed_count"]
    assert slots == 1_005_900
    projected = slots * 64 + full["atlas_bytes"] + terminal["atlas_bytes"] \
        + OVERHEAD_PROJECTION
    assert projected == 65_793_168 < 64 * 1024 * 1024
    receipt = {"schema": 1, "status": "constructed",
               "generator_sha256": digest(Path(__file__).read_bytes()),
               "parent_generator_sha256": digest(PARENT.read_bytes()),
               "radix": RADIX, "windows": WINDOWS,
               "full": full, "terminal": terminal,
               "affine_slots": slots, "affine_payload_bytes": slots * 64,
               "atlas_bytes": full["atlas_bytes"] + terminal["atlas_bytes"],
               "assumed_native_overhead_bytes": OVERHEAD_PROJECTION,
               "projected_native_retained_bytes": projected,
               "reported_cache_bytes": 64 * 1024 * 1024,
               "nominal_cache_headroom_bytes": 64 * 1024 * 1024 - projected}
    (HERE / "atlas-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
