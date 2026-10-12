#!/usr/bin/env python3
"""Independent Sage seed points for the mixed-radix native replay."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

from selective_mixed_atlas import UNION_SEEDS


HERE = Path(__file__).resolve().parent
FIXTURES = (HERE / "mixed-radix-fixture.json",)
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F


def main():
    curve = EllipticCurve(GF(P), [0, 7])
    panels = {}
    beta_hex = None
    for path in FIXTURES:
        raw = path.read_bytes()
        fixture = json.loads(raw)
        if beta_hex is None:
            beta_hex = fixture["beta_hex"]
        else:
            assert fixture["beta_hex"] == beta_hex
        beta = curve.base_field()(int(beta_hex, 16))
        assert beta**3 == 1 and beta != 1
        bases = {}
        for case in fixture["cases"]:
            key = case["base_x_hex"], case["base_y_hex"]
            if key in bases:
                continue
            base = curve(int(key[0], 16), int(key[1], 16))
            omega_base = curve(beta * base[0], base[1])
            tau_base = base - omega_base
            seeds = []
            for a, b in UNION_SEEDS:
                point = a * base + b * tau_base
                assert point != curve(0)
                seeds.append([f"{int(point[0]):064x}", f"{int(point[1]):064x}"])
            bases[key] = {"base_x_hex": key[0], "base_y_hex": key[1],
                          "seeds": seeds}
        panels[path.name] = {
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(fixture["cases"]),
            "bases": list(bases.values()),
        }
    assert [len(panels[path.name]["bases"]) for path in FIXTURES] == [8]
    result = {
        "schema": 1, "curve": "secp256k1", "beta_hex": beta_hex,
        "seed_coefficients": UNION_SEEDS,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "panels": panels,
    }
    target = HERE / "mixed-radix-seed-fixture.json"
    if target.exists():
        raise SystemExit("mixed-radix seed fixture exists; refusing overwrite")
    target.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"bases": sum(len(p["bases"]) for p in panels.values()),
                      "seed_points": 12 * sum(len(p["bases"]) for p in panels.values()),
                      "fixture_sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
