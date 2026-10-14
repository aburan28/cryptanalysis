#!/usr/bin/env python3
"""Check Voronoi clipping on frozen design and independently generated panels."""

from __future__ import annotations

import argparse
from array import array
from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

import hex

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NATIVE = EXP / "prime-j0-secp256k1-native"
DESIGN = EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json"
PRIOR_ROWS = EXP / "prime-j0-power2-direct-terminal-20261012/design-rows.jsonl"
PANELS = (
    EXP / "prime-j0-axis286-20261012/holdout.json",
    EXP / "prime-j0-power2-direct-terminal-20261012/holdout.json",
    EXP / "prime-j0-power2-direct-terminal-20261012/holdout2.json",
)


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def atlas(orbit) -> tuple[array, list[tuple[int,int]]]:
    codes = array("I", [0xffffffff])*65536
    digits: list[tuple[int,int]] = []
    for index in range(65536):
        if codes[index] != 0xffffffff:
            continue
        residue = divmod(index,256)
        images = [(a % 256,b % 256) for a,b in orbit.unit_images(residue)]
        assert residue == min(images)
        digit = orbit.nearest_digit(residue,256)
        orbit_id = len(digits)
        digits.append(digit)
        for code,(a,b) in enumerate(images):
            slot = a*256+b
            if codes[slot] == 0xffffffff:
                codes[slot] = (orbit_id << 3)|code
    assert len(digits) == 10924 and all(x != 0xffffffff for x in codes)
    return codes,digits


def evaluate(scalars: list[int], old, orbit, codes, digits,
             prior_rows: list[dict] | None = None) -> dict:
    terms = 0
    top_ids: set[int] = set()
    nonzero_tops = 0
    for index,k in enumerate(scalars):
        rep = old.nearest_representative(k)
        assert (rep[0]+old.LAMBDA_TAU*rep[1]-k) % hex.ORDER == 0
        assert 3*hex.norm(rep) <= hex.ORDER
        assert all(abs(hex.twice_inner(rep,v)) <= hex.ORDER for v in hex.NEIGHBORS)
        a,b = rep
        for _ in range(15):
            packed = codes[(a % 256)*256+(b % 256)]
            digit = orbit.unit_images(digits[packed >> 3])[packed & 7]
            assert (a-digit[0]) % 256 == (b-digit[1]) % 256 == 0
            a,b = (a-digit[0])//256,(b-digit[1])//256
            terms += digit != (0,0)
        top = (a,b)
        assert hex.in_domain(top)
        top_id,code = hex.top_index(top)
        if top != (0,0):
            assert hex.images(next(z for z in hex.images(top) if hex.sector(z)))[code] == top
            nonzero_tops += 1
            top_ids.add(top_id)
            terms += 1
        if prior_rows is not None:
            assert prior_rows[index]["index"] == index
            assert tuple(map(int,prior_rows[index]["representative"])) == rep
            assert tuple(prior_rows[index]["terminal"]) == top
    return {"cases":len(scalars),"selected_terms":terms,
            "nonzero_tops":nonzero_tops,"distinct_top_orbits":len(top_ids)}


def run() -> dict:
    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("voronoi_orbit", NATIVE / "unit_orbit_windows_screen.py")
    old = load("voronoi_representative", NATIVE / "radix943_screen.py")
    assert old.ORDER == hex.ORDER
    codes,digits = atlas(orbit)
    data = json.loads(DESIGN.read_text())
    controls = [json.loads(line) for line in PRIOR_ROWS.read_text().splitlines()]
    design = evaluate([int(value,16) for value in data["scalars_hex"]],
                      old,orbit,codes,digits,controls)
    assert design["cases"] == 4096 and design["selected_terms"] == 65534
    panels = []
    for path in PANELS:
        values = json.loads(path.read_text())
        scalars = [int(case["scalar_hex"],16) for case in values["cases"]]
        result = evaluate(scalars,old,orbit,codes,digits)
        assert result["cases"] == 512
        panels.append({"fixture":str(path.relative_to(EXP)),"sha256":sha(path),**result})
    return {"schema":1,"status":"voronoi_terminal_panel_screen_passed",
            "design":{"fixture":str(DESIGN.relative_to(EXP)),"sha256":sha(DESIGN),**design},
            "panels":panels,"prior_rows_sha256":sha(PRIOR_ROWS),
            "hex_source_sha256":sha(HERE/"hex.py"),
            "source_sha256":sha(Path(__file__))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write",action="store_true")
    group.add_argument("--check",action="store_true")
    args = parser.parse_args()
    data = (json.dumps(run(),indent=2,sort_keys=True)+"\n").encode()
    target = HERE/"screen.json"
    if args.write:
        if target.exists():
            raise SystemExit("screen receipt exists; use --check")
        target.write_bytes(data)
    elif target.read_bytes()!=data:
        raise SystemExit("screen receipt differs from sources")
    print(json.dumps({"status":"passed","design_cases":4096,"holdout_cases":1536}))


if __name__ == "__main__":
    main()
