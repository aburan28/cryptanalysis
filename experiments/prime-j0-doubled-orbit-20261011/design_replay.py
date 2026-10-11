#!/usr/bin/env python3
"""Recode the inherited design panel with a doubled-image bucket."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "prime-j0-cycle-compression-20261011"
SOURCE = ROOT / "prime-j0-orbit-swap-20261011/replay_holdout.py"
SPEC = importlib.util.spec_from_file_location("doubled_replay_parent", SOURCE)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
dual = parent.dual


def digest(raw):
    return sha256(raw).hexdigest()


def load(raw, mask):
    magic, radix, classes, count, actual_mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, actual_mask) == \
        (b"LP21", 1024, 174_764, 67_338, mask)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    assignments = [divmod(value, 16) for (value,) in
                   struct.iter_unpack("<I", raw[20:offset])]
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    return assignments, seeds


def recode(scalar, assignments, seeds, canonical, node_index):
    a, b = dual.screen.representative(scalar % dual.screen.ORDER)
    start = a, b
    assert (a + b * dual.LAMBDA_TAU - scalar) % dual.screen.ORDER == 0
    reconstructed = [0, 0]
    place = 1
    counts = Counter()
    for _ in range(12):
        residue = (a % 1024) * 1024 + b % 1024
        seed_id, map_id = assignments[node_index[canonical[residue]]]
        seed = seeds[seed_id]
        mapped = (2 * seed[0], 2 * seed[1]) if map_id == 4 \
            else dual.mapped(seed, map_id)
        matches = [digit for digit in dual.screen.units(mapped)
                   if digit[0] % 1024 == a % 1024
                   and digit[1] % 1024 == b % 1024]
        assert matches
        digit = matches[0]
        assert dual.screen.norm(digit) <= 1024 * 1024
        reconstructed[0] += place * digit[0]
        reconstructed[1] += place * digit[1]
        a, b = (a - digit[0]) // 1024, (b - digit[1]) // 1024
        place *= 1024
        if seed_id:
            counts[f"map_{map_id}"] += 1
            counts[f"active_{map_id}"] = 1
            counts["nonzero_full_window"] += 1
    assert dual.screen.norm((a, b)) < 149 * 149
    reconstructed[0] += place * a
    reconstructed[1] += place * b
    assert tuple(reconstructed) == start
    return counts, dual.screen.norm((a, b))


def main():
    old_raw = (BASE / "cover-cycle-compressed.bin").read_bytes()
    new_raw = (HERE / "cover-doubled.bin").read_bytes()
    old_assign, old_seeds = load(old_raw, 15)
    new_assign, new_seeds = load(new_raw, 31)
    assert old_seeds == new_seeds
    panel_raw = (BASE / "holdout-inputs.json").read_bytes()
    panel = json.loads(panel_raw)
    assert len(panel["scalars_hex"]) == 4_096
    canonical, nodes, _, _ = dual.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    totals = {"parent": Counter(), "doubled": Counter()}
    transitions = Counter()
    for text in panel["scalars_hex"]:
        scalar = int(text, 16)
        old, old_terminal = recode(
            scalar, old_assign, old_seeds, canonical, node_index)
        new, new_terminal = recode(
            scalar, new_assign, new_seeds, canonical, node_index)
        for name, counts, terminal in (("parent", old, old_terminal),
                                       ("doubled", new, new_terminal)):
            totals[name].update(counts)
            totals[name]["max_terminal_norm"] = max(
                totals[name]["max_terminal_norm"], terminal)
        transitions[(bool(old["active_3"]), bool(new["active_3"]),
                     bool(new["active_4"]))] += 1
    receipt = {"schema": 1, "status": "screened",
               "timing_class": "path_diagnostic",
               "panel_role": "inherited_design_panel",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "base_cover_sha256": digest(old_raw),
               "cover_sha256": digest(new_raw),
               "panel_sha256": digest(panel_raw),
               "cases": 4_096,
               "parent": dict(sorted(totals["parent"].items())),
               "doubled": dict(sorted(totals["doubled"].items())),
               "activation_transitions": [
                   {"parent_rho": old, "doubled_rho": new,
                    "doubled_double": doubled, "cases": count}
                   for (old, new, doubled), count in sorted(transitions.items())]}
    (HERE / "design-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("parent", "doubled", "activation_transitions")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
