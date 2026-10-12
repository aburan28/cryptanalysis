#!/usr/bin/env python3
"""Replay both fixed-base source schedules on frozen design and holdout inputs."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NATIVE = ROOT / "prime-j0-secp256k1-native"
DESIGN = ROOT / "prime-j0-sector-digit-20261010/fresh-inputs.json"
HOLDOUT = HERE / "holdout.json"
PLANS = ROOT / "prime-j0-pareto-tree-20261012/plans.bin"
RADIX = 943


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def plan_cost(codes, plan_bytes, plan_index):
    counts = tuple(sum(code // 2 == gauge for code in codes)
                   for gauge in range(3))
    data = plan_bytes[42 * plan_index(counts):42 * (plan_index(counts) + 1)]
    assert len(data) == 42 and data[39] == max(len(codes) - 1, 0)
    n = len(codes)
    return n, (10 * n - 14 if n >= 2 else 0) + data[40], data[40], data[41]


def main():
    sys.path.insert(0, str(NATIVE.resolve()))
    orbit = load("orbit_screen", NATIVE / "unit_orbit_windows_screen.py")
    radix = load("radix_screen", NATIVE / "radix943_screen.py")
    plans = load("pareto_plans", ROOT / "prime-j0-pareto-tree-20261012/plans.py")
    table = PLANS.read_bytes()
    assert len(table) == 680 * 42
    atlas = {width: orbit.OrbitAtlas(width) for width in (9, 10)}
    residue_cache = {}

    def radix_digit(a, b):
        residue = (a % RADIX, b % RADIX)
        if residue not in residue_cache:
            canonical = min((x % RADIX, y % RADIX)
                            for x, y in orbit.unit_images(residue))
            seed = radix.nearest_digit(canonical)
            images = orbit.unit_images(seed)
            codes = [code for code, (x, y) in enumerate(images)
                     if (x % RADIX, y % RADIX) == residue]
            assert codes
            code = codes[0]  # same first assignment as the native orbit atlas
            digit = images[code]
            assert (digit[0] % RADIX, digit[1] % RADIX) == residue
            assert 3 * radix.norm(digit) <= RADIX * RADIX
            residue_cache[residue] = (digit, code)
        return residue_cache[residue]

    def one_scalar(scalar):
        scalar %= radix.ORDER
        representative = tuple(orbit.hex_choices(scalar)[0][2:4])
        assert representative == radix.nearest_representative(scalar)
        ref_codes = [code for _, code, active in orbit.recode(representative, atlas)
                     if active]
        reference = plan_cost(ref_codes, table, plans.index)
        a, b = representative
        candidate_codes = []
        for _ in range(13):
            (da, db), code = radix_digit(a, b)
            assert (a - da) % RADIX == (b - db) % RADIX == 0
            a, b = (a - da) // RADIX, (b - db) // RADIX
            if da or db:
                candidate_codes.append(code)
        assert (a, b) == (0, 0)
        candidate = plan_cost(candidate_codes, table, plans.index)
        return reference, candidate

    results = {}
    for name, scalars in (
        ("design", [int(value, 16) for value in json.loads(DESIGN.read_text())["scalars_hex"]]),
        ("holdout", [int(case["scalar_hex"], 16)
                     for case in json.loads(HOLDOUT.read_text())["cases"]]),
    ):
        totals = Counter()
        savings = Counter()
        for scalar in scalars:
            reference, candidate = one_scalar(scalar)
            totals.update(cases=1, reference_terms=reference[0],
                          reference_field_products=reference[1],
                          reference_rotations=reference[2], reference_depth=reference[3],
                          candidate_terms=candidate[0],
                          candidate_field_products=candidate[1],
                          candidate_rotations=candidate[2], candidate_depth=candidate[3],
                          candidate_lower_work=int(candidate[1] < reference[1]))
            savings[reference[1] - candidate[1]] += 1
        results[name] = {"totals": dict(sorted(totals.items())),
                         "product_saving_histogram": dict(sorted(savings.items()))}
    assert results["design"]["totals"] == {
        "cases": 4096, "reference_terms": 57343,
        "reference_field_products": 526168, "reference_rotations": 10082,
        "reference_depth": 200505, "candidate_terms": 53248,
        "candidate_field_products": 484163, "candidate_rotations": 9027,
        "candidate_depth": 199382, "candidate_lower_work": 4096,
    }
    report = {
        "schema": 1, "status": "independently_replayed_source_model",
        "design": results["design"], "holdout": results["holdout"],
        "frozen_design_sha256": sha(DESIGN), "holdout_sha256": sha(HOLDOUT),
        "plan_table_sha256": sha(PLANS), "screen_source_sha256": sha(Path(__file__)),
        "radix943_screen_sha256": sha(NATIVE / "radix943_screen.py"),
        "orbit_screen_sha256": sha(NATIVE / "unit_orbit_windows_screen.py"),
        "visited_radix_residues": len(residue_cache),
    }
    (HERE / "screen.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: result["totals"] for name, result in results.items()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
