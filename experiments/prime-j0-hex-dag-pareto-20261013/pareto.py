#!/usr/bin/env python3
"""Search gauge-count trees using native-formula work and coordinate DAG depth."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-workdepth-20261013"
sys.path.insert(0, str(PRIOR))
from dag_depth import Node, join, tree as replay_tree  # noqa: E402

BEAM = 12


@dataclass(frozen=True)
class State:
    node: Node
    tree: tuple


def dominates(a: State, b: State) -> bool:
    x, y = a.node, b.node
    return (x.work <= y.work and x.x <= y.x and x.y <= y.y
            and x.zz <= y.zz and x.zzz <= y.zzz)


def priority(state: State):
    n = state.node
    return (n.work, n.depth(), n.x + n.y + n.zz + n.zzz)


def insert(frontier: list[State], item: State) -> None:
    if any(dominates(existing, item) for existing in frontier):
        return
    frontier[:] = [existing for existing in frontier if not dominates(item, existing)]
    frontier.append(item)
    if len(frontier) > BEAM:
        frontier.sort(key=priority)
        del frontier[BEAM:]


@cache
def search(counts: tuple[int, int, int]) -> tuple[State, ...]:
    n = sum(counts)
    assert 1 <= n <= 16
    if n == 1:
        gauge = next(i for i, count in enumerate(counts) if count)
        return (State(Node(gauge, True), ("leaf", gauge)),)
    frontiers: dict[int, list[State]] = {g: [] for g in range(3)}
    for a in range(counts[0] + 1):
        for b in range(counts[1] + 1):
            for c in range(counts[2] + 1):
                left = a, b, c
                right = tuple(v - w for v, w in zip(counts, left))
                if not sum(left) or not sum(right) or left > right:
                    continue
                for lhs in search(left):
                    for rhs in search(right):
                        for gauge in (lhs.node.gauge, rhs.node.gauge):
                            node = join(lhs.node, rhs.node, gauge)
                            candidate = State(node,
                                ("join", gauge, lhs.tree, rhs.tree))
                            insert(frontiers[gauge], candidate)
    result = tuple(state for gauge in range(3) for state in frontiers[gauge])
    assert result
    return result


def candidates(counts: tuple[int, int, int]):
    for state in search(counts):
        rotated = state.node.rotate(0)
        yield State(rotated, state.tree)


@cache
def choose(counts: tuple[int, int, int]) -> State | None:
    frozen = replay_tree(counts, (PRIOR / "plans.bin").read_bytes())
    eligible = [s for s in candidates(counts) if s.node.work <= frozen.work]
    if not eligible:
        return None
    best = min(eligible, key=lambda s: (s.node.depth(), s.node.work))
    return best if best.node.depth() < frozen.depth() else None


def screen(counts: tuple[int, int, int]) -> dict:
    frozen = (PRIOR / "plans.bin").read_bytes()
    old = replay_tree(counts, frozen)
    selected = choose(counts)
    chosen = selected.node if selected else old
    return {"counts": counts, "frozen_work": old.work,
            "frozen_dag_depth": old.depth(),
            "candidate_work": chosen.work,
            "candidate_dag_depth": chosen.depth(),
            "frontier_size": len(search(counts)),
            "improved": chosen.work <= old.work and chosen.depth() < old.depth()}


if __name__ == "__main__":
    counts = tuple(int(v) for v in sys.argv[1:])
    assert len(counts) == 3
    print(json.dumps(screen(counts), sort_keys=True))
