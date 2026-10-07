#!/usr/bin/env python3
"""Independent Sage group replay of the frozen selective mixed digit stream."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from mixed_atlas_screen import make_options
from seed_chain_bound import orbit
from selective_mixed_atlas import FIXTURES, UNION_SEEDS, recode


HERE = Path(__file__).resolve().parent
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F


def check_fixture(path, tables, options):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    curve = EllipticCurve(GF(P), [0, 7])
    beta = curve.base_field()(int(fixture["beta_hex"], 16))
    assert beta**3 == 1 and beta != 1
    cache = {}
    digest = hashlib.sha256()
    checked_digits = 0
    for case in fixture["cases"]:
        base_key = case["base_x_hex"], case["base_y_hex"]
        if base_key not in cache:
            base = curve(int(base_key[0], 16), int(base_key[1], 16))
            omega_base = curve(beta * base[0], base[1])
            tau_base = base - omega_base
            cache[base_key] = (base, tau_base, {})
        base, tau_base, digit_points = cache[base_key]
        short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        digits, _ = recode(short, tables, options)
        accumulator = curve(0)
        for digit in reversed(digits):
            if accumulator != curve(0):
                omega_accumulator = curve(beta * accumulator[0], accumulator[1])
                accumulator -= omega_accumulator
            if digit is None:
                continue
            a, b, seed = digit
            assert (a, b) in orbit(UNION_SEEDS[seed])
            if (a, b) not in digit_points:
                digit_points[a, b] = a * base + b * tau_base
            accumulator += digit_points[a, b]
            checked_digits += 1
        if case.get("expected_identity", False):
            expected = curve(0)
        else:
            expected = curve(int(case["expected_x_hex"], 16),
                             int(case["expected_y_hex"], 16))
        assert accumulator == expected, f"scalar replay mismatch at {path.name}:{case['index']}"
        digest.update(case["base_x_hex"].encode())
        digest.update(case["scalar_hex"].encode())
        digest.update(b"identity" if accumulator == curve(0) else
                      f"{int(accumulator[0]):064x}{int(accumulator[1]):064x}".encode())
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(fixture["cases"]),
            "base_points": len(cache),
            "nonzero_digit_additions": checked_digits,
            "output_digest_sha256": digest.hexdigest(),
            "verified": True}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = [check_fixture(path, tables, options) for path in FIXTURES]
    assert [panel["cases"] for panel in panels] == [64, 256]
    result = {
        "schema": 1, "curve": "secp256k1",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "selector_sha256": hashlib.sha256((HERE / "selective_mixed_atlas.py").read_bytes()).hexdigest(),
        "runtime_info_sha256": hashlib.sha256((HERE / "selective-runtime-info.json").read_bytes()).hexdigest(),
        "panels": panels, "verified": True,
        "cpu_speedup_claim": None,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
