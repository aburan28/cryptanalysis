#!/usr/bin/env python3
"""Count occupied unit phases, including exact terminal codes, for both paths."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("phase_carry_screen", HERE / "screen.py")
screen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(screen)
TERMINAL = ROOT / "prime-j0-fused-orbit-20261011/atlas-r1024-terminal-fused-orbit.bin"


def terminal_code(raw, a, b):
    magic, bound, b_min, b_max, count, pairs, reserved = struct.unpack_from(
        "<4sHhhIIH", raw)
    assert (magic, bound, reserved) == (b"R103", 149, 0)
    assert b_min <= b <= b_max
    row_count = b_max - b_min + 1
    a_min, length, row_offset = struct.unpack_from(
        "<hHI", raw, 20 + 8 * (b - b_min))
    assert a_min <= a < a_min + length
    code_start = 20 + 8 * row_count
    code = struct.unpack_from("<I", raw,
                              code_start + 4 * (row_offset + a - a_min))[0]
    seed, exponent, unit = code >> 5, (code >> 3) & 3, code & 7
    assert seed < count and exponent < 3 and unit < 6
    seed_start = code_start + 4 * pairs
    base = struct.unpack_from("<hh", raw, seed_start + 4 * seed)
    digit = base
    for _ in range(exponent):
        digit = screen.dual.screen.tau(digit)
    assert screen.dual.screen.units(digit)[unit] == (a, b)
    return seed, exponent, unit


def phases(state, terminal):
    masks = [0, 0, 0, 0]
    for _, _, seed, map_id, unit in state[4]:
        if seed:
            masks[map_id] |= 1 << (unit // 2)
    a, b = state[:2]
    seed, exponent, unit = terminal_code(terminal, a, b)
    if seed:
        masks[exponent] |= 1 << (unit // 2)
    rotations = sum(mask.bit_count() - 1 + int(not mask & 1)
                    for mask in masks if mask)
    return tuple(masks), rotations


def main():
    raw, assignments, seeds = screen.load_cover()
    canonical, nodes, _, _ = screen.dual.parent.full_classes()
    node_index, providers = screen.offer_index(seeds, canonical, nodes)
    options = screen.make_options(canonical, node_index, providers)
    panel = json.loads((HERE / "holdout-inputs.json").read_bytes())
    cert = (HERE / "holdout-paths-width2.jsonl").read_bytes().splitlines()
    terminal_raw = TERMINAL.read_bytes()
    assert len(cert) == len(panel["scalars_hex"]) == 4096
    fixed_rotations = selected_rotations = 0
    differences = Counter()
    bucket_activation = Counter()
    for index, (scalar_hex, line) in enumerate(zip(panel["scalars_hex"], cert)):
        fixed, selected, _, _, _ = screen.replay(
            int(scalar_hex, 16), assignments, seeds, canonical,
            node_index, options, 2)
        encoded = json.loads(line)
        assert encoded["index"] == index
        assert tuple(encoded["terminal"]) == selected[:2]
        assert tuple(tuple(row) for row in encoded["digits"]) == selected[4]
        fixed_masks, fr = phases(fixed, terminal_raw)
        selected_masks, sr = phases(selected, terminal_raw)
        fixed_rotations += fr
        selected_rotations += sr
        differences[sr - fr] += 1
        for name, mask in (("fixed", fixed_masks), ("carry_aware", selected_masks)):
            bucket_activation[name] += sum(bool(value) for value in mask)
    result = {"schema": 1, "status": "phase_occupancy_screen",
              "cases": len(cert), "fixed_rotations_proxy": fixed_rotations,
              "carry_aware_rotations_proxy": selected_rotations,
              "rotation_difference_histogram": dict(sorted(differences.items())),
              "bucket_activation_sum": dict(bucket_activation),
              "terminal_sha256": sha256(terminal_raw).hexdigest(),
              "certificate_sha256": sha256(b"\n".join(cert) + b"\n").hexdigest(),
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "phase-cost.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
