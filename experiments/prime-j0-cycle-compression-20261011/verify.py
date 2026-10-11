#!/usr/bin/env python3
"""Independently replay compression and verify every radix residue."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "prime-j0-cycle-prune-20261011/cover-cycle-redundant.bin"
INDEPENDENT = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("compression_independent", INDEPENDENT)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def read_cover(path):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count
    return raw, seeds


def main():
    base_raw, seeds = read_cover(BASE)
    final_raw, final_seeds = read_cover(HERE / "cover-cycle-compressed.bin")
    path_raw = (HERE / "compression-path.jsonl").read_bytes()
    screen_raw = (HERE / "screen.json").read_bytes()
    screen = json.loads(screen_raw)
    assert screen["status"] == "constructed"
    assert digest(base_raw) == screen["base_cover_sha256"]
    assert digest(final_raw) == screen["cover_sha256"]
    assert digest(path_raw) == screen["path_sha256"]
    assert digest((HERE / "augment.py").read_bytes()) == \
        screen["source_sha256"]
    steps = [json.loads(line) for line in path_raw.splitlines()]
    assert len(steps) == screen["accepted_exchanges"]
    bound = json.loads((HERE.parent / "prime-j0-tau-bound-20261011/exact-check.json")
                       .read_bytes())
    assert bound["status"] == "passed"
    assert bound["rho_only_class_lower_bound_at_budget"] == \
        screen["lower_bound"] == 6_079

    canonical, nodes = independent.orbit_partition()
    node_index = {node: index for index, node in enumerate(nodes)}

    def offers(seed):
        full = set()
        tau = set()
        for map_id in range(4):
            digit = independent.action(seed, map_id)
            if independent.norm(digit) > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(digit)]]
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
    chosen = set(seeds)
    for index, row in enumerate(steps, 1):
        slot_a, slot_b = row["slot_a"], row["slot_b"]
        old_a, old_b = tuple(row["old_a_pair"]), tuple(row["old_b_pair"])
        new_cover = tuple(row["new_cover_pair"])
        new_tau = tuple(row["new_tau_pair"])
        assert row["step"] == index and 0 < slot_a != slot_b > 0
        assert seeds[slot_a] == old_a and seeds[slot_b] == old_b
        assert new_cover != new_tau
        assert new_cover not in chosen and new_tau not in chosen
        before = sum(value == 0 for value in tau_count)
        old_offers = [offers(old_a), offers(old_b)]
        cover_full, cover_tau = offers(new_cover)
        refill_full, refill_tau = offers(new_tau)
        for full, tau in old_offers:
            for target in full:
                full_count[target] -= 1
            for target in tau:
                tau_count[target] -= 1
        for target in cover_full:
            full_count[target] += 1
        for target in cover_tau:
            tau_count[target] += 1
        assert all(full_count[target] > 0
                   for full, _ in old_offers for target in full)
        for target in refill_full:
            full_count[target] += 1
        for target in refill_tau:
            tau_count[target] += 1
        after = sum(value == 0 for value in tau_count)
        assert row["rho_improvement"] == before - after > 0
        assert row["rho_only_classes"] == after >= screen["lower_bound"]
        chosen.remove(old_a)
        chosen.remove(old_b)
        chosen.add(new_cover)
        chosen.add(new_tau)
        seeds[slot_a], seeds[slot_b] = new_cover, new_tau
    assert seeds == final_seeds and min(full_count) > 0
    assert sum(value == 0 for value in tau_count) == \
        screen["final_rho_only_classes"]

    best = [None] * len(nodes)
    for seed_id, seed in enumerate(final_seeds):
        for map_id in range(4):
            digit = independent.action(seed, map_id)
            value = independent.norm(digit)
            if value > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(digit)]]
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
        digit = independent.action(final_seeds[seed_id], map_id)
        actual = {independent.residue(value)
                  for value in independent.unit_images(digit)}
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
               "lower_bound": screen["lower_bound"],
               "gap": map_counts[3] - screen["lower_bound"],
               "exchanges_replayed": len(steps),
               "cover_sha256": digest(final_raw),
               "screen_sha256": digest(screen_raw),
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "independent_actions_sha256": digest(INDEPENDENT.read_bytes())}
    (HERE / "check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
