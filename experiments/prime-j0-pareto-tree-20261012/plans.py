#!/usr/bin/env python3
"""Build exact work/depth Pareto plans for the 14-term gauge tree."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NATIVE = ROOT / "prime-j0-secp256k1-native"
INPUT = ROOT / "prime-j0-sector-digit-20261010/fresh-inputs.json"
PRIOR = ROOT / "prime-j0-gauge-tree-20261012/model.json"
PLAN_BYTES = 42
PLAN_COUNT = 680


@dataclass(frozen=True)
class Tree:
    counts: tuple[int, int, int]
    gauge: int
    work: int
    depth: int
    left: "Tree | None" = None
    right: "Tree | None" = None


def pareto(candidates):
    """Discard plans dominated in both charged products and product depth."""
    best_depth = 1 << 30
    out = []
    for tree in sorted(candidates, key=lambda t: (t.work, t.depth)):
        if tree.depth < best_depth:
            out.append(tree)
            best_depth = tree.depth
    return out


def exact_frontiers():
    """Exhaust every nonempty gauge-count split and every output gauge."""
    states = {}
    for size in range(1, 15):
        for a in range(size + 1):
            for b in range(size - a + 1):
                counts = (a, b, size - a - b)
                candidates = [[], [], []]
                if size == 1:
                    gauge = counts.index(1)
                    candidates[gauge].append(Tree(counts, gauge, 0, 0))
                else:
                    for left_counts in product(*(range(x + 1) for x in counts)):
                        left_size = sum(left_counts)
                        if left_size == 0 or left_size == size:
                            continue
                        right_counts = tuple(x - y for x, y in zip(counts, left_counts))
                        if left_counts > right_counts:
                            continue  # point addition is commutative
                        right_size = size - left_size
                        products = (6 if left_size == right_size == 1 else
                                    10 if min(left_size, right_size) == 1 else 14)
                        for gauge in range(3):
                            for left_gauge, right_gauge in product(range(3), repeat=2):
                                left_turn = int(left_gauge != gauge)
                                right_turn = int(right_gauge != gauge)
                                for left in states[left_counts][left_gauge]:
                                    for right in states[right_counts][right_gauge]:
                                        candidates[gauge].append(Tree(
                                            counts, gauge,
                                            left.work + right.work + products +
                                            left_turn + right_turn,
                                            max(left.depth + left_turn,
                                                right.depth + right_turn) + products,
                                            left, right))
                states[counts] = tuple(pareto(row) for row in candidates)
    assert len(states) == 679
    return states


def greedy_depth(counts):
    """Reproduce the cached mode-172 shape selector's depth cap."""
    nodes = [(0, gauge, True) for gauge, number in enumerate(counts)
             for _ in range(number)]
    while len(nodes) > 1:
        candidates = []
        for i, left in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                right = nodes[j]
                products = (6 if left[2] and right[2] else
                            10 if left[2] or right[2] else 14)
                for gauge in (left[1], right[1]):
                    ra, rb = int(left[1] != gauge), int(right[1] != gauge)
                    candidates.append((max(left[0] + ra, right[0] + rb) + products,
                                       products + ra + rb, gauge, i, j))
        depth, _, gauge, i, j = min(candidates)
        nodes = [node for k, node in enumerate(nodes) if k not in (i, j)]
        nodes.append((depth, gauge, False))
    return nodes[0][0] + int(nodes[0][1] != 0) if nodes else 0


def choose_plan(states, counts):
    if sum(counts) == 0:
        return None
    cap = greedy_depth(counts)
    options = [tree for gauge in range(3) for tree in states[counts][gauge]
               if tree.depth + int(gauge != 0) <= cap]
    assert options, counts
    return min(options, key=lambda tree: (
        tree.work + int(tree.gauge != 0),
        tree.depth + int(tree.gauge != 0), tree.gauge))


def encode_plan(tree, counts):
    """Emit postorder joins with the same remove-and-append convention as Rust."""
    if tree is None:
        return bytes(PLAN_BYTES)
    offsets = (0, counts[0], counts[0] + counts[1])
    active = list(range(sum(counts)))
    steps = []

    def visit(node, starts):
        if node.left is None:
            gauge = node.counts.index(1)
            return offsets[gauge] + starts[gauge]
        left = visit(node.left, starts)
        right_starts = tuple(starts[g] + node.left.counts[g] for g in range(3))
        right = visit(node.right, right_starts)
        i, j = sorted((active.index(left), active.index(right)))
        steps.extend((i, j, node.gauge))
        active.pop(j)
        active.pop(i)
        new_id = 14 + len(steps) // 3
        active.append(new_id)
        return new_id

    visit(tree, (0, 0, 0))
    assert len(active) == 1 and len(steps) // 3 == sum(counts) - 1
    work, depth, rotations = replay_plan(steps, counts)
    assert (work, depth) == (tree.work + int(tree.gauge != 0),
                             tree.depth + int(tree.gauge != 0))
    assert depth <= greedy_depth(counts)
    assert max(steps, default=0) < 14 and max(rotations, depth) < 256
    return bytes(steps + [0] * (39 - len(steps)) +
                 [len(steps) // 3, rotations, depth])


def replay_plan(steps, counts):
    """Independently compute the metadata from the flat runtime schedule."""
    nodes = [(0, gauge, True) for gauge, number in enumerate(counts)
             for _ in range(number)]
    work = rotations = 0
    for i, j, gauge in zip(steps[::3], steps[1::3], steps[2::3]):
        assert i < j < len(nodes) and gauge < 3
        left, right = nodes[i], nodes[j]
        ra, rb = int(left[1] != gauge), int(right[1] != gauge)
        products = (6 if left[2] and right[2] else
                    10 if left[2] or right[2] else 14)
        work += products + ra + rb
        rotations += ra + rb
        depth = max(left[0] + ra, right[0] + rb) + products
        nodes.pop(j)
        nodes.pop(i)
        nodes.append((depth, gauge, False))
    if not nodes:
        return 0, 0, 0
    final_turn = int(nodes[0][1] != 0)
    return work + final_turn, nodes[0][0] + final_turn, rotations + final_turn


def index(counts):
    a, b, c = counts
    remaining = 17 - a
    preceding = PLAN_COUNT - remaining * (remaining - 1) * (remaining - 2) // 6
    return preceding + b * (15 - a) - b * max(b - 1, 0) // 2 + c


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    sys.path.insert(0, str(NATIVE.resolve()))
    spec = importlib.util.spec_from_file_location("pareto_screen", NATIVE / "unit_orbit_windows_screen.py")
    screen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(screen)
    inputs = json.loads(INPUT.read_text())
    assert json.loads(PRIOR.read_text())["input_sha256"] == digest(INPUT)
    states = exact_frontiers()
    plans = [bytes(PLAN_BYTES)] * PLAN_COUNT
    seen = set()
    for a in range(15):
        for b in range(15 - a):
            for c in range(15 - a - b):
                counts = (a, b, c)
                slot = index(counts)
                assert slot not in seen
                seen.add(slot)
                plans[slot] = encode_plan(choose_plan(states, counts), counts)
    assert len(seen) == PLAN_COUNT and len(set(plans)) > 1
    binary = b"".join(plans)
    atlases = {width: screen.OrbitAtlas(width) for width in (9, 10)}
    totals = Counter()
    patterns = set()
    for scalar_hex in inputs["scalars_hex"]:
        scalar = int(scalar_hex, 16)
        representative = tuple(screen.hex_choices(scalar)[0][2:4])
        codes = [unit for _, unit, active in screen.recode(representative, atlases)
                 if active]
        counts = tuple(sum(code // 2 == gauge for code in codes)
                       for gauge in range(3))
        patterns.add(counts)
        plan = plans[index(counts)]
        steps = list(plan[:3 * plan[39]])
        work, depth, rotations = replay_plan(steps, counts)
        assert (rotations, depth) == (plan[40], plan[41])
        totals.update(cases=1, terms=len(codes), field_products=work,
                      rotations=rotations, product_depth=depth)
    assert totals["cases"] == 4096 and totals["terms"] == 57343
    assert (totals["field_products"], totals["rotations"], totals["product_depth"]) == (
        526168, 10082, 200505)
    result = {
        "schema": 1, "status": "exhaustive_pareto_screen",
        "objective": "minimum ordinary-path field products subject to mode-172 depth cap per gauge-count pattern",
        "all_count_patterns": PLAN_COUNT,
        "frozen_panel_patterns": len(patterns),
        "panel": dict(sorted(totals.items())),
        "parent_field_products": 528972,
        "parent_product_depth": 201965,
        "plan_bytes": len(binary),
        "input_sha256": digest(INPUT),
        "prior_model_sha256": digest(PRIOR),
        "generator_sha256": digest(Path(__file__)),
        "plans_sha256": sha256(binary).hexdigest(),
    }
    encoded = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if "--check" in sys.argv:
        assert (HERE / "plans.bin").read_bytes() == binary
        assert (HERE / "screen.json").read_bytes() == encoded
    else:
        (HERE / "plans.bin").write_bytes(binary)
        (HERE / "screen.json").write_bytes(encoded)
    print(json.dumps(result["panel"], sort_keys=True))


if __name__ == "__main__":
    main()
