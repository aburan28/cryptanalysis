#!/usr/bin/env python3
"""Independent decimal and direct quotient-orbit check of the screen."""

import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "complex-radix-screen-result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_orbits(a, b, norm):
    assert a * a - a * b + b * b == norm
    # The first adjugate row sends Z[omega]/(a+b*omega) to Z/norm.
    # These two witnesses have gcd(a-b,norm)=1, making this map bijective.
    lam = b * pow(a - b, -1, norm) % norm
    assert (lam * lam + lam + 1) % norm == 0
    units = {1, norm - 1, lam, -lam % norm, lam * lam % norm,
             -(lam * lam) % norm}
    assert len(units) == 6
    seen = bytearray(norm)
    orbits = 0
    for value in range(norm):
        if seen[value]:
            continue
        orbits += 1
        for unit in units:
            seen[unit * value % norm] = 1
    return orbits


def main():
    data = json.loads(RECEIPT.read_text())
    assert sha(HERE / "PROTOCOL.md") == data["source_sha256"]["protocol"]
    assert sha(HERE / "complex_radix_screen.py") == data["source_sha256"]["screen"]
    n = int(data["subgroup_order_hex"], 16)
    with localcontext() as context:
        context.prec = 90
        sqrt_n, sqrt3 = Decimal(n).sqrt(), Decimal(3).sqrt()
        threshold_checks = {}
        for norm in (889021, 889022, 889023, 889027):
            r = Decimal(norm).sqrt()
            passed = sqrt_n + sum(r**k for k in range(1, 14)) < sqrt3 * r**13
            threshold_checks[str(norm)] = passed
        assert threshold_checks == {
            "889021": False, "889022": True,
            "889023": True, "889027": True,
        }
        continuous_slots = Decimal(13) / 6 * (
            Decimal(n) / (sqrt3 - 1)**2
        ) ** (Decimal(1) / 13)
        assert Decimal(1_925_782) < continuous_slots < Decimal(1_925_783)

    norm_search = data["eisenstein_norm_search"]
    checked_orbits = {}
    for name in ("first_representable", "preferred_equal_slot_design"):
        witness = norm_search[name]
        a, b = witness["beta_a_plus_b_omega"]
        norm = witness["norm"]
        count = direct_orbits(a, b, norm)
        assert count == witness["orbit_slots_per_window"] == 148_172
        checked_orbits[name] = count

    capacity = data["fixed_slot_capacity"]
    for slots, label in ((12, "twelve"), (13, "thirteen")):
        b = capacity[label]["minimum_stored_nonidentity_points"]
        def product(points):
            q, extra = divmod(points, slots)
            return (1 + 6 * q) ** (slots - extra) * (7 + 6 * q) ** extra
        assert product(b - 1) < n <= product(b)
        assert str(product(b - 1)) == capacity[label]["product_at_previous"]
        assert str(product(b)) == capacity[label]["product_at_minimum"]

    verification = {
        "schema": 1,
        "status": "passed",
        "receipt_sha256": sha(RECEIPT),
        "verifier_sha256": sha(Path(__file__)),
        "decimal_precision": 90,
        "uniform_norm_checks": threshold_checks,
        "direct_quotient_orbits": checked_orbits,
        "capacity_products_checked": [12, 13],
        "cpu_timing_used": False,
    }
    output = HERE / "complex-radix-independent-verify.json"
    output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": verification["status"],
                      "direct_quotient_orbits": checked_orbits}, sort_keys=True))


if __name__ == "__main__":
    main()
