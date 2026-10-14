#!/usr/bin/env python3
"""Audit the radix-671 split-top table and frozen scalar design panel."""

from __future__ import annotations

import argparse
from array import array
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from math import isqrt
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NATIVE = EXP / "prime-j0-secp256k1-native"
sys.path.insert(0, str(NATIVE))
DESIGN = EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json"
PLANS = EXP / "prime-j0-pareto-tree-20261012/plans.bin"
CONTROL = EXP / "prime-j0-radix929-topball-20261012/design-rows.jsonl"
BASE = 671
WINDOWS = 12
SPLIT = 256
HALF = SPLIT // 2
CAP = 1_668_628_670
ABOUND = 47_168
BBOUND = 27_232
HIGH_A = 184
HIGH_B = 106
UNSET = (1 << 32) - 1


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def split(x: int) -> tuple[int, int]:
    high = (x + HALF) // SPLIT
    low = x - SPLIT * high
    assert -HALF <= low < HALF and x == low + SPLIT * high
    return low, high


def plan_cost(codes: list[int], table: bytes, plans) -> dict[str, int]:
    counts = tuple(sum(code // 2 == gauge for code in codes)
                   for gauge in range(3))
    offset = 42 * plans.index(counts)
    data = table[offset:offset + 42]
    n = len(codes)
    assert len(data) == 42 and data[39] == max(n - 1, 0)
    return {"terms": n, "products": (10*n - 14 if n >= 2 else 0) + data[40],
            "rotations": data[40], "depth": data[41]}


def atlas(orbit) -> tuple[array, list[tuple[int, int]], str]:
    codes = array("I", [UNSET]) * (BASE * BASE)
    digits = []
    digest = sha256()
    for index in range(BASE * BASE):
        if codes[index] != UNSET:
            continue
        residue = divmod(index, BASE)
        images = [(a % BASE, b % BASE) for a, b in orbit.unit_images(residue)]
        assert residue == min(images)
        digit = orbit.nearest_digit(residue, BASE)
        assert 3 * orbit.norm(digit) <= BASE * BASE
        orbit_id = len(digits)
        digits.append(digit)
        digest.update(struct.pack("<hh", *digit))
        for code, (a, b) in enumerate(images):
            slot = a * BASE + b
            if codes[slot] == UNSET:
                codes[slot] = (orbit_id << 3) | code
    assert all(code != UNSET for code in codes)
    assert len(digits) == (BASE * BASE + 5) // 6 == 75_041
    for index, packed in enumerate(codes):
        digit = orbit.unit_images(digits[packed >> 3])[packed & 7]
        assert (digit[0] % BASE, digit[1] % BASE) == divmod(index, BASE)
        assert 3 * orbit.norm(digit) <= BASE * BASE
    return codes, digits, digest.hexdigest()


def run() -> tuple[dict, bytes]:
    orbit = load("split671_orbit", NATIVE / "unit_orbit_windows_screen.py")
    old = load("split671_old", NATIVE / "radix943_screen.py")
    plans = load("split671_plans", EXP / "prime-j0-pareto-tree-20261012/plans.py")
    table = PLANS.read_bytes()
    assert len(table) == 680 * 42
    codes, digits, atlas_digest = atlas(orbit)
    initial_radius = 1 << 128
    radius = sum(BASE**j for j in range(1, WINDOWS + 1))
    assert (initial_radius + radius)**2 < (CAP + 1) * BASE**(2*WINDOWS)
    assert (initial_radius + radius)**2 >= CAP * BASE**(2*WINDOWS)
    assert 3*ABOUND*ABOUND <= 4*CAP < 3*(ABOUND+1)**2
    assert 9*BBOUND*BBOUND <= 4*CAP < 9*(BBOUND+1)**2
    assert (ABOUND + HALF)//SPLIT == HIGH_A
    assert (BBOUND + HALF)//SPLIT == HIGH_B
    ordinary = WINDOWS * len(digits)
    low_entries = SPLIT*SPLIT
    high_entries = (2*HIGH_A+1)*(2*HIGH_B+1)
    assert ordinary == 900_492 and low_entries == 65_536
    assert high_entries == 78_597
    assert ordinary + low_entries + high_entries == 1_044_625

    design = json.loads(DESIGN.read_text())
    scalars = [int(value, 16) for value in design["scalars_hex"]]
    controls = [json.loads(line) for line in CONTROL.read_text().splitlines()]
    assert len(scalars) == len(controls) == 4096
    totals = {key: 0 for key in ("cases", "terms", "products", "rotations",
                                  "low_active", "high_active", "control929_products",
                                  "control943_products")}
    max_top = 0
    rows = []
    for index, (scalar, control) in enumerate(zip(scalars, controls)):
        start = old.nearest_representative(scalar)
        assert tuple(map(int, control["representative"])) == start
        assert 3 * orbit.norm(start) <= old.ORDER
        assert (start[0] + old.LAMBDA_TAU*start[1] - scalar) % old.ORDER == 0
        a, b = start
        rebuilt_a = rebuilt_b = 0
        power = 1
        selected = []
        for _ in range(WINDOWS):
            packed = codes[(a % BASE)*BASE + (b % BASE)]
            orbit_id, code = packed >> 3, packed & 7
            da, db = orbit.unit_images(digits[orbit_id])[code]
            assert (a-da) % BASE == (b-db) % BASE == 0
            assert 3 * orbit.norm((da, db)) <= BASE*BASE
            rebuilt_a += power*da
            rebuilt_b += power*db
            a, b = (a-da)//BASE, (b-db)//BASE
            if da or db:
                selected.append(code)
            power *= BASE
        top_norm = 3 * orbit.norm((a, b))
        assert top_norm <= CAP
        max_top = max(max_top, top_norm)
        assert abs(a) <= ABOUND and abs(b) <= BBOUND
        la, ha = split(a)
        lb, hb = split(b)
        assert abs(ha) <= HIGH_A and abs(hb) <= HIGH_B
        assert (rebuilt_a + power*(la+SPLIT*ha),
                rebuilt_b + power*(lb+SPLIT*hb)) == start
        if la or lb:
            selected.append(0)
            totals["low_active"] += 1
        if ha or hb:
            selected.append(0)
            totals["high_active"] += 1
        cost = plan_cost(selected, table, plans)
        totals["cases"] += 1
        for key in ("terms", "products", "rotations"):
            totals[key] += cost[key]
        totals["control929_products"] += control["candidate"]["products"]
        totals["control943_products"] += control["reference"]["products"]
        rows.append({"index": index,
                     "scalar_sha256": sha256(scalar.to_bytes(32, "big")).hexdigest(),
                     "top": [a, b], "low": [la, lb], "high": [ha, hb],
                     "codes": selected, "cost": cost,
                     "control929_products": control["candidate"]["products"]})
    assert totals == {"cases": 4096, "terms": 57_343, "products": 525_674,
                      "rotations": 9_588, "low_active": 4096,
                      "high_active": 4095, "control929_products": 484_152,
                      "control943_products": 484_163}
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    receipt = {"schema": 1, "status": "exact_recode_and_design_source_model",
               "base": BASE, "windows": WINDOWS, "split": SPLIT,
               "top_cap_3norm": CAP, "a_bound": ABOUND, "b_bound": BBOUND,
               "max_design_top_3norm": max_top,
               "ordinary_orbits_per_window": len(digits),
               "ordinary_atlas_sha256": atlas_digest,
               "residues_audited": len(codes),
               "ordinary_point_entries": ordinary,
               "low_point_entries": low_entries,
               "high_point_entries": high_entries,
               "total_point_entries": ordinary + low_entries + high_entries,
               "point_payload_bytes": 64*(ordinary + low_entries + high_entries),
               "totals": totals, "rows_sha256": sha256(row_bytes).hexdigest(),
               "design_sha256": sha(DESIGN), "plans_sha256": sha(PLANS),
               "control_rows_sha256": sha(CONTROL),
               "orbit_source_sha256": sha(NATIVE / "unit_orbit_windows_screen.py"),
               "reference_source_sha256": sha(NATIVE / "radix943_screen.py"),
               "screen_source_sha256": sha(Path(__file__))}
    return receipt, row_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt, rows = run()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    receipt_path = HERE / "design.json"
    rows_path = HERE / "design-rows.jsonl"
    if args.write:
        if receipt_path.exists() or rows_path.exists():
            raise SystemExit("design receipt exists; use --check")
        receipt_path.write_bytes(payload)
        rows_path.write_bytes(rows)
    elif receipt_path.read_bytes() != payload or rows_path.read_bytes() != rows:
        raise SystemExit("split-top design differs from frozen files")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
