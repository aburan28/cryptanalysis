#!/usr/bin/env python3
"""Exchange two redundant cover seeds for one under the fixed table budget."""

from collections import Counter
from hashlib import sha256
import importlib.util
import itertools
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "prune.py"
SPEC = importlib.util.spec_from_file_location("cycle_exchange_parent", SOURCE)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
graph = parent.source
dual = parent.dual


def digest(raw):
    return sha256(raw).hexdigest()


def read_pruned():
    raw = (HERE / "cover-cycle-pruned.bin").read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 68_743, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    return raw, list(struct.iter_unpack("<hh", raw[offset:]))


def valid_exchange(new, old_a, old_b, covers, full):
    added = set(covers[new])
    for target in set(covers[old_a]) | set(covers[old_b]):
        count = full[target] - (target in covers[old_a]) - \
            (target in covers[old_b]) + (target in added)
        if count <= 0:
            return False
    return True


def rho_delta(new, old_a, old_b, tau_covers, tau):
    added = set(tau_covers[new])
    before = after = 0
    for target in set(tau_covers[old_a]) | set(tau_covers[old_b]) | added:
        before += tau[target] == 0
        count = tau[target] - (target in tau_covers[old_a]) - \
            (target in tau_covers[old_b]) + (target in added)
        assert count >= 0
        after += count == 0
    return after - before


def scan(selected, covers, tau_covers, full, tau, norms):
    chosen = set(selected)
    unique = {seed: frozenset(target for target in covers[seed]
                              if full[target] == 1) for seed in selected}
    owner = {target: seed for seed, targets in unique.items()
             for target in targets}
    choices = []
    for new, targets in enumerate(covers):
        if new in chosen:
            continue
        offered = set(targets)
        removable = sorted({owner[target] for target in targets
                            if target in owner and owner[target] != selected[0]
                            and unique[owner[target]] <= offered})
        for old_a, old_b in itertools.combinations(removable, 2):
            if not valid_exchange(new, old_a, old_b, covers, full):
                continue
            delta = rho_delta(new, old_a, old_b, tau_covers, tau)
            choices.append((delta, norms[new], new, old_a, old_b))
    choices.sort()
    return choices


def apply(selected, covers, tau_covers, full, tau, choices):
    where = {seed: slot for slot, seed in enumerate(selected)}
    chosen = set(selected)
    path = []
    for _, _, new, old_a, old_b in choices:
        if len(chosen) <= parent.TARGET_SEEDS:
            break
        if new in chosen or old_a not in chosen or old_b not in chosen:
            continue
        if not valid_exchange(new, old_a, old_b, covers, full):
            continue
        delta = rho_delta(new, old_a, old_b, tau_covers, tau)
        before = sum(value == 0 for value in tau)
        for old in (old_a, old_b):
            for target in covers[old]:
                full[target] -= 1
            for target in tau_covers[old]:
                tau[target] -= 1
            chosen.remove(old)
        for target in covers[new]:
            full[target] += 1
        for target in tau_covers[new]:
            tau[target] += 1
        chosen.add(new)
        assert min(full[target] for old in (old_a, old_b)
                   for target in covers[old]) > 0
        assert sum(value == 0 for value in tau) == before + delta
        slot_a, slot_b = where.pop(old_a), where.pop(old_b)
        selected[slot_a] = new
        selected[slot_b] = None
        where[new] = slot_a
        path.append({"step": len(path) + 1, "new": new,
                     "old_a": old_a, "old_b": old_b,
                     "rho_delta": delta,
                     "rho_only_classes": before + delta})
    selected = [seed for seed in selected if seed is not None]
    assert len(selected) == len(chosen)
    return selected, path


def main():
    raw, seed_pairs = read_pruned()
    canonical, nodes, direct, _ = dual.parent.full_classes()
    covers, tau_covers, inverse, norms, node_index = graph.candidate_graph(
        canonical, nodes, direct)
    by_pair = {direct[node]: index for index, node in enumerate(nodes)}
    selected = [by_pair[pair] for pair in seed_pairs]
    full, tau = parent.counts(selected, covers, tau_covers, len(nodes))
    initial_rho = sum(value == 0 for value in tau)
    choices = scan(selected, covers, tau_covers, full, tau, norms)
    selected, path = apply(selected, covers, tau_covers, full, tau, choices)
    assert min(full) > 0
    final_rho = sum(value == 0 for value in tau)
    assert final_rho == initial_rho + sum(row["rho_delta"] for row in path)
    binary, assigned, providers = parent.serialize(
        selected, nodes, direct, canonical, node_index)
    assert all(providers)
    assert final_rho == sum(map_id == 3 for _, map_id in assigned)
    (HERE / "cover-cycle-exchanged.bin").write_bytes(binary)
    path_raw = ("\n".join(json.dumps(row, sort_keys=True,
                                       separators=(",", ":")) for row in path) + "\n").encode()
    (HERE / "exchange-path.jsonl").write_bytes(path_raw)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "pruned_cover_sha256": digest(raw),
               "cover_sha256": digest(binary),
               "exchange_path_sha256": digest(path_raw),
               "initial_seeds": len(seed_pairs),
               "final_seeds": len(selected),
               "class_count": len(nodes),
               "scan_feasible_choices": len(choices),
               "accepted_exchanges": len(path),
               "initial_rho_only_classes": initial_rho,
               "final_rho_only_classes": final_rho,
               "delta_counts": dict(sorted(Counter(row["rho_delta"]
                                                   for row in path).items())),
               "assigned_maps": dict(sorted(Counter(map_id for _, map_id
                                                   in assigned).items()))}
    (HERE / "exchange-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
