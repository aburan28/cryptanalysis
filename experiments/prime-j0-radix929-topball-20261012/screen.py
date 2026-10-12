#!/usr/bin/env python3
"""Replay the radix-929 top-state format on the frozen scalar design panel."""

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
import topball

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NATIVE = EXP / "prime-j0-secp256k1-native"
DESIGN = EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json"
PLANS = EXP / "prime-j0-pareto-tree-20261012/plans.bin"
BASE = 929
WINDOWS = 12
REFERENCE_WINDOWS = 13
UNSET = (1 << 32) - 1


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def atlas(orbit):
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
    assert len(digits) == (BASE * BASE + 5) // 6 == 143_841
    return codes, digits, digest.hexdigest()


def plan_cost(codes, table, plans):
    counts = tuple(sum(code // 2 == gauge for code in codes) for gauge in range(3))
    index = plans.index(counts)
    data = table[42 * index:42 * (index + 1)]
    n = len(codes)
    assert len(data) == 42 and data[39] == max(n - 1, 0)
    return {"terms": n, "products": (10 * n - 14 if n >= 2 else 0) + data[40],
            "rotations": data[40], "depth": data[41]}


def run():
    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("radix929_orbit_screen", NATIVE / "unit_orbit_windows_screen.py")
    old = load("radix929_old_radix_screen", NATIVE / "radix943_screen.py")
    plans = load("radix929_plans", EXP / "prime-j0-pareto-tree-20261012/plans.py")
    table = PLANS.read_bytes()
    assert len(table) == 680 * 42
    codes, digits, atlas_digest = atlas(orbit)
    old_cache = {}

    prefix = [0]
    for u in range(1, topball.MAX_ROW + 1):
        low, high = topball.row_bounds(u)
        prefix.append(prefix[-1] + max(0, high - low + 1))
    assert prefix[-1] + 1 == 136_993

    def top_code_rank(pair):
        assert 3 * topball.norm(pair) <= topball.CAP
        if pair == (0, 0):
            return 0, 0
        canonical = [candidate for candidate in topball.images(pair) if topball.sector(candidate)]
        assert len(canonical) == 1
        ca, cb = canonical[0]
        u = -ca
        low, high = topball.row_bounds(u)
        assert low <= cb <= high
        rank = 1 + prefix[u - 1] + cb - low
        code = topball.images(canonical[0]).index(pair)
        assert 0 < rank < 136_993 and code < 6
        return code, rank

    def digit929(pair):
        ra, rb = pair[0] % BASE, pair[1] % BASE
        value = codes[ra * BASE + rb]
        orbit_id, code = value >> 3, value & 7
        assert code < 6
        digit = orbit.unit_images(digits[orbit_id])[code]
        assert (digit[0] % BASE, digit[1] % BASE) == (ra, rb)
        return digit, code

    def digit943(pair):
        residue = pair[0] % 943, pair[1] % 943
        if residue not in old_cache:
            canonical = min((a % 943, b % 943)
                            for a, b in orbit.unit_images(residue))
            seed = old.nearest_digit(canonical)
            images = orbit.unit_images(seed)
            code = next(code for code, (a, b) in enumerate(images)
                        if (a % 943, b % 943) == residue)
            old_cache[residue] = images[code], code
        return old_cache[residue]

    def recode(representative, base, chooser, windows):
        a, b = representative
        factor = 1
        rebuilt = [0, 0]
        selected = []
        for _ in range(windows):
            (da, db), code = chooser((a, b))
            assert (a - da) % base == (b - db) % base == 0
            assert 3 * orbit.norm((da, db)) <= base * base
            rebuilt[0] += factor * da
            rebuilt[1] += factor * db
            a, b = (a - da) // base, (b - db) // base
            if da or db:
                selected.append(code)
            factor *= base
        rebuilt[0] += factor * a
        rebuilt[1] += factor * b
        assert tuple(rebuilt) == representative
        return (a, b), selected

    scalars = [int(value, 16) for value in json.loads(DESIGN.read_text())["scalars_hex"]]
    assert len(scalars) == 4096
    totals = Counter()
    top_ranks = set()
    savings = Counter()
    rows = []
    for index, scalar in enumerate(scalars):
        representative = old.nearest_representative(scalar)
        assert representative == tuple(orbit.hex_choices(scalar)[0][2:4])
        assert 3 * orbit.norm(representative) <= old.ORDER
        assert (representative[0] + old.LAMBDA_TAU * representative[1] - scalar) % old.ORDER == 0
        residual, selected = recode(representative, BASE, digit929, WINDOWS)
        top_code, top_rank = top_code_rank(residual)
        top_ranks.add(top_rank)
        if residual != (0, 0):
            selected.append(top_code)
        old_residual, old_selected = recode(representative, 943, digit943, REFERENCE_WINDOWS)
        assert old_residual == (0, 0)
        candidate = plan_cost(selected, table, plans)
        reference = plan_cost(old_selected, table, plans)
        totals.update(cases=1, candidate_terms=candidate["terms"],
                      candidate_products=candidate["products"],
                      candidate_rotations=candidate["rotations"],
                      candidate_depth=candidate["depth"],
                      reference_terms=reference["terms"],
                      reference_products=reference["products"],
                      reference_rotations=reference["rotations"],
                      reference_depth=reference["depth"],
                      top_nonzero=int(residual != (0, 0)))
        savings[reference["products"] - candidate["products"]] += 1
        rows.append({"index": index,
                     "scalar_sha256": sha256(scalar.to_bytes(32, "big")).hexdigest(),
                     "representative": [str(x) for x in representative],
                     "top": list(residual), "top_rank": top_rank,
                     "candidate_codes": selected,
                     "candidate": candidate, "reference": reference})
    assert totals["reference_products"] == 484_163
    assert totals["reference_rotations"] == 9027
    assert totals["candidate_products"] == 484_152
    assert totals["candidate_terms"] == 53_248
    row_bytes = ("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":"))
                           for row in rows) + "\n").encode()
    return {
        "schema": 1, "status": "design_source_model_and_exact_recode",
        "radix": BASE, "windows": WINDOWS,
        "curve": "secp256k1", "top_cap_3norm": topball.CAP,
        "top_unit_orbits": 136_993, "distinct_top_ranks_in_panel": len(top_ranks),
        "table_point_entries": WINDOWS * len(digits) + 136_993,
        "table_point_bytes_at_64_each": (WINDOWS * len(digits) + 136_993) * 64,
        "residue_map_bytes_at_4_each": BASE * BASE * 4,
        "canonical_digit_bytes_at_4_each": len(digits) * 4,
        "canonical_orbits_per_window": len(digits), "residues_audited": BASE * BASE,
        "canonical_digits_sha256": atlas_digest,
        "reference_radix": 943,
        "reference_point_entries": 13 * 148_209,
        "reference_point_bytes_at_64_each": 13 * 148_209 * 64,
        "totals": dict(sorted(totals.items())),
        "product_difference_histogram": dict(sorted(savings.items())),
        "frozen_design_sha256": sha(DESIGN), "plan_table_sha256": sha(PLANS),
        "topball_source_sha256": sha(HERE / "topball.py"),
        "topball_receipt_sha256": sha(HERE / "topball.json"),
        "screen_source_sha256": sha(Path(__file__)),
        "orbit_screen_sha256": sha(NATIVE / "unit_orbit_windows_screen.py"),
        "radix943_screen_sha256": sha(NATIVE / "radix943_screen.py"),
        "rows_sha256": sha256(row_bytes).hexdigest(),
    }, row_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt, rows = run()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    path = HERE / "design.json"
    row_path = HERE / "design-rows.jsonl"
    if args.write:
        if path.exists() or row_path.exists():
            raise SystemExit("design output exists; use --check")
        path.write_bytes(payload)
        row_path.write_bytes(rows)
        print(json.dumps({"status": receipt["status"], "totals": receipt["totals"]}, sort_keys=True))
    elif path.read_bytes() != payload or row_path.read_bytes() != rows:
        raise SystemExit("design receipt differs from frozen sources or inputs")
    else:
        print("radix-929 top-state design and full residue audit verified")


if __name__ == "__main__":
    main()
