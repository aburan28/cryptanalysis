#!/usr/bin/env python3
"""Count kernel-call dependencies inside the actual XYZZ addition formulas."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys

from optimize import finish, greedy_cost, load_module

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-tree-20261013"


@dataclass(frozen=True)
class Node:
    gauge: int
    affine: bool
    x: int = 0
    y: int = 0
    zz: int = 0
    zzz: int = 0
    work: int = 0

    def rotate(self, gauge: int) -> Node:
        if self.gauge == gauge:
            return self
        return Node(gauge, self.affine, self.x + 1, self.y,
                    self.zz, self.zzz, self.work + 1)

    def depth(self) -> int:
        return max(self.x, self.y, self.zz, self.zzz)


def product(a: int, b: int) -> int:
    return max(a, b) + 1


def square(a: int) -> int:
    return a + 1


def join(left: Node, right: Node, gauge: int) -> Node:
    a, b = left.rotate(gauge), right.rotate(gauge)
    if a.affine and b.affine:
        p = max(a.x, b.x)
        r = max(a.y, b.y)
        pp = square(p)
        ppp = product(p, pp)
        axpp = product(a.x, pp)
        x = max(square(r), ppp, axpp)
        y = max(product(r, max(axpp, x)), product(a.y, ppp))
        return Node(gauge, False, x, y, pp, ppp, a.work + b.work + 6)
    if a.affine:
        a, b = b, a
    if b.affine:
        u2 = product(b.x, a.zz)
        s2 = product(b.y, a.zzz)
        p = max(u2, a.x)
        r = max(s2, a.y)
        pp = square(p)
        ppp = product(p, pp)
        qx = product(a.x, pp)
        x = max(square(r), ppp, qx)
        y = max(product(r, max(qx, x)), product(a.y, ppp))
        zz = product(a.zz, pp)
        zzz = product(a.zzz, ppp)
        return Node(gauge, False, x, y, zz, zzz, a.work + b.work + 10)
    u1 = product(a.x, b.zz)
    u2 = product(b.x, a.zz)
    s1 = product(a.y, b.zzz)
    s2 = product(b.y, a.zzz)
    h, r = max(u1, u2), max(s1, s2)
    hh = square(h)
    hhh = product(h, hh)
    v = product(u1, hh)
    x = max(square(r), hhh, v)
    y = max(product(r, max(v, x)), product(s1, hhh))
    zz = product(product(a.zz, b.zz), hh)
    zzz = product(product(a.zzz, b.zzz), hhh)
    return Node(gauge, False, x, y, zz, zzz, a.work + b.work + 14)


def plan_index(counts):
    a, b, c = counts
    n = a + b + c
    return n * (n + 1) * (n + 2) // 6 + a * (n + 1) - a * (a - 1) // 2 + b


def tree(counts, data: bytes) -> Node:
    n = sum(counts)
    record = data[48 * plan_index(counts):48 * (plan_index(counts) + 1)]
    assert len(record) == 48
    nodes = [Node(g, True) for g, count in enumerate(counts)
             for _ in range(count)]
    for k in range(0, 3 * record[45], 3):
        i, j, gauge = record[k:k + 3]
        assert i < j < len(nodes)
        joined = join(nodes[i], nodes[j], gauge)
        nodes.pop(j)
        nodes.pop(i)
        nodes.append(joined)
    assert len(nodes) == (1 if n else 0)
    return nodes[0].rotate(0) if nodes else Node(0, False)


def serial(counts) -> Node:
    result = None
    gauge = None
    for power in (1, 2, 0):
        if counts[power] == 0:
            continue
        if result is not None:
            result = result.rotate(power)
        gauge = power
        for _ in range(counts[power]):
            leaf = Node(power, True)
            if result is None:
                result = Node(power, False)  # identity.add_mixed returns from_affine
            else:
                result = join(result, leaf, power)
    if result is None:
        return Node(0, False)
    assert gauge is not None
    return result.rotate(0)


def panel(path: Path, greedy: bytes, lowwork: bytes) -> dict:
    screen = load_module("dag_screen", PRIOR / "screen.py")
    screen.sys.path.insert(0, str(screen.NATIVE.resolve()))
    orbit = screen.load("dag_orbit", screen.NATIVE / "unit_orbit_windows_screen.py")
    old = screen.load("dag_representative", screen.NATIVE / "radix943_screen.py")
    codes, digits = screen.hex_screen.atlas(orbit)
    cases = json.loads(path.read_text())["cases"]
    totals = {key: 0 for key in ("serial_work", "serial_dag_depth",
                               "greedy_work", "greedy_dag_depth",
                               "lowwork_work", "lowwork_dag_depth")}
    for case in cases:
        gauges = screen.selected_gauges(int(case["scalar_hex"], 16), old, orbit, codes, digits)
        counts = tuple(gauges.count(g) for g in range(3))
        a, b, c = serial(counts), tree(counts, greedy), tree(counts, lowwork)
        assert b.work == greedy_cost(counts)[0]
        assert c.work == finish(counts).work
        assert a.work == screen.serial_cost(gauges)[0]
        for name, node in (("serial", a), ("greedy", b), ("lowwork", c)):
            totals[f"{name}_work"] += node.work
            totals[f"{name}_dag_depth"] += node.depth()
    return {"cases": len(cases), "fixture_sha256": sha256(path.read_bytes()).hexdigest(),
            **totals}


def run() -> dict:
    greedy = (PRIOR / "plans.bin").read_bytes()
    lowwork = (HERE / "plans.bin").read_bytes()
    patterns = 0
    for n in range(17):
        for a in range(n + 1):
            for b in range(n - a + 1):
                counts = a, b, n - a - b
                assert tree(counts, greedy).work == greedy_cost(counts)[0]
                assert tree(counts, lowwork).work == finish(counts).work
                patterns += 1
    return {"schema": 1, "status": "formula_dag_model_replayed",
            "patterns": patterns,
            "fresh_panel": panel(HERE / "holdout.json", greedy, lowwork),
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "greedy_plan_sha256": sha256(greedy).hexdigest(),
            "lowwork_plan_sha256": sha256(lowwork).hexdigest()}


if __name__ == "__main__":
    result = run()
    output = HERE / "dag-depth.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        assert not output.exists()
        output.write_text(data)
    else:
        assert output.read_text() == data
    print(json.dumps(result["fresh_panel"], sort_keys=True))
