#!/usr/bin/env python3
"""Replace orbit-cover seeds without changing table size or losing coverage."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-carry-aware-v2-20261011/screen.py"
SPEC = importlib.util.spec_from_file_location("orbit_swap_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
dual = parent.dual
MAX_PASSES = 12


def digest(raw):
    return sha256(raw).hexdigest()


def candidate_graph(canonical, nodes, direct):
    node_index = {node: index for index, node in enumerate(nodes)}
    covers = []
    tau_covers = []
    inverse = [[] for _ in nodes]
    norms = []
    for candidate, node in enumerate(nodes):
        pair = direct[node]
        norms.append(dual.screen.norm(pair))
        classes = set()
        tau_classes = set()
        for map_id in range(4):
            digit = dual.mapped(pair, map_id)
            if dual.screen.norm(digit) > dual.NORM_LIMIT:
                continue
            target = node_index[canonical[dual.screen.index(digit, dual.RADIX)]]
            classes.add(target)
            if map_id < 3:
                tau_classes.add(target)
        cover = tuple(sorted(classes))
        covers.append(cover)
        tau_covers.append(tuple(sorted(tau_classes)))
        for target in cover:
            inverse[target].append(candidate)
    return covers, tau_covers, inverse, norms, node_index


def optimize(selected, covers, tau_covers, inverse, norms):
    size = len(inverse)
    chosen = set(selected)
    assert len(chosen) == len(selected)
    cover_count = [0] * size
    tau_count = [0] * size
    for candidate in selected:
        for target in covers[candidate]:
            cover_count[target] += 1
        for target in tau_covers[candidate]:
            tau_count[target] += 1
    assert min(cover_count) > 0
    initial_rho_only = sum(count == 0 for count in tau_count)
    history = []
    for pass_index in range(MAX_PASSES):
        swaps = 0
        improvement = 0
        for slot in range(1, len(selected)):
            old = selected[slot]
            unique = [target for target in covers[old]
                      if cover_count[target] == 1]
            if not unique:
                continue
            best = None
            for new in inverse[unique[0]]:
                if new in chosen or not all(target in covers[new]
                                            for target in unique[1:]):
                    continue
                new_tau = tau_covers[new]
                gain = sum(tau_count[target] == 0 for target in new_tau)
                loss = sum(tau_count[target] == 1 and target not in new_tau
                           for target in tau_covers[old])
                score = gain - loss
                choice = (score, -norms[new], -new)
                if score > 0 and (best is None or choice > best[0]):
                    best = (choice, new)
            if best is None:
                continue
            new = best[1]
            for target in covers[old]:
                cover_count[target] -= 1
            for target in tau_covers[old]:
                tau_count[target] -= 1
            for target in covers[new]:
                cover_count[target] += 1
            for target in tau_covers[new]:
                tau_count[target] += 1
            assert all(cover_count[target] > 0 for target in covers[old])
            chosen.remove(old)
            chosen.add(new)
            selected[slot] = new
            swaps += 1
            improvement += best[0][0]
        rho_only = sum(count == 0 for count in tau_count)
        history.append({"pass": pass_index + 1, "swaps": swaps,
                        "rho_only_classes": rho_only})
        assert rho_only == initial_rho_only - sum(
            row["rho_only_improvement"] for row in history[:-1]) - improvement
        history[-1]["rho_only_improvement"] = improvement
        print(json.dumps(history[-1], sort_keys=True), flush=True)
        if swaps == 0:
            break
    assert min(cover_count) > 0
    return selected, history, initial_rho_only, tau_count


def build_assignment(selected, nodes, direct, canonical, node_index):
    providers = [[] for _ in nodes]
    seeds = [direct[nodes[candidate]] for candidate in selected]
    for seed_id, pair in enumerate(seeds):
        for map_id in range(4):
            digit = dual.mapped(pair, map_id)
            if dual.screen.norm(digit) > dual.NORM_LIMIT:
                continue
            target = node_index[canonical[dual.screen.index(digit, dual.RADIX)]]
            providers[target].append((seed_id, map_id, digit))
    assert all(providers)
    assigned = []
    for row in providers:
        seed_id, map_id, _ = min(
            row, key=lambda item: (item[1] == 3,
                                   dual.screen.norm(item[2]),
                                   item[1], item[0]))
        assigned.append((seed_id, map_id))
    return seeds, assigned, providers


def main():
    old_raw, _, old_seeds = parent.load_cover()
    canonical, nodes, direct, _ = dual.parent.full_classes()
    covers, tau_covers, inverse, norms, node_index = candidate_graph(
        canonical, nodes, direct)
    by_pair = {direct[node]: index for index, node in enumerate(nodes)}
    assert all(pair in by_pair for pair in old_seeds)
    selected = [by_pair[pair] for pair in old_seeds]
    selected, history, initial, tau_count = optimize(
        selected, covers, tau_covers, inverse, norms)
    seeds, assigned, providers = build_assignment(
        selected, nodes, direct, canonical, node_index)
    final = sum(count == 0 for count in tau_count)
    assert final == sum(not any(map_id < 3 for _, map_id, _ in row)
                        for row in providers)
    assert final == sum(map_id == 3 for _, map_id in assigned)
    binary = bytearray(struct.pack("<4sIIII", b"LP21", 1024, len(nodes),
                                   len(seeds), 15))
    for seed_id, map_id in assigned:
        binary.extend(struct.pack("<I", seed_id << 4 | map_id))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    assert len(binary) == len(old_raw)
    output = HERE / "cover-swapped-rho0.bin"
    output.write_bytes(binary)
    panel = dual.replay_panel(assigned, seeds, nodes, canonical)
    receipt = {"schema": 1, "status": "screened",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "parent_sha256": digest(PARENT.read_bytes()),
               "cover_source_sha256": digest(old_raw),
               "cover_swapped_sha256": digest(binary),
               "seed_count": len(seeds), "class_count": len(nodes),
               "initial_rho_only_classes": initial,
               "final_rho_only_classes": final,
               "passes": history,
               "assigned_maps": dict(sorted(Counter(map_id for _, map_id
                                                    in assigned).items())),
               "retained_bytes_before_offer_index": 54_339_936,
               "design_panel": panel}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"seed_count": len(seeds), "rho_only_classes": final,
                      "design_active_rho": panel["active_branch_cases"].get("1", 0),
                      "design_terminal_failures": panel["terminal_bound_failures"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
