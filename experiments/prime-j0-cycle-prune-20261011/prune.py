#!/usr/bin/env python3
"""Reduce the exact tau cover while retaining full tau/rho residue coverage."""

from collections import Counter
from hashlib import sha256
import heapq
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "prime-j0-orbit-swap-20261011/optimize.py"
TAU = ROOT / "prime-j0-tau-bound-20261011/cover-tau-exact.bin"
SPEC = importlib.util.spec_from_file_location("cycle_prune_graph", SOURCE)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
dual = source.dual
TARGET_SEEDS = 67_338


def digest(raw):
    return sha256(raw).hexdigest()


def counts(selected, covers, tau_covers, size):
    full = [0] * size
    tau = [0] * size
    for seed in selected:
        for target in covers[seed]:
            full[target] += 1
        for target in tau_covers[seed]:
            tau[target] += 1
    assert min(full) > 0
    return full, tau


def read_tau_seeds():
    raw = TAU.read_bytes()
    magic, radix, classes, seeds, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seeds, mask) == \
        (b"LP21", 1024, 174_764, 73_417, 7)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * seeds
    return raw, list(struct.iter_unpack("<hh", raw[offset:]))


def prune(selected, covers, tau_covers, inverse, norms):
    size = len(inverse)
    chosen = bytearray(len(covers))
    for seed in selected:
        chosen[seed] = 1
    full, tau = counts(selected, covers, tau_covers, size)
    version = [0] * len(covers)
    heap = []

    def enqueue(seed):
        if not chosen[seed] or seed == selected[0]:
            return
        version[seed] += 1
        if any(full[target] == 1 for target in covers[seed]):
            return
        loss = sum(tau[target] == 1 for target in tau_covers[seed])
        heapq.heappush(heap, (loss, -norms[seed], seed, version[seed]))

    for seed in selected[1:]:
        enqueue(seed)
    removed = 0
    while heap and len(selected) - removed > TARGET_SEEDS:
        loss, _, seed, stamp = heapq.heappop(heap)
        if not chosen[seed] or version[seed] != stamp:
            continue
        assert all(full[target] > 1 for target in covers[seed])
        assert loss == sum(tau[target] == 1 for target in tau_covers[seed])
        chosen[seed] = 0
        removed += 1
        touched = set(covers[seed])
        for target in covers[seed]:
            full[target] -= 1
        for target in tau_covers[seed]:
            tau[target] -= 1
        neighbors = {provider for target in touched
                     for provider in inverse[target] if chosen[provider]}
        for provider in neighbors:
            enqueue(provider)
    remaining = [seed for seed in selected if chosen[seed]]
    assert min(full) > 0
    assert len(remaining) == len(selected) - removed
    return remaining, full, tau, removed


def serialize(selected, nodes, direct, canonical, node_index):
    seeds, assigned, providers = source.build_assignment(
        selected, nodes, direct, canonical, node_index)
    raw = bytearray(struct.pack("<4sIIII", b"LP21", dual.RADIX,
                                len(nodes), len(seeds), 15))
    for seed_id, map_id in assigned:
        raw.extend(struct.pack("<I", seed_id << 4 | map_id))
    for a, b in seeds:
        raw.extend(struct.pack("<hh", a, b))
    return bytes(raw), assigned, providers


def main():
    tau_raw, tau_seeds = read_tau_seeds()
    canonical, nodes, direct, _ = dual.parent.full_classes()
    covers, tau_covers, inverse, norms, node_index = source.candidate_graph(
        canonical, nodes, direct)
    by_pair = {direct[node]: index for index, node in enumerate(nodes)}
    selected = [by_pair[pair] for pair in tau_seeds]
    selected, full, tau, removed = prune(
        selected, covers, tau_covers, inverse, norms)
    raw, assigned, providers = serialize(
        selected, nodes, direct, canonical, node_index)
    assert len(assigned) == len(nodes) and all(providers)
    rho_only = sum(value == 0 for value in tau)
    assert rho_only == sum(map_id == 3 for _, map_id in assigned)
    (HERE / "cover-cycle-pruned.bin").write_bytes(raw)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "graph_source_sha256": digest(SOURCE.read_bytes()),
               "tau_cover_sha256": digest(tau_raw),
               "cover_sha256": digest(raw), "initial_seeds": len(tau_seeds),
               "removed_seeds": removed, "seed_count": len(selected),
               "class_count": len(nodes), "rho_only_classes": rho_only,
               "assigned_maps": dict(sorted(Counter(map_id for _, map_id
                                                   in assigned).items()))}
    (HERE / "prune-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
