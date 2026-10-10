#!/usr/bin/env python3
"""Independent affine-curve replay of the selected 17-window tau format."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "prime-j0-tau-power16-20261010" / "verify_group.py"
sys.path.insert(0, str(BASE.parent))
spec = importlib.util.spec_from_file_location("tau_group", BASE)
group = importlib.util.module_from_spec(spec)
spec.loader.exec_module(group)
PANELS = ("prime-j0-cache-window-20261010", "prime-j0-tau384-matching-20261010")


def check_panel(name, widths, bounds, atlases, bases):
    path = ROOT / name / "fresh-inputs.json"
    raw = path.read_bytes()
    panel = json.loads(raw)
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == panel["count"] == 4096
    cache = {}
    bucket_counts = [0, 0]
    for case, scalar in enumerate(scalars):
        a, b = group.representative(scalar % group.ORDER)
        assert (a + b * group.LAMBDA_TAU - scalar) % group.ORDER == 0
        buckets = [None, None]
        for row, ((width, bound), (base, tau_base)) in enumerate(
                zip(zip(widths, bounds), bases)):
            atlas = atlases[(width, bound)]
            digit, seed_id, exponent, unit = atlas.decode(a, b)
            assert group.norm(digit) <= bound * bound
            if seed_id:
                key = (row, seed_id)
                if key not in cache:
                    sa, sb = atlas.seed(seed_id)
                    cache[key] = group.add(group.multiply(sa, base),
                                           group.multiply(sb, tau_base))
                buckets[exponent] = group.add(buckets[exponent],
                                              group.unit_point(cache[key], unit))
                bucket_counts[exponent] += 1
            radix = 1 << width
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0), (name, case)
        actual = group.add(buckets[0], group.tau_point(buckets[1]))
        expected = group.multiply(scalar % group.ORDER, group.G)
        assert actual == expected, (name, case)
    return {"cases": len(scalars), "panel_sha256": sha256(raw).hexdigest(),
            "bucket_terms": bucket_counts, "cached_seed_points": len(cache)}


def main():
    assert group.omega_point(group.G) == group.multiply(
        (1 - group.LAMBDA_TAU) % group.ORDER, group.G)
    assert group.tau_point(group.G) == group.multiply(group.LAMBDA_TAU, group.G)
    frontier = json.loads((HERE / "screen-result.json").read_text())
    selected = frontier["best"]["17"][0]
    widths, bounds = selected["widths"], selected["bounds"]
    atlases = {}
    saved = group.HERE
    for width, bound in sorted(set(zip(widths, bounds))):
        group.HERE = HERE / f"w{width}-d{bound}"
        atlases[(width, bound)] = group.Atlas(width)
    group.HERE = saved
    bases = []
    base = group.G
    for width in widths:
        bases.append((base, group.tau_point(base)))
        base = group.multiply(1 << width, base)
    result = {"schema": "prime-j0-tau-frontier-group17-v1",
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "group_source_sha256": sha256(BASE.read_bytes()).hexdigest(),
              "frontier_sha256": sha256((HERE / "screen-result.json").read_bytes()).hexdigest(),
              "atlas_sha256": {f"w{w}-d{d}": atlas.sha256
                               for (w, d), atlas in atlases.items()},
              "point_slots": selected["point_slots"],
              "panels": {name: check_panel(name, widths, bounds, atlases, bases)
                         for name in PANELS}}
    (HERE / "group17-check.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"point_slots": result["point_slots"],
                      "panel_checks": {k: v["cases"] for k, v in result["panels"].items()}},
                     sort_keys=True))


if __name__ == "__main__":
    main()
