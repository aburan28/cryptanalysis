#!/usr/bin/env python3
"""Exchange two cover seeds for one, then spend the freed slot on tau."""

from collections import Counter
from hashlib import sha256
import importlib.util
import itertools
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-cycle-prune-20261011/refine.py"
SPEC = importlib.util.spec_from_file_location("compression_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
exchange = parent.exchange
BASE = HERE.parent / "prime-j0-cycle-prune-20261011/cover-cycle-redundant.bin"
LOWER_BOUND = 6_079


def digest(raw):
    return sha256(raw).hexdigest()


def counts_after(a, b, p, tau_covers, tau):
    affected = set(tau_covers[a]) | set(tau_covers[b]) | set(tau_covers[p])
    after = {target: tau[target] - (target in tau_covers[a])
             - (target in tau_covers[b]) + (target in tau_covers[p])
             for target in affected}
    assert min(after.values()) >= 0
    delta = sum(after[target] == 0 for target in affected) - sum(
        tau[target] == 0 for target in affected)
    newly_zero = {target for target in affected
                  if tau[target] > 0 and after[target] == 0}
    newly_covered = {target for target in affected
                     if tau[target] == 0 and after[target] > 0}
    return delta, newly_zero, newly_covered


def scan(selected, covers, tau_covers, inverse_tau, norms, full, tau):
    chosen = set(selected)
    unique = {seed: frozenset(target for target in covers[seed]
                              if full[target] == 1) for seed in selected}
    owner = {target: seed for seed, targets in unique.items()
             for target in targets}
    gain0 = [sum(tau[target] == 0 for target in targets)
             for targets in tau_covers]
    by_gain = {level: [seed for seed, gain in enumerate(gain0)
                       if gain >= level and seed not in chosen]
               for level in (1, 2, 3)}
    lowest_unused = min((seed for seed in range(len(covers))
                         if seed not in chosen), key=lambda seed: (norms[seed], seed))
    choices = []
    compressions = 0
    for p, offered_tuple in enumerate(covers):
        if p in chosen:
            continue
        offered = set(offered_tuple)
        removable = sorted({owner[target] for target in offered_tuple
                            if target in owner and owner[target] != selected[0]
                            and unique[owner[target]] <= offered})
        for a, b in itertools.combinations(removable, 2):
            if not exchange.valid_exchange(p, a, b, covers, full):
                continue
            compressions += 1
            delta, newly_zero, newly_covered = counts_after(
                a, b, p, tau_covers, tau)
            if delta >= 3:
                continue
            candidates = set(by_gain.get(max(delta + 1, 1), ()))
            for target in newly_zero:
                candidates.update(inverse_tau[target])
            if delta < 0:
                candidates.add(lowest_unused)
            for q in candidates:
                if q == p or q in chosen:
                    continue
                gain = gain0[q] + sum(target in tau_covers[q]
                                      for target in newly_zero) - sum(
                    target in tau_covers[q] for target in newly_covered)
                improvement = gain - delta
                if improvement > 0:
                    choices.append((-improvement, norms[p] + norms[q],
                                    p, q, a, b))
    choices.sort()
    return choices, compressions


def apply(selected, choices, covers, tau_covers, full, tau, lower_bound,
          nodes, direct):
    chosen = set(selected)
    where = {seed: slot for slot, seed in enumerate(selected)}
    path = []
    current_rho_only = sum(value == 0 for value in tau)
    for _, _, p, q, a, b in choices:
        if current_rho_only == lower_bound:
            break
        if a not in chosen or b not in chosen or p in chosen or q in chosen:
            continue
        if not exchange.valid_exchange(p, a, b, covers, full):
            continue
        affected = set(tau_covers[a]) | set(tau_covers[b]) | \
            set(tau_covers[p]) | set(tau_covers[q])
        before = sum(tau[target] == 0 for target in affected)
        after = sum(tau[target] - (target in tau_covers[a])
                    - (target in tau_covers[b]) + (target in tau_covers[p])
                    + (target in tau_covers[q]) == 0 for target in affected)
        improvement = before - after
        if improvement <= 0:
            continue
        total_before = current_rho_only
        assert total_before - improvement >= lower_bound
        for old in (a, b):
            for target in covers[old]:
                full[target] -= 1
            for target in tau_covers[old]:
                tau[target] -= 1
        for new in (p, q):
            for target in covers[new]:
                full[target] += 1
            for target in tau_covers[new]:
                tau[target] += 1
        assert all(full[target] > 0 for old in (a, b)
                   for target in covers[old])
        current_rho_only -= improvement
        slot_a, slot_b = where.pop(a), where.pop(b)
        selected[slot_a], selected[slot_b] = p, q
        where[p], where[q] = slot_a, slot_b
        chosen.remove(a)
        chosen.remove(b)
        chosen.add(p)
        chosen.add(q)
        path.append({"step": len(path) + 1, "old_a": a, "old_b": b,
                     "new_cover": p, "new_tau": q,
                     "slot_a": slot_a, "slot_b": slot_b,
                     "old_a_pair": direct[nodes[a]],
                     "old_b_pair": direct[nodes[b]],
                     "new_cover_pair": direct[nodes[p]],
                     "new_tau_pair": direct[nodes[q]],
                     "rho_improvement": improvement,
                     "rho_only_classes": total_before - improvement})
    assert len(chosen) == len(selected) and min(full) > 0
    assert sum(value == 0 for value in tau) == current_rho_only
    return selected, path


def main():
    raw = BASE.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    pairs = list(struct.iter_unpack("<hh", raw[offset:]))
    canonical, nodes, direct, _ = parent.dual.parent.full_classes()
    covers, tau_covers, _, norms, node_index = \
        parent.graph.candidate_graph(canonical, nodes, direct)
    by_pair = {direct[node]: index for index, node in enumerate(nodes)}
    selected = [by_pair[pair] for pair in pairs]
    full, tau = parent.parent.counts(selected, covers, tau_covers, len(nodes))
    initial = sum(value == 0 for value in tau)
    inverse_tau = [[] for _ in nodes]
    for seed, targets in enumerate(tau_covers):
        for target in targets:
            inverse_tau[target].append(seed)
    history = []
    path = []
    for pass_index in range(20):
        if sum(value == 0 for value in tau) == LOWER_BOUND:
            break
        choices, compressions = scan(
            selected, covers, tau_covers, inverse_tau, norms, full, tau)
        selected, accepted = apply(
            selected, choices, covers, tau_covers, full, tau, LOWER_BOUND,
            nodes, direct)
        for row in accepted:
            row["step"] = len(path) + 1
            path.append(row)
        row = {"pass": pass_index + 1,
               "feasible_compressions": compressions,
               "improving_choices": len(choices),
               "accepted": len(accepted),
               "rho_only_classes": sum(value == 0 for value in tau)}
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if not accepted:
            break
    binary, assigned, providers = parent.parent.serialize(
        selected, nodes, direct, canonical, node_index)
    final = sum(value == 0 for value in tau)
    assert all(providers) and final == sum(map_id == 3 for _, map_id in assigned)
    assert len(selected) == count and len(set(selected)) == count
    path_raw = ("\n".join(json.dumps(row, sort_keys=True,
                                    separators=(",", ":")) for row in path)
                + "\n").encode()
    (HERE / "cover-cycle-compressed.bin").write_bytes(binary)
    (HERE / "compression-path.jsonl").write_bytes(path_raw)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "base_cover_sha256": digest(raw),
               "cover_sha256": digest(binary),
               "path_sha256": digest(path_raw),
               "seed_count": count, "class_count": classes,
               "initial_rho_only_classes": initial,
               "final_rho_only_classes": final,
               "lower_bound": LOWER_BOUND,
               "accepted_exchanges": len(path), "passes": history,
               "assigned_maps": dict(sorted(Counter(map_id for _, map_id
                                                    in assigned).items()))}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("accepted_exchanges", "final_rho_only_classes",
                       "cover_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
