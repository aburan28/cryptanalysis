#!/usr/bin/env python3
"""Recode a frozen secp256k1 panel with fifteen shift windows and one top point."""

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
CONTROL = EXP / "prime-j0-axis286-20261012/design-rows.jsonl"
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
    assert len(digits) == 10_924 and all(code != UNSET for code in codes)
    for index, packed in enumerate(codes):
        digit = orbit.unit_images(digits[packed >> 3])[packed & 7]
        assert (digit[0] % base, digit[1] % base) == divmod(index, base)
        assert 3*axis.norm(digit) <= base*base
    return codes, digits, digest.hexdigest()


def run() -> tuple[dict, bytes]:
    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("direct_terminal_orbit", NATIVE / "unit_orbit_windows_screen.py")
    old = load("direct_terminal_reference", NATIVE / "radix943_screen.py")
    codes, digits, atlas_digest = atlas(orbit)
    scalars = [int(v, 16) for v in json.loads(DESIGN.read_text())["scalars_hex"]]
    controls = [json.loads(line) for line in CONTROL.read_text().splitlines()]
    assert len(scalars) == len(controls) == 4096
    totals = Counter()
    rows = []
    top_seen = set()
    for index, (scalar, control) in enumerate(zip(scalars, controls, strict=True)):
        assert control["index"] == index
        digest = sha256(scalar.to_bytes(32, "big")).hexdigest()
        assert control["scalar_sha256"] == digest
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
        top_id, code = axis.top_index(terminal)
        if terminal != (0, 0):
            selected.append([axis.WINDOWS, a, b, code])
            top_seen.add(top_id)
        reconstructed[0] += factor*a
        reconstructed[1] += factor*b
        assert tuple(reconstructed) == representative
        totals.update(cases=1, terms=len(selected),
                      ordinary_terms=len(selected)-(terminal != (0, 0)),
                      top_terms=(terminal != (0, 0)),
                      control286_terms=len(control["selected"]))
        rows.append({"index": index, "scalar_sha256": digest,
                     "representative": [str(x) for x in representative],
                     "terminal": list(terminal), "top_orbit_id": top_id,
                     "top_unit_code": code, "selected": selected})
    entries = axis.WINDOWS*len(digits) + axis.TOP_ENTRIES
    assert entries == 177_174
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    return {
        "schema": 1, "status": "direct_terminal_design_reconstruction",
        "curve": "secp256k1", "base": axis.BASE, "windows": axis.WINDOWS,
        "top_cap_3norm": axis.CAP, "top_orbits": axis.TOP_ENTRIES,
        "ordinary_orbits_per_window": len(digits),
        "residues_audited": axis.BASE**2,
        "canonical_digits_sha256": atlas_digest,
        "table_point_entries": entries,
        "table_point_payload_bytes": 64*entries,
        "residue_map_bytes_at_4_each": 4*axis.BASE**2,
        "distinct_top_orbits_in_panel": len(top_seen),
        "totals": dict(sorted(totals.items())),
        "rows_sha256": sha256(row_bytes).hexdigest(),
        "frozen_design_sha256": sha(DESIGN),
        "control286_rows_sha256": sha(CONTROL),
        "axis_source_sha256": sha(HERE / "axis.py"),
        "screen_source_sha256": sha(Path(__file__)),
        "orbit_screen_sha256": sha(NATIVE / "unit_orbit_windows_screen.py"),
    }, row_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
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
