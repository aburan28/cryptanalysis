#!/usr/bin/env python3
"""Find low-product gauge trees by dynamic programming on the leaf counts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PRIOR = EXP / "prime-j0-hex-tree-20261013"


@dataclass(frozen=True)
class Plan:
    gauge: int
    work: int
    depth: int
    rotations: int
    tree: tuple


def size(counts: tuple[int, int, int]) -> int:
    return sum(counts)


@cache
def best(counts: tuple[int, int, int]) -> tuple[Plan, ...]:
    n = size(counts)
    assert 1 <= n <= 16
    if n == 1:
        gauge = next(i for i, count in enumerate(counts) if count)
        return (Plan(gauge, 0, 0, 0, ("leaf", gauge)),)
    choices: dict[int, Plan] = {}
    for a in range(counts[0] + 1):
        for b in range(counts[1] + 1):
            for c in range(counts[2] + 1):
                left_counts = (a, b, c)
                right_counts = tuple(x - y for x, y in zip(counts, left_counts))
                nl, nr = size(left_counts), size(right_counts)
                if not nl or not nr or left_counts > right_counts:
                    continue
                products = 6 if nl == nr == 1 else 10 if nl == 1 or nr == 1 else 14
                for left in best(left_counts):
                    for right in best(right_counts):
                        for gauge in (left.gauge, right.gauge):
                            ra = int(left.gauge != gauge)
                            rb = int(right.gauge != gauge)
                            candidate = Plan(
                                gauge, left.work + right.work + products + ra + rb,
                                max(left.depth + ra, right.depth + rb) + products,
                                left.rotations + right.rotations + ra + rb,
                                ("join", gauge, left.tree, right.tree),
                            )
                            previous = choices.get(gauge)
                            if previous is None or (
                                candidate.work, candidate.depth, candidate.rotations
                            ) < (previous.work, previous.depth, previous.rotations):
                                choices[gauge] = candidate
    assert choices
    return tuple(choices[gauge] for gauge in sorted(choices))


def finish(counts: tuple[int, int, int]) -> Plan:
    if size(counts) == 0:
        return Plan(0, 0, 0, 0, ())
    candidates = []
    for plan in best(counts):
        last = int(plan.gauge != 0)
        candidates.append(Plan(0, plan.work + last, plan.depth + last,
                               plan.rotations + last, plan.tree))
    return min(candidates, key=lambda p: (p.work, p.depth, p.rotations))


def greedy_cost(counts: tuple[int, int, int]) -> tuple[int, int, int]:
    n = size(counts)
    before_size = n * (n + 1) * (n + 2) // 6
    a, b, _ = counts
    before_a = a * (n + 1) - a * (a - 1) // 2
    data = (PRIOR / "plans.bin").read_bytes()
    record = data[(before_size + before_a + b) * 48:][:48]
    nodes = [(g, 0, 0, True) for g, count in enumerate(counts) for _ in range(count)]
    rotations = 0
    for i, j, gauge in (record[k:k + 3] for k in range(0, 3 * record[45], 3)):
        left, right = nodes[i], nodes[j]
        ra, rb = int(left[0] != gauge), int(right[0] != gauge)
        products = 6 if left[3] and right[3] else 10 if left[3] or right[3] else 14
        joined = (gauge, max(left[1] + ra, right[1] + rb) + products,
                  left[2] + right[2] + products + ra + rb, False)
        rotations += ra + rb
        nodes.pop(j)
        nodes.pop(i)
        nodes.append(joined)
    if not nodes:
        return 0, 0, 0
    last = int(nodes[0][0] != 0)
    result = nodes[0][2] + last, nodes[0][1] + last, rotations + last
    assert result[1:] == (record[47], record[46])
    return result


def load_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def panel(path: Path) -> dict:
    old_screen = load_module("workdepth_old_screen", PRIOR / "screen.py")
    old_screen.sys.path.insert(0, str(old_screen.NATIVE.resolve()))
    orbit = old_screen.load("workdepth_orbit", old_screen.NATIVE / "unit_orbit_windows_screen.py")
    old = old_screen.load("workdepth_representative", old_screen.NATIVE / "radix943_screen.py")
    codes, digits = old_screen.hex_screen.atlas(orbit)
    source = json.loads(path.read_text())
    scalars = (source["scalars_hex"] if "scalars_hex" in source else
               [case["scalar_hex"] for case in source["cases"]])
    totals = {key: 0 for key in ("cases", "greedy_work", "greedy_depth",
                               "greedy_rotations", "optimized_work", "optimized_depth",
                               "optimized_rotations", "lower_work", "lower_depth")}
    frequencies = {}
    for scalar_hex in scalars:
        gauges = old_screen.selected_gauges(int(scalar_hex, 16), old, orbit, codes, digits)
        counts = tuple(gauges.count(g) for g in range(3))
        frequencies[counts] = frequencies.get(counts, 0) + 1
        greedy = greedy_cost(counts)
        optimized = finish(counts)
        assert optimized.work <= greedy[0]
        totals["cases"] += 1
        totals["greedy_work"] += greedy[0]
        totals["greedy_depth"] += greedy[1]
        totals["greedy_rotations"] += greedy[2]
        totals["optimized_work"] += optimized.work
        totals["optimized_depth"] += optimized.depth
        totals["optimized_rotations"] += optimized.rotations
        totals["lower_work"] += optimized.work < greedy[0]
        totals["lower_depth"] += optimized.depth < greedy[1]
    return {**totals, "distinct_gauge_counts": len(frequencies),
            "fixture_sha256": sha256(path.read_bytes()).hexdigest()}


def run() -> dict:
    all_counts = [(a, b, n - a - b) for n in range(17)
                  for a in range(n + 1) for b in range(n - a + 1)]
    improvements = []
    for counts in all_counts:
        optimized = finish(counts)
        greedy = greedy_cost(counts)
        assert optimized.work <= greedy[0]
        if optimized.work < greedy[0]:
            improvements.append({"counts": list(counts), "greedy": list(greedy),
                                 "optimized": [optimized.work, optimized.depth,
                                               optimized.rotations]})
    design = panel(EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json")
    holdout = panel(PRIOR / "holdout.json")
    return {"schema": 1, "status": "operation_model_screen",
            "all_count_patterns": len(all_counts),
            "improved_count_patterns": len(improvements),
            "top_improvements": sorted(improvements,
                                       key=lambda x: (x["greedy"][0] - x["optimized"][0]),
                                       reverse=True)[:10],
            "design": design, "prior_holdout": holdout,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "prior_plan_sha256": sha256((PRIOR / "plans.bin").read_bytes()).hexdigest()}


if __name__ == "__main__":
    result = run()
    output = HERE / "screen.json"
    if "--write" in sys.argv:
        assert not output.exists()
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        assert json.loads(output.read_text()) == result
    print(json.dumps({key: result[key] for key in
                      ("all_count_patterns", "improved_count_patterns", "design",
                       "prior_holdout")}, sort_keys=True))
