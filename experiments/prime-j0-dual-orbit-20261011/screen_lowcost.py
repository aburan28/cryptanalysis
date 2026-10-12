#!/usr/bin/env python3
"""Screen low-cost norm-seven map subsets after the full-map cover."""

from collections import Counter
from hashlib import sha256
import heapq
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("dual_orbit_screen_base", HERE / "screen.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
MODES = (("rho0", (0, 1, 2, 3)),
         ("rho0_bar0", (0, 1, 2, 3, 6)),
         ("rho0_bar012", (0, 1, 2, 3, 6, 7, 8)))


def digest(raw):
    return sha256(raw).hexdigest()


def greedy_subset(name, allowed, nodes, direct, norms, canonical, all_offers):
    size = len(nodes)
    offers = [tuple(entry for entry in row if entry[1] in allowed)
              for row in all_offers]
    providers = [[] for _ in range(size)]
    for seed, row in enumerate(offers):
        for target, _ in row:
            providers[target].append(seed)
    identity = nodes.index(0)
    selected = bytearray(size)
    covered = bytearray(size)
    selected[identity] = covered[identity] = 1
    assigned = [None] * size
    assigned[identity] = (0, 0)
    seeds = [(0, 0)]
    gain = [sum(not covered[target] for target, _ in row) for row in offers]
    heaps = [[] for _ in range(len(allowed) + 1)]
    for index, count in enumerate(gain):
        if count and not selected[index]:
            heapq.heappush(heaps[count], (norms[index], index))
    maximum = len(allowed)
    remaining = size - 1
    selected_gain = Counter()
    while remaining:
        while maximum and not heaps[maximum]:
            maximum -= 1
        assert maximum > 0
        _, index = heapq.heappop(heaps[maximum])
        if selected[index] or gain[index] != maximum:
            continue
        selected[index] = 1
        seed_id = len(seeds)
        seeds.append(direct[nodes[index]])
        selected_gain[maximum] += 1
        for target, map_id in offers[index]:
            if covered[target]:
                continue
            covered[target] = 1
            assigned[target] = (seed_id, map_id)
            remaining -= 1
            for provider in providers[target]:
                if selected[provider]:
                    continue
                gain[provider] -= 1
                if gain[provider]:
                    heapq.heappush(heaps[gain[provider]], (norms[provider], provider))
    assert all(covered) and all(pair is not None for pair in assigned)
    map_uses = Counter()
    for index, (seed_id, map_id) in enumerate(assigned):
        digit = base.mapped(seeds[seed_id], map_id)
        assert base.screen.norm(digit) <= base.NORM_LIMIT
        assert canonical[base.screen.index(digit, base.RADIX)] == nodes[index]
        map_uses[base.MAP_NAMES[map_id]] += 1
    mask = sum(1 << map_id for map_id in allowed)
    binary = bytearray(struct.pack("<4sIIII", b"LC19", base.RADIX,
                                   size, len(seeds), mask))
    for seed_id, map_id in assigned:
        binary.extend(struct.pack("<I", seed_id << 4 | map_id))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / f"cover-lowcost-{name}.bin"
    output.write_bytes(binary)
    panel = base.replay_panel(assigned, seeds, nodes, canonical)
    return {"mode": name, "allowed_map_ids": list(allowed),
            "seed_count": len(seeds), "selected_gain": dict(sorted(selected_gain.items())),
            "map_uses": dict(sorted(map_uses.items())),
            "affine_slots": base.WINDOWS * len(seeds) + 9_288,
            "affine_payload_bytes": 64 * (base.WINDOWS * len(seeds) + 9_288),
            "full_atlas_bytes": len(binary), "full_atlas_sha256": digest(binary),
            "design_panel": panel}


def main():
    canonical, nodes, direct, cycles = base.parent.full_classes()
    assert len(nodes) == 174_764 and len(cycles) == 513
    node_index = {node: index for index, node in enumerate(nodes)}
    norms = [base.screen.norm(direct[node]) for node in nodes]
    all_offers = [base.offers_for_seed(direct[node], canonical, node_index)
                  for node in nodes]
    modes = [greedy_subset(name, allowed, nodes, direct, norms,
                           canonical, all_offers)
             for name, allowed in MODES]
    receipt = {"schema": 1, "status": "screened",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "base_source_sha256": digest((HERE / "screen.py").read_bytes()),
               "panel_sha256": digest(base.PANEL.read_bytes()),
               "unit_classes": len(nodes),
               "exact_three_image_seed_reference": 73_417,
               "modes": modes}
    (HERE / "lowcost-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"modes": [{"mode": row["mode"],
                                 "seed_count": row["seed_count"],
                                 "affine_payload_bytes": row["affine_payload_bytes"],
                                 "terminal_bound_failures": row["design_panel"]["terminal_bound_failures"]}
                                for row in modes]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
