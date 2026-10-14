#!/usr/bin/env python3
"""Exhaustively bound one-axis tables for mixed-radix Eisenstein digits."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import model


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "selective-holdout.json"
ATLAS = (("512", 512, model.mixed.ATLAS512),
         ("640", 640, model.mixed.ATLAS640),
         ("391", 640, model.mixed.ATLAS391))


def evaluate() -> dict:
    atlases = model.atlas_records()
    bounds = {}
    for label, radix, path in ATLAS:
        atlas = atlases[label][0]
        maximum = [0, 0]
        for ra in range(radix):
            for rb in range(radix):
                digit, _, _, _ = atlas.decode(ra, rb)
                maximum[0] = max(maximum[0], abs(digit[0]))
                maximum[1] = max(maximum[1], abs(digit[1]))
        axis_max = max(maximum)
        bounds[label] = {
            "residue_pairs_checked": radix * radix,
            "coordinate_max_abs": maximum,
            "axis_max_abs": axis_max,
            "axis_entries_including_zero": axis_max + 1,
            "axis_bytes": 64 * (axis_max + 1),
            "atlas_sha256": sha256(path.read_bytes()).hexdigest(),
            "atlas_bytes": path.stat().st_size,
        }

    fixture_bytes = FIXTURE.read_bytes()
    cases = json.loads(fixture_bytes)["cases"]
    term_distribution = Counter()
    component_totals = [0, 0]
    for case in cases:
        a, b = model.mixed.screen.representative(
            int(case["scalar_hex"], 16) % model.mixed.screen.ORDER)
        counts = [0, 0]
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, _, _, _ = atlases[label][0].decode(a, b)
            assert max(abs(digit[0]), abs(digit[1])) <= bounds[label]["axis_max_abs"]
            counts[0] += digit[0] != 0
            counts[1] += digit[1] != 0
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
        component_totals[0] += counts[0]
        component_totals[1] += counts[1]
        term_distribution[str(sum(counts))] += 1

    entries = 6 * bounds["512"]["axis_entries_including_zero"]
    entries += 7 * bounds["640"]["axis_entries_including_zero"]
    entries += bounds["391"]["axis_entries_including_zero"]
    atlas_bytes = sum(row["atlas_bytes"] for row in bounds.values())
    return {
        "schema": 1,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": sha256(fixture_bytes).hexdigest(),
        "bounds": bounds,
        "windows": 14,
        "axis_entries_including_zero": entries,
        "axis_point_bytes": 64 * entries,
        "atlas_bytes": atlas_bytes,
        "point_and_atlas_bytes": 64 * entries + atlas_bytes,
        "holdout_cases": len(cases),
        "holdout_component_terms": component_totals,
        "holdout_total_term_distribution": dict(sorted(term_distribution.items())),
    }


if __name__ == "__main__":
    result = evaluate()
    path = HERE / "axial-model.json"
    if sys.argv[1:] == ["--write"]:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    elif sys.argv[1:] == []:
        assert json.loads(path.read_text()) == result
    else:
        raise SystemExit("usage: axial_model.py [--write]")
    print(json.dumps({key: result[key] for key in (
        "axis_entries_including_zero", "axis_point_bytes", "atlas_bytes",
        "point_and_atlas_bytes", "holdout_component_terms",
        "holdout_total_term_distribution")}, sort_keys=True))
