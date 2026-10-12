#!/usr/bin/env python3
"""Audit ordinary residues and reconstruct a frozen 4096-scalar panel."""

from __future__ import annotations

import argparse
from array import array
from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import struct
import sys

import axis

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NATIVE = EXP / "prime-j0-secp256k1-native"
DESIGN = EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json"
CONTROL = EXP / "prime-j0-radix569-topball-20261012/design-rows.jsonl"
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


def atlas(orbit) -> tuple[array, list[tuple[int, int]], str]:
    base = axis.BASE
    codes = array("I", [UNSET]) * (base*base)
    digits: list[tuple[int, int]] = []
    digest = sha256()
    for index in range(base*base):
        if codes[index] != UNSET:
            continue
        residue = divmod(index, base)
        images = [(a % base, b % base) for a, b in orbit.unit_images(residue)]
        assert residue == min(images)
        digit = orbit.nearest_digit(residue, base)
        assert 3*axis.norm(digit) <= base*base
        orbit_id = len(digits)
        digits.append(digit)
        digest.update(struct.pack("<hh", *digit))
        for code, (a, b) in enumerate(images):
            slot = a*base+b
            if codes[slot] == UNSET:
                codes[slot] = (orbit_id << 3) | code
    assert len(digits) == 28_844
    assert all(code != UNSET for code in codes)
    for index, packed in enumerate(codes):
        digit = orbit.unit_images(digits[packed >> 3])[packed & 7]
        assert (digit[0] % base, digit[1] % base) == divmod(index, base)
        assert 3*axis.norm(digit) <= base*base
    return codes, digits, digest.hexdigest()


def run() -> tuple[dict, bytes]:
    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("axis416_orbit", NATIVE / "unit_orbit_windows_screen.py")
    old = load("axis416_reference", NATIVE / "radix943_screen.py")
    codes, digits, atlas_digest = atlas(orbit)
    scalars = [int(v, 16) for v in json.loads(DESIGN.read_text())["scalars_hex"]]
    controls = [json.loads(line) for line in CONTROL.read_text().splitlines()]
    assert len(scalars) == len(controls) == 4096
    totals = Counter()
    rows = []
    max_u = max_b = 0
    for index, (scalar, control) in enumerate(zip(scalars, controls)):
        representative = old.nearest_representative(scalar)
        assert tuple(map(int, control["representative"])) == representative
        assert 3*axis.norm(representative) <= old.ORDER
        assert (representative[0] + old.LAMBDA_TAU*representative[1] - scalar) % old.ORDER == 0
        a, b = representative
        reconstructed = [0, 0]
        factor = 1
        selected = []
        for window in range(axis.WINDOWS):
            packed = codes[(a % axis.BASE)*axis.BASE + (b % axis.BASE)]
            orbit_id, code = packed >> 3, packed & 7
            da, db = orbit.unit_images(digits[orbit_id])[code]
            assert (a-da) % axis.BASE == (b-db) % axis.BASE == 0
            reconstructed[0] += factor*da
            reconstructed[1] += factor*db
            a, b = (a-da)//axis.BASE, (b-db)//axis.BASE
            if da or db:
                selected.append([window, da, db, code])
            factor *= axis.BASE
        terminal = (a, b)
        assert 3*axis.norm(terminal) <= axis.CAP
        code, u, v = axis.factor(terminal)
        assert axis.images((-u, v))[code] == terminal
        if terminal != (0, 0):
            selected.extend(([axis.WINDOWS, -u, 0, code],
                             [axis.WINDOWS, 0, v, code]))
        reconstructed[0] += factor*a
        reconstructed[1] += factor*b
        assert tuple(reconstructed) == representative
        max_u, max_b = max(max_u, u), max(max_b, v)
        totals.update(cases=1, terms=len(selected), ordinary_terms=len(selected)-2*(terminal != (0,0)),
                      top_axis_terms=2*(terminal != (0,0)),
                      control569_terms=control["candidate"]["terms"])
        rows.append({"index": index,
                     "scalar_sha256": sha256(scalar.to_bytes(32, "big")).hexdigest(),
                     "representative": [str(x) for x in representative],
                     "terminal": list(terminal), "sector_code": code,
                     "axis_u": u, "axis_b": v,
                     "selected": selected})
    entries = axis.WINDOWS*len(digits) + axis.U_MAX + axis.B_MAX
    assert entries == 433_578
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    return {
        "schema": 1, "status": "exact_axis_format_design_replay",
        "curve": "secp256k1", "base": axis.BASE, "windows": axis.WINDOWS,
        "top_cap_3norm": axis.CAP, "axis_u_max": axis.U_MAX,
        "axis_b_max": axis.B_MAX,
        "ordinary_orbits_per_window": len(digits),
        "residues_audited": axis.BASE**2,
        "canonical_digits_sha256": atlas_digest,
        "table_point_entries": entries,
        "table_point_payload_bytes": 64*entries,
        "residue_map_bytes_at_4_each": 4*axis.BASE**2,
        "max_axis_u_in_panel": max_u, "max_axis_b_in_panel": max_b,
        "totals": dict(sorted(totals.items())),
        "rows_sha256": sha256(row_bytes).hexdigest(),
        "frozen_design_sha256": sha(DESIGN),
        "control569_rows_sha256": sha(CONTROL),
        "axis_source_sha256": sha(HERE / "axis.py"),
        "screen_source_sha256": sha(Path(__file__)),
        "orbit_screen_sha256": sha(NATIVE / "unit_orbit_windows_screen.py"),
    }, row_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt, rows = run()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        for name in ("design.json", "design-rows.jsonl"):
            if (HERE / name).exists():
                raise SystemExit(f"{name} exists; use --check")
        (HERE / "design.json").write_bytes(payload)
        (HERE / "design-rows.jsonl").write_bytes(rows)
    elif (HERE / "design.json").read_bytes() != payload or \
            (HERE / "design-rows.jsonl").read_bytes() != rows:
        raise SystemExit("design receipt differs from frozen sources or inputs")
    print(json.dumps({"entries": receipt["table_point_entries"],
                      "totals": receipt["totals"]}, sort_keys=True))


if __name__ == "__main__":
    main()
