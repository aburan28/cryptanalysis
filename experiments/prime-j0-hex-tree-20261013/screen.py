#!/usr/bin/env python3
"""Compare serial and gauge-tree evaluation of frozen hex-terminal terms."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
HEX = EXP / "prime-j0-hex-terminal-20261012"
NATIVE = EXP / "prime-j0-secp256k1-native"
DESIGN = EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json"
CALIBRATION = EXP / "prime-j0-axis286-20261012/holdout.json"
REPLAY = HEX / "replay.json"
sys.path.insert(0, str(HEX))
import hex as lattice  # noqa: E402
import screen as hex_screen  # noqa: E402


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class Node:
    gauge: int
    depth: int
    work: int
    affine: bool


def serial_cost(gauges: list[int]) -> tuple[int, int, int]:
    if not gauges:
        return 0, 0, 0
    order = [g for g in (1, 2, 0) if g in gauges]
    turns = sum(a != b for a, b in zip(order, order[1:])) + (order[-1] != 0)
    work = 10 * (len(gauges) - 1) + turns
    return work, work, turns


@cache
def tree_plan(gauges: tuple[int, ...]) -> tuple[int, int, int, tuple[tuple[int, int, int], ...]]:
    assert gauges == tuple(sorted(gauges))  # plans are keyed by gauge counts
    nodes = [Node(g, 0, 0, True) for g in gauges]
    turns = 0
    steps = []
    if not nodes:
        return 0, 0, 0, ()
    while len(nodes) > 1:
        options = []
        for i, a in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                b = nodes[j]
                products = (6 if a.affine and b.affine else
                            10 if a.affine or b.affine else 14)
                for gauge in sorted({a.gauge, b.gauge}):
                    ra, rb = int(a.gauge != gauge), int(b.gauge != gauge)
                    depth = max(a.depth + ra, b.depth + rb) + products
                    work = a.work + b.work + products + ra + rb
                    options.append((depth, work, gauge, i, j, ra + rb))
        depth, work, gauge, i, j, turn = min(options)
        steps.append((i, j, gauge))
        turns += turn
        nodes.pop(j)
        nodes.pop(i)
        nodes.append(Node(gauge, depth, work, False))
    root = nodes[0]
    turns += int(root.gauge != 0)
    return (root.work + int(root.gauge != 0),
            root.depth + int(root.gauge != 0), turns, tuple(steps))


def selected_gauges(k: int, old, orbit, codes, digits) -> list[int]:
    a, b = old.nearest_representative(k)
    assert (a + old.LAMBDA_TAU * b - k) % lattice.ORDER == 0
    gauges = []
    for _ in range(lattice.WINDOWS):
        packed = codes[(a % lattice.RADIX) * lattice.RADIX + b % lattice.RADIX]
        orbit_id, code = packed >> 3, packed & 7
        digit = orbit.unit_images(digits[orbit_id])[code]
        assert (a - digit[0]) % lattice.RADIX == 0
        assert (b - digit[1]) % lattice.RADIX == 0
        a, b = (a - digit[0]) // lattice.RADIX, (b - digit[1]) // lattice.RADIX
        if orbit_id:
            gauges.append(code // 2)
    assert lattice.in_domain((a, b))
    top_id, top_code = lattice.top_index((a, b))
    if top_id:
        gauges.append(top_code // 2)
    assert len(gauges) <= 16
    return gauges


def panel(scalars, old, orbit, codes, digits) -> dict:
    tree_plan.cache_clear()
    totals = {key: 0 for key in ("terms", "additions", "serial_work", "serial_depth",
                               "serial_rotations", "tree_work", "tree_depth",
                               "tree_rotations", "improved_depth", "improved_work")}
    max_terms = 0
    for k in scalars:
        gauges = selected_gauges(k, old, orbit, codes, digits)
        sw, sd, sr = serial_cost(gauges)
        tw, td, tr, _ = tree_plan(tuple(sorted(gauges)))
        totals["terms"] += len(gauges)
        totals["additions"] += max(0, len(gauges) - 1)
        totals["serial_work"] += sw
        totals["serial_depth"] += sd
        totals["serial_rotations"] += sr
        totals["tree_work"] += tw
        totals["tree_depth"] += td
        totals["tree_rotations"] += tr
        totals["improved_depth"] += td < sd
        totals["improved_work"] += tw < sw
        max_terms = max(max_terms, len(gauges))
    return {"cases": len(scalars), "max_terms": max_terms, **totals,
            "distinct_gauge_plans": tree_plan.cache_info().currsize}


def run() -> dict:
    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("tree_orbit", NATIVE / "unit_orbit_windows_screen.py")
    old = load("tree_representative", NATIVE / "radix943_screen.py")
    codes, digits = hex_screen.atlas(orbit)
    source = json.loads(DESIGN.read_text())
    scalars = [int(value, 16) for value in source["scalars_hex"]]
    assert len(scalars) == 4096
    design = panel(scalars, old, orbit, codes, digits)
    assert design["terms"] == 65534
    fixture = json.loads(CALIBRATION.read_text())
    calibrate = panel([int(case["scalar_hex"], 16) for case in fixture["cases"]],
                      old, orbit, codes, digits)
    recorded = json.loads(REPLAY.read_text())["panels"][0]
    assert calibrate["additions"] == recorded["candidate_additions"]
    assert calibrate["serial_rotations"] == recorded["candidate_rotations"]
    return {"schema": 1, "status": "operation_model_only",
            "design": design, "serial_calibration": calibrate,
            "fixture_sha256": sha256(DESIGN.read_bytes()).hexdigest(),
            "calibration_fixture_sha256": sha256(CALIBRATION.read_bytes()).hexdigest(),
            "calibration_replay_sha256": sha256(REPLAY.read_bytes()).hexdigest(),
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "hex_source_sha256": sha256((HEX / "hex.py").read_bytes()).hexdigest(),
            "hex_screen_sha256": sha256((HEX / "screen.py").read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = run()
    target = HERE / "design.json"
    if args.write:
        target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        if json.loads(target.read_text()) != result:
            raise SystemExit("design receipt differs")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
