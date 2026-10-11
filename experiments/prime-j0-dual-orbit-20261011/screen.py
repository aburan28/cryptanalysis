#!/usr/bin/env python3
"""Exact residue-cover screen for tau and split norm-seven endomorphisms."""

from collections import Counter
from hashlib import sha256
import heapq
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "prime-j0-power2-residual-20261010/build_atlas.py"
PANEL = ROOT / "prime-j0-adic-orbit-20261011/fresh-inputs.json"
SPEC = importlib.util.spec_from_file_location("dual_orbit_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
screen = parent.screen
RADIX = 1024
NORM_LIMIT = RADIX * RADIX
WINDOWS = 12
TERMINAL_BOUND = 149
MAP_NAMES = ("one", "tau", "tau2", "rho", "tau_rho", "tau2_rho",
             "rho_bar", "tau_rho_bar", "tau2_rho_bar")
MODES = (("tau", 3), ("tau_rho", 6), ("tau_rho_both", 9))
LAMBDA_TAU = (-screen.V[0] * pow(screen.V[1], -1, screen.ORDER)) % screen.ORDER


def digest(raw):
    return sha256(raw).hexdigest()


def rho(pair):
    a, b = pair
    return a - 3 * b, a + 4 * b


def rho_bar(pair):
    a, b = pair
    return 4 * a + 3 * b, b - a


def mapped(pair, map_id):
    branch, exponent = divmod(map_id, 3)
    if branch == 1:
        pair = rho(pair)
    elif branch == 2:
        pair = rho_bar(pair)
    for _ in range(exponent):
        pair = screen.tau(pair)
    return pair


def offers_for_seed(pair, canonical, node_index):
    result = []
    seen = set()
    for map_id in range(len(MAP_NAMES)):
        digit = mapped(pair, map_id)
        if screen.norm(digit) > NORM_LIMIT:
            continue
        node = canonical[screen.index(digit, RADIX)]
        target = node_index[node]
        if target not in seen:
            seen.add(target)
            result.append((target, map_id))
    assert result and result[0][1] == 0
    return tuple(result)


def greedy(mode, limit, nodes, direct, norms, canonical, all_offers):
    size = len(nodes)
    offers = [tuple(entry for entry in row if entry[1] < limit)
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
    heaps = [[] for _ in range(limit + 1)]
    for index, count in enumerate(gain):
        if count and not selected[index]:
            heapq.heappush(heaps[count], (norms[index], index))
    maximum = limit
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
                    heapq.heappush(heaps[gain[provider]],
                                   (norms[provider], provider))
    assert all(covered) and all(pair is not None for pair in assigned)
    map_uses = Counter()
    for index, (seed_id, map_id) in enumerate(assigned):
        digit = mapped(seeds[seed_id], map_id)
        assert screen.norm(digit) <= NORM_LIMIT
        assert canonical[screen.index(digit, RADIX)] == nodes[index]
        map_uses[MAP_NAMES[map_id]] += 1

    binary = bytearray(struct.pack("<4sIIII", b"DO19", RADIX, size,
                                   len(seeds), limit))
    for seed_id, map_id in assigned:
        binary.extend(struct.pack("<I", seed_id << 4 | map_id))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / f"cover-{mode}.bin"
    output.write_bytes(binary)
    panel = replay_panel(assigned, seeds, nodes, canonical)
    return {"mode": mode, "maps": list(MAP_NAMES[:limit]),
            "seed_count": len(seeds), "selected_gain": dict(sorted(selected_gain.items())),
            "map_uses": dict(sorted(map_uses.items())),
            "affine_slots": WINDOWS * len(seeds) + 9_288,
            "affine_payload_bytes": 64 * (WINDOWS * len(seeds) + 9_288),
            "full_atlas_bytes": len(binary), "full_atlas_sha256": digest(binary),
            "design_panel": panel}


def decode(ra, rb, assigned, seeds, canonical, node_index):
    node = canonical[ra * RADIX + rb]
    seed_id, map_id = assigned[node_index[node]]
    base_digit = mapped(seeds[seed_id], map_id)
    matches = [digit for digit in screen.units(base_digit)
               if digit[0] % RADIX == ra and digit[1] % RADIX == rb]
    assert matches
    digit = matches[0]
    assert screen.norm(digit) <= NORM_LIMIT
    return digit, seed_id, map_id


def replay_panel(assigned, seeds, nodes, canonical):
    node_index = {node: index for index, node in enumerate(nodes)}
    panel = json.loads(PANEL.read_bytes())
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == 4096
    map_terms = Counter()
    active_branches = Counter()
    additions = 0
    terminal_maximum = 0
    terminal_failures = 0
    output_hash = sha256()
    for scalar in scalars:
        a, b = screen.representative(scalar % screen.ORDER)
        assert (a + b * LAMBDA_TAU - scalar) % screen.ORDER == 0
        start = a, b
        place = 1
        reconstruction = [0, 0]
        nonzero = 0
        branches = set()
        for _ in range(WINDOWS):
            digit, seed_id, map_id = decode(a % RADIX, b % RADIX,
                                            assigned, seeds, canonical, node_index)
            reconstruction[0] += place * digit[0]
            reconstruction[1] += place * digit[1]
            if seed_id:
                nonzero += 1
                map_terms[MAP_NAMES[map_id]] += 1
                branches.add(map_id // 3)
            assert (a - digit[0]) % RADIX == (b - digit[1]) % RADIX == 0
            a, b = (a - digit[0]) // RADIX, (b - digit[1]) // RADIX
            place *= RADIX
        terminal_norm = screen.norm((a, b))
        terminal_maximum = max(terminal_maximum, terminal_norm)
        terminal_failures += terminal_norm >= TERMINAL_BOUND * TERMINAL_BOUND
        reconstruction[0] += place * a
        reconstruction[1] += place * b
        nonzero += (a, b) != (0, 0)
        assert tuple(reconstruction) == start
        additions += max(0, nonzero - 1)
        for branch in branches:
            active_branches[branch] += 1
        output_hash.update(int(a).to_bytes(8, "little", signed=True))
        output_hash.update(int(b).to_bytes(8, "little", signed=True))
    return {"cases": len(scalars), "input_sha256": digest(PANEL.read_bytes()),
            "mixed_additions": additions,
            "map_terms": dict(sorted(map_terms.items())),
            "active_branch_cases": {str(k): v for k, v in sorted(active_branches.items())},
            "terminal_maximum_norm": terminal_maximum,
            "terminal_bound_failures": terminal_failures,
            "terminal_stream_sha256": output_hash.hexdigest()}


def main():
    assert screen.norm(rho((7, -5))) == 7 * screen.norm((7, -5))
    assert screen.norm(rho_bar((7, -5))) == 7 * screen.norm((7, -5))
    canonical, nodes, direct, cycles = parent.full_classes()
    assert len(nodes) == 174_764 and len(cycles) == 513
    node_index = {node: index for index, node in enumerate(nodes)}
    norms = [screen.norm(direct[node]) for node in nodes]
    all_offers = [offers_for_seed(direct[node], canonical, node_index)
                  for node in nodes]
    coverage = Counter(len(row) for row in all_offers)
    modes = [greedy(name, limit, nodes, direct, norms, canonical, all_offers)
             for name, limit in MODES]
    receipt = {"schema": 1, "status": "screened",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "parent_source_sha256": digest(PARENT.read_bytes()),
               "screen_source_sha256": digest(Path(screen.__file__).read_bytes()),
               "panel_sha256": digest(PANEL.read_bytes()),
               "unit_classes": len(nodes),
               "maximum_map_coverage_histogram": dict(sorted(coverage.items())),
               "exact_three_image_seed_reference": 73_417,
               "modes": modes}
    (HERE / "screen.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"modes": [{"mode": row["mode"],
                                 "seed_count": row["seed_count"],
                                 "affine_payload_bytes": row["affine_payload_bytes"],
                                 "terminal_bound_failures": row["design_panel"]["terminal_bound_failures"]}
                                for row in modes]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
