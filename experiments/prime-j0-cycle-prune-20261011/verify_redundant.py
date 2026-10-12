#!/usr/bin/env python3
"""Independently replay redundant swaps and audit every radix residue."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("redundant_independent", SOURCE)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def read_cover(path):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    start = 20 + 4 * classes
    assert len(raw) == start + 4 * count
    seeds = list(struct.iter_unpack("<hh", raw[start:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count
    return raw, seeds


def main():
    source_raw, seeds = read_cover(HERE / "cover-cycle-refined.bin")
    final_raw, final_seeds = read_cover(HERE / "cover-cycle-redundant.bin")
    path_raw = (HERE / "redundant-path.jsonl").read_bytes()
    screen_raw = (HERE / "redundant-screen.json").read_bytes()
    screen = json.loads(screen_raw)
    assert digest(source_raw) == screen["refined_cover_sha256"]
    assert digest(final_raw) == screen["cover_sha256"]
    assert digest(path_raw) == screen["path_sha256"]
    assert digest((HERE / "augment_redundant.py").read_bytes()) == \
        screen["source_sha256"]
    steps = [json.loads(line) for line in path_raw.splitlines()]
    assert len(steps) == screen["swaps"]

    canonical, nodes = independent.orbit_partition()
    node_index = {node: index for index, node in enumerate(nodes)}

    def offers(seed):
        full = set()
        tau = set()
        for map_id in range(4):
            image = independent.action(seed, map_id)
            if independent.norm(image) > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(image)]]
            full.add(target)
            if map_id < 3:
                tau.add(target)
        return full, tau

    full_count = [0] * len(nodes)
    tau_count = [0] * len(nodes)
    for seed in seeds:
        full, tau = offers(seed)
        for target in full:
            full_count[target] += 1
        for target in tau:
            tau_count[target] += 1
    assert min(full_count) > 0
    initial = sum(value == 0 for value in tau_count)
    assert initial == screen["initial_rho_only_classes"]
    selected = set(seeds)
    for index, row in enumerate(steps, 1):
        slot = row["slot"]
        old = tuple(row["old_pair"])
        new = tuple(row["new_pair"])
        assert row["step"] == index and slot > 0
        assert seeds[slot] == old and new not in selected
        old_full, old_tau = offers(old)
        new_full, new_tau = offers(new)
        assert all(full_count[target] > 1 for target in old_full)
        before = sum(value == 0 for value in tau_count)
        for target in old_full:
            full_count[target] -= 1
        for target in old_tau:
            tau_count[target] -= 1
        for target in new_full:
            full_count[target] += 1
        for target in new_tau:
            tau_count[target] += 1
        after = sum(value == 0 for value in tau_count)
        assert row["rho_gain"] == before - after > 0
        assert row["rho_only_classes"] == after
        selected.remove(old)
        selected.add(new)
        seeds[slot] = new
    assert seeds == final_seeds and min(full_count) > 0
    assert sum(value == 0 for value in tau_count) == \
        screen["final_rho_only_classes"]

    best = [None] * len(nodes)
    for seed_id, seed in enumerate(final_seeds):
        for map_id in range(4):
            image = independent.action(seed, map_id)
            value = independent.norm(image)
            if value > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(image)]]
            key = (map_id == 3, value, map_id, seed_id)
            if best[target] is None or key < best[target][0]:
                best[target] = (key, seed_id, map_id)
    assert all(best)
    used = set()
    map_counts = Counter()
    residues = 0
    for index, node in enumerate(nodes):
        code = struct.unpack_from("<I", final_raw, 20 + 4 * index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert (seed_id, map_id) == best[index][1:]
        image = independent.action(final_seeds[seed_id], map_id)
        actual = {independent.residue(value)
                  for value in independent.unit_images(image)}
        expected = {independent.residue(value)
                    for value in independent.unit_images(divmod(node, 1024))}
        assert actual == expected
        assert all(canonical[value] == node for value in actual)
        residues += len(actual)
        used.add(seed_id)
        map_counts[map_id] += 1
    assert residues == independent.SIZE and len(used) == len(final_seeds)
    assert map_counts[3] == sum(value == 0 for value in tau_count)
    assert dict(sorted(map_counts.items())) == \
        {int(key): value for key, value in screen["assigned_maps"].items()}
    receipt = {"schema": 1, "status": "passed",
               "seed_count": len(final_seeds), "class_count": len(nodes),
               "residues_checked": residues,
               "initial_rho_only_classes": initial,
               "final_rho_only_classes": map_counts[3],
               "swaps_replayed": len(steps),
               "cover_sha256": digest(final_raw),
               "screen_sha256": digest(screen_raw),
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "independent_actions_sha256": digest(SOURCE.read_bytes())}
    (HERE / "redundant-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
