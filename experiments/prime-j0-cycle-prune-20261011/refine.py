#!/usr/bin/env python3
"""Improve tau coverage by one-for-one swaps at the fixed seed count."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "exchange.py"
SPEC = importlib.util.spec_from_file_location("cycle_refine_exchange", SOURCE)
exchange = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exchange)
parent = exchange.parent
graph = exchange.graph
dual = exchange.dual


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    old_raw = (HERE / "cover-cycle-exchanged.bin").read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", old_raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    assert len(old_raw) == offset + 4 * count
    seed_pairs = list(struct.iter_unpack("<hh", old_raw[offset:]))
    canonical, nodes, direct, _ = dual.parent.full_classes()
    covers, tau_covers, inverse, norms, node_index = graph.candidate_graph(
        canonical, nodes, direct)
    by_pair = {direct[node]: index for index, node in enumerate(nodes)}
    selected = [by_pair[pair] for pair in seed_pairs]
    selected, history, initial, tau_count = graph.optimize(
        selected, covers, tau_covers, inverse, norms)
    final = sum(value == 0 for value in tau_count)
    binary, assigned, providers = parent.serialize(
        selected, nodes, direct, canonical, node_index)
    assert all(providers)
    assert final == sum(map_id == 3 for _, map_id in assigned)
    (HERE / "cover-cycle-refined.bin").write_bytes(binary)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "exchange_cover_sha256": digest(old_raw),
               "cover_sha256": digest(binary),
               "seed_count": len(selected), "class_count": len(nodes),
               "initial_rho_only_classes": initial,
               "final_rho_only_classes": final,
               "passes": history,
               "assigned_maps": dict(sorted(Counter(map_id for _, map_id
                                                   in assigned).items()))}
    (HERE / "refine-screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"seed_count": len(selected),
                      "rho_only_classes": final,
                      "cover_sha256": digest(binary)}, sort_keys=True))


if __name__ == "__main__":
    main()
