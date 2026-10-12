#!/usr/bin/env python3
"""Spend full-cover-redundant slots on uncovered tau classes."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "refine.py"
SPEC = importlib.util.spec_from_file_location("redundant_refine", SOURCE)
refine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refine)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    old_raw = (HERE / "cover-cycle-refined.bin").read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", old_raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    pairs = list(struct.iter_unpack("<hh", old_raw[offset:]))
    canonical, nodes, direct, _ = refine.dual.parent.full_classes()
    covers, tau_covers, _, norms, node_index = refine.graph.candidate_graph(
        canonical, nodes, direct)
    by_pair = {direct[node]: index for index, node in enumerate(nodes)}
    selected = [by_pair[pair] for pair in pairs]
    chosen = set(selected)
    full, tau = refine.parent.counts(selected, covers, tau_covers, len(nodes))
    initial = sum(value == 0 for value in tau)
    path = []
    while True:
        redundant = [(slot, seed) for slot, seed in enumerate(selected)
                     if slot > 0 and all(full[target] > 1
                                         for target in covers[seed])]
        offers = [(candidate, sum(tau[target] == 0
                                  for target in tau_covers[candidate]))
                  for candidate in range(len(covers)) if candidate not in chosen
                  and any(tau[target] == 0
                          for target in tau_covers[candidate])]
        best = None
        for slot, old in redundant:
            singleton_tau = {target for target in tau_covers[old]
                             if tau[target] == 1}
            for new, gain in offers:
                score = gain - len(singleton_tau) + sum(
                    target in tau_covers[new] for target in singleton_tau)
                if score <= 0:
                    continue
                key = (-score, norms[new], new, slot)
                if best is None or key < best[0]:
                    best = (key, slot, old, new, score)
        if best is None:
            break
        assert len(path) < classes
        _, slot, old, new, score = best
        before = sum(value == 0 for value in tau)
        for target in covers[old]:
            full[target] -= 1
        for target in tau_covers[old]:
            tau[target] -= 1
        for target in covers[new]:
            full[target] += 1
        for target in tau_covers[new]:
            tau[target] += 1
        assert all(full[target] > 0 for target in covers[old])
        assert sum(value == 0 for value in tau) == before - score
        selected[slot] = new
        chosen.remove(old)
        chosen.add(new)
        path.append({"step": len(path) + 1, "slot": slot,
                     "old": old, "new": new, "rho_gain": score,
                     "old_pair": direct[nodes[old]],
                     "new_pair": direct[nodes[new]],
                     "rho_only_classes": before - score})

    binary, assigned, providers = refine.parent.serialize(
        selected, nodes, direct, canonical, node_index)
    final = sum(value == 0 for value in tau)
    assert all(providers) and final == sum(map_id == 3 for _, map_id in assigned)
    assert len(selected) == count and len(chosen) == count
    path_raw = ("\n".join(json.dumps(row, sort_keys=True,
                                    separators=(",", ":")) for row in path)
                + "\n").encode()
    (HERE / "cover-cycle-redundant.bin").write_bytes(binary)
    (HERE / "redundant-path.jsonl").write_bytes(path_raw)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "refined_cover_sha256": digest(old_raw),
               "cover_sha256": digest(binary),
               "path_sha256": digest(path_raw),
               "seed_count": count, "class_count": classes,
               "initial_rho_only_classes": initial,
               "final_rho_only_classes": final,
               "swaps": len(path),
               "assigned_maps": dict(sorted(Counter(map_id for _, map_id
                                                    in assigned).items()))}
    (HERE / "redundant-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
