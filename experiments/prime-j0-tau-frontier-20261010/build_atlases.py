#!/usr/bin/env python3
"""Construct exact frontier atlases and replay the frozen scalar panels."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "prime-j0-tau-power16-20261010" / "screen.py"
spec = importlib.util.spec_from_file_location("tau_base_screen", BASE)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
PANELS = ("prime-j0-cache-window-20261010", "prime-j0-tau384-matching-20261010")
CONFIGS = ((6, 64), (6, 44), (7, 128), (7, 90), (8, 256))


def build_all():
    result = {}
    for width, bound in CONFIGS:
        target = HERE / f"w{width}-d{bound}"
        target.mkdir(exist_ok=True)
        source.HERE = target
        source.LIMITS[width] = bound
        codes, seeds, receipt = source.build_atlas(width)
        result[(width, bound)] = (codes, seeds, receipt)
    return result


def replay(name, widths, bounds, atlases):
    path = ROOT / name / "fresh-inputs.json"
    raw = path.read_bytes()
    panel = json.loads(raw)
    values = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(values) == panel["count"] == 4096
    bucket_counts = Counter()
    for scalar in values:
        start = source.representative(scalar % source.ORDER)
        assert (start[0] + start[1] * 0xAC9C52B33FA3CF1F5AD9E3FD77ED9BA4A880B9FC8EC739C2E0CFC810B51283D0 - scalar) % source.ORDER == 0
        a, b = start
        reconstruction = [0, 0]
        power = 1
        for width, bound in zip(widths, bounds):
            radix = 1 << width
            codes, seeds, _ = atlases[(width, bound)]
            digit, exponent = source.digit_from_code(codes[source.index((a, b), radix)], seeds)
            assert source.norm(digit) <= bound * bound
            assert (a - digit[0]) % radix == (b - digit[1]) % radix == 0
            reconstruction[0] += power * digit[0]
            reconstruction[1] += power * digit[1]
            bucket_counts[exponent] += int(digit != (0, 0))
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
            power *= radix
        assert (a, b) == (0, 0) and tuple(reconstruction) == start
    return {"cases": len(values), "panel_sha256": sha256(raw).hexdigest(),
            "nonidentity_by_bucket": dict(bucket_counts)}


def main():
    frontier = json.loads((HERE / "screen-result.json").read_text())
    atlases = build_all()
    checks = {}
    for count in (17, 18, 19):
        candidate = frontier["best"][str(count)][0]
        widths, bounds = candidate["widths"], candidate["bounds"]
        assert set(zip(widths, bounds)) <= set(atlases)
        assert sum(atlases[item][2]["seed_count"] for item in zip(widths, bounds)) == candidate["point_slots"]
        checks[str(count)] = {name: replay(name, widths, bounds, atlases)
                              for name in PANELS}
    receipt = {"schema": "prime-j0-tau-frontier-atlas-replay-v1",
               "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "base_source_sha256": sha256(BASE.read_bytes()).hexdigest(),
               "frontier_sha256": sha256((HERE / "screen-result.json").read_bytes()).hexdigest(),
               "atlases": {f"w{w}-d{d}": item[2] for (w, d), item in atlases.items()},
               "panels": checks}
    (HERE / "atlas-replay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"atlases": {k: v["seed_count"] for k, v in receipt["atlases"].items()},
                      "panel_checks": {k: sum(v["cases"] for v in rows.values())
                                       for k, rows in checks.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
