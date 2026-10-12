#!/usr/bin/env python3
"""Independently replay every two-for-one exchange on exact residue classes."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("cycle_exchange_independent", SOURCE)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def read_seeds(path, expected):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, expected, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    return raw, list(struct.iter_unpack("<hh", raw[offset:]))


def minimum_pair(node):
    a, b = divmod(node, independent.RADIX)
    return min((independent.norm((a + i * independent.RADIX,
                                  b + j * independent.RADIX)),
                a + i * independent.RADIX, b + j * independent.RADIX)
               for i in range(-2, 2) for j in range(-2, 2))[1:]


def covers(pair, canonical, node_index):
    full = set()
    tau = set()
    for map_id in range(4):
        digit = independent.action(pair, map_id)
        if independent.norm(digit) > independent.SIZE:
            continue
        target = node_index[canonical[independent.residue(digit)]]
        full.add(target)
        if map_id < 3:
            tau.add(target)
    return full, tau


def main():
    pruned_raw, pruned_seeds = read_seeds(
        HERE / "cover-cycle-pruned.bin", 68_743)
    final_raw, final_seeds = read_seeds(
        HERE / "cover-cycle-exchanged.bin", 67_338)
    receipt = json.loads((HERE / "exchange-screen.json").read_bytes())
    assert digest(pruned_raw) == receipt["pruned_cover_sha256"]
    assert digest(final_raw) == receipt["cover_sha256"]
    path_raw = (HERE / "exchange-path.jsonl").read_bytes()
    assert digest(path_raw) == receipt["exchange_path_sha256"]
    path = [json.loads(line) for line in path_raw.splitlines()]
    assert len(path) == receipt["accepted_exchanges"] == 1_405
    canonical, nodes = independent.orbit_partition()
    node_index = {node: i for i, node in enumerate(nodes)}
    selected = []
    where = {}
    full = [0] * len(nodes)
    tau = [0] * len(nodes)
    known = {}
    for slot, pair in enumerate(pruned_seeds):
        seed = node_index[canonical[independent.residue(pair)]]
        assert seed not in where
        assert pair == minimum_pair(nodes[seed])
        where[seed] = slot
        selected.append(seed)
        known[seed] = covers(pair, canonical, node_index)
        for target in known[seed][0]:
            full[target] += 1
        for target in known[seed][1]:
            tau[target] += 1
    assert min(full) > 0
    rho_only = sum(value == 0 for value in tau)
    assert rho_only == receipt["initial_rho_only_classes"] == 4_841
    for step, row in enumerate(path, 1):
        assert row["step"] == step
        new, old_a, old_b = row["new"], row["old_a"], row["old_b"]
        assert new not in where and old_a in where and old_b in where
        assert old_a != old_b and old_a != selected[0] and old_b != selected[0]
        if new not in known:
            pair = minimum_pair(nodes[new])
            known[new] = covers(pair, canonical, node_index)
        old_full_a, old_tau_a = known[old_a]
        old_full_b, old_tau_b = known[old_b]
        new_full, new_tau = known[new]
        for target in old_full_a | old_full_b | new_full:
            after = full[target] - (target in old_full_a) - \
                (target in old_full_b) + (target in new_full)
            assert after > 0, (step, target)
        delta = 0
        for target in old_tau_a | old_tau_b | new_tau:
            before = tau[target]
            after = before - (target in old_tau_a) - \
                (target in old_tau_b) + (target in new_tau)
            assert after >= 0
            delta += (after == 0) - (before == 0)
            tau[target] = after
        assert delta == row["rho_delta"]
        rho_only += delta
        assert rho_only == row["rho_only_classes"]
        for target in old_full_a:
            full[target] -= 1
        for target in old_full_b:
            full[target] -= 1
        for target in new_full:
            full[target] += 1
        slot_a, slot_b = where.pop(old_a), where.pop(old_b)
        selected[slot_a] = new
        selected[slot_b] = None
        where[new] = slot_a
    assert min(full) > 0
    assert rho_only == receipt["final_rho_only_classes"] == 6_262
    assert len(where) == 67_338
    actual = [minimum_pair(nodes[seed]) for seed in selected
              if seed is not None]
    assert actual == final_seeds
    result = {"schema": 1, "status": "passed",
              "exchanges": len(path), "seed_count": len(actual),
              "class_count": len(nodes), "rho_only_classes": rho_only,
              "path_sha256": digest(path_raw),
              "final_cover_sha256": digest(final_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_actions_sha256": digest(SOURCE.read_bytes())}
    (HERE / "exchange-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
